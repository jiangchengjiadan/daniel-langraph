"""基于 LangGraph 的旅行规划器"""

from langgraph.graph import StateGraph, START, END
from . import TripPlanState
from .nodes import (
    attraction_search_node,
    error_handler_node,
    hotel_product_search_node,
    hotel_search_node,
    itinerary_planning_node,
    product_enrichment_node,
    ticket_product_search_node,
    weather_query_node,
)
from ..models.schemas import TripRequest, TripPlan
from typing import Any, Dict, List, Literal
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class LangGraphTripPlanner:
    """基于LangGraph的旅行规划器"""

    def __init__(self):
        """初始化LangGraph规划器"""
        logger.info("初始化 LangGraph 旅行规划器...")
        self.graph = self._build_graph()
        self.app = self.graph.compile()
        logger.info("✅ LangGraph 旅行规划器初始化成功")

    def _build_graph(self) -> StateGraph:
        """
        构建计算图

        图结构：
        1. 并行执行：景点搜索、天气查询、酒店搜索、酒店商品搜索
        2. 景点搜索完成后查询门票商品
        3. 汇聚到：行程规划节点
        4. 成功或 fallback 后都进入商品回填节点
        """
        # 创建StateGraph
        graph = StateGraph(TripPlanState)

        # 添加所有节点
        graph.add_node("attraction_search", attraction_search_node)
        graph.add_node("weather_query", weather_query_node)
        graph.add_node("hotel_search", hotel_search_node)
        graph.add_node("hotel_product_search", hotel_product_search_node)
        graph.add_node("ticket_product_search", ticket_product_search_node)
        graph.add_node("itinerary_planning", itinerary_planning_node)
        graph.add_node("product_enrichment", product_enrichment_node)
        graph.add_node("error_handler", error_handler_node)

        # 从 START 扇出，信息采集节点并行执行
        graph.add_edge(START, "attraction_search")
        graph.add_edge(START, "weather_query")
        graph.add_edge(START, "hotel_search")
        graph.add_edge(START, "hotel_product_search")

        # 门票商品搜索依赖景点名称
        graph.add_edge("attraction_search", "ticket_product_search")

        # 等待信息采集与商品增强节点完成后，再汇聚到行程规划节点
        graph.add_edge(
            ["weather_query", "hotel_search", "hotel_product_search", "ticket_product_search"],
            "itinerary_planning",
        )

        # 从行程规划节点添加条件路由
        graph.add_conditional_edges(
            "itinerary_planning",
            self._route_after_planning,
            {
                "success": "product_enrichment",
                "error": "error_handler"
            }
        )

        # 错误处理节点生成 fallback 后也尝试商品回填
        graph.add_edge("error_handler", "product_enrichment")
        graph.add_edge("product_enrichment", END)

        return graph

    def _route_after_planning(self, state: TripPlanState) -> Literal["success", "error"]:
        """
        决定行程规划后的路由

        如果有行程计划，则成功；否则进入错误处理
        """
        # 如果有行程计划并且状态是完成的，则成功。错误处理节点会返回 completed_with_fallback。
        if state.get("itinerary") and state.get("status") in {"completed", "completed_with_fallback"}:
            return "success"

        # 否则进入错误处理
        return "error"

    def _build_initial_state(self, request: TripRequest, city: str, start_date: str, end_date: str, travel_days: int) -> TripPlanState:
        return {
            "city": city,
            "cities": request.cities,
            "current_city": city,
            "city_segments": [],
            "start_date": start_date,
            "end_date": end_date,
            "travel_days": travel_days,
            "preferences": request.preferences,
            "accommodation": request.accommodation,
            "transportation": request.transportation,
            "free_text_input": request.free_text_input,
            "attractions": [],
            "weather_data": {},
            "hotels": [],
            "hotel_products": [],
            "ticket_products": [],
            "itinerary": None,
            "budget": None,
            "errors": [],
            "execution_log": [],
            "status": "processing",
        }

    def _allocate_city_segments(self, request: TripRequest) -> List[Dict[str, Any]]:
        start = datetime.strptime(request.start_date, "%Y-%m-%d").date()
        city_count = len(request.cities)
        total_days = request.travel_days
        base_days = max(1, total_days // city_count)
        remainder = max(0, total_days - base_days * city_count)

        segments: List[Dict[str, Any]] = []
        cursor = start
        for index, city in enumerate(request.cities):
            allocated = base_days + (1 if index < remainder else 0)
            if index == city_count - 1:
                used_days = sum(segment["travel_days"] for segment in segments)
                allocated = max(1, total_days - used_days)
            segment_end = cursor + timedelta(days=allocated - 1)
            segments.append(
                {
                    "city": city,
                    "start_date": cursor.isoformat(),
                    "end_date": segment_end.isoformat(),
                    "travel_days": allocated,
                }
            )
            cursor = segment_end + timedelta(days=1)
        return segments

    async def _run_single_city_plan(self, request: TripRequest, segment: Dict[str, Any]) -> TripPlan:
        logger.info(
            "📍 规划城市段: city=%s, date=%s~%s, days=%s",
            segment["city"],
            segment["start_date"],
            segment["end_date"],
            segment["travel_days"],
        )
        final_state = await self.app.ainvoke(
            self._build_initial_state(
                request=request,
                city=segment["city"],
                start_date=segment["start_date"],
                end_date=segment["end_date"],
                travel_days=segment["travel_days"],
            )
        )
        logger.info(
            "📦 城市段结束: city=%s, status=%s, has_itinerary=%s, errors=%s",
            segment["city"],
            final_state.get("status"),
            bool(final_state.get("itinerary")),
            len(final_state.get("errors", [])),
        )
        if not final_state.get("itinerary"):
            error_msg = "未能生成行程计划"
            if final_state.get("errors"):
                error_msg += f": {'; '.join(final_state['errors'])}"
            raise Exception(f"{segment['city']} {error_msg}")
        return TripPlan(**final_state["itinerary"])

    def _merge_trip_plans(self, request: TripRequest, plans: List[TripPlan]) -> TripPlan:
        merged_days: List[Dict[str, Any]] = []
        merged_weather: List[Dict[str, Any]] = []
        total_budget = {
            "total_attractions": 0,
            "total_hotels": 0,
            "total_meals": 0,
            "total_transportation": 0,
            "total": 0,
        }
        suggestions: List[str] = []

        for plan in plans:
            if plan.overall_suggestions:
                suggestions.append(f"{plan.city}：{plan.overall_suggestions}")
            for weather in plan.weather_info:
                merged_weather.append(weather.model_dump())
            if plan.budget:
                total_budget["total_attractions"] += plan.budget.total_attractions
                total_budget["total_hotels"] += plan.budget.total_hotels
                total_budget["total_meals"] += plan.budget.total_meals
                total_budget["total_transportation"] += plan.budget.total_transportation

        day_index = 0
        for plan in plans:
            for day in plan.days:
                day_dict = day.model_dump()
                day_dict["city"] = plan.city
                day_dict["day_index"] = day_index
                merged_days.append(day_dict)
                day_index += 1

        total_budget["total"] = sum(total_budget.values()) - total_budget["total"]
        merged_data = {
            "city": request.primary_city,
            "cities": request.cities,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "days": merged_days,
            "weather_info": merged_weather,
            "overall_suggestions": "；".join(suggestions) if suggestions else f"建议按 {' -> '.join(request.cities)} 的顺序游览。",
            "budget": total_budget,
        }
        return TripPlan(**merged_data)

    async def plan_trip(self, request: TripRequest) -> TripPlan:
        """执行旅行规划"""
        try:
            logger.info(f"\n{'='*60}")
            logger.info("🚀 开始 LangGraph 旅行规划...")
            logger.info("目的地: %s", " -> ".join(request.cities))
            logger.info(f"日期: {request.start_date} 至 {request.end_date}")
            logger.info(f"天数: {request.travel_days}天")
            logger.info(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
            logger.info(f"{'='*60}\n")

            if len(request.cities) == 1:
                trip_plan = await self._run_single_city_plan(
                    request,
                    {
                        "city": request.primary_city,
                        "start_date": request.start_date,
                        "end_date": request.end_date,
                        "travel_days": request.travel_days,
                    },
                )
            else:
                segments = self._allocate_city_segments(request)
                plans = []
                for segment in segments:
                    plans.append(await self._run_single_city_plan(request, segment))
                trip_plan = self._merge_trip_plans(request, plans)

            logger.info(f"\n{'='*60}")
            logger.info("✅ 旅行计划生成完成!")
            logger.info("   城市: %s", " -> ".join(trip_plan.cities or [trip_plan.city]))
            logger.info(f"   天数: {len(trip_plan.days)}天")
            if trip_plan.budget:
                logger.info(f"   总预算: {trip_plan.budget.total}元")
            logger.info(f"{'='*60}\n")
            return trip_plan

        except Exception as e:
            logger.error(f"❌ LangGraph 旅行规划失败: {str(e)}")
            raise


# === 单例模式 ===

_langgraph_planner_instance = None


def get_langgraph_trip_planner() -> LangGraphTripPlanner:
    """
    获取 LangGraph 旅行规划器单例

    Returns:
        LangGraphTripPlanner 实例
    """
    global _langgraph_planner_instance

    if _langgraph_planner_instance is None:
        _langgraph_planner_instance = LangGraphTripPlanner()

    return _langgraph_planner_instance


__all__ = ["LangGraphTripPlanner", "get_langgraph_trip_planner"]
