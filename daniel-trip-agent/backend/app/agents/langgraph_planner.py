"""基于 LangGraph 的旅行规划器"""

from langgraph.graph import StateGraph, END
from . import TripPlanState
from .nodes import (attraction_search_node,hotel_search_node,itinerary_planning_node,
                   error_handler_node,weather_query_node)
from ..models.schemas import TripRequest, TripPlan
from typing import Literal
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
        1. 并行执行：景点搜索、天气查询、酒店搜索
        2. 汇聚到：行程规划节点
        3. 条件路由：成功 -> END，失败 -> 错误处理 -> END
        """
        # 创建StateGraph
        graph = StateGraph(TripPlanState)

        # 添加所有节点
        graph.add_node("attraction_search", attraction_search_node)
        graph.add_node("weather_query", weather_query_node)
        graph.add_node("hotel_search", hotel_search_node)
        graph.add_node("itinerary_planning", itinerary_planning_node)
        graph.add_node("error_handler", error_handler_node)

        # 设置入口点（3个搜索节点并行执行）
        graph.set_entry_point("attraction_search")
        graph.set_entry_point("weather_query")
        graph.set_entry_point("hotel_search")

        # 3个搜索节点都汇聚到行程规划节点
        graph.add_edge("attraction_search", "itinerary_planning")
        graph.add_edge("weather_query", "itinerary_planning")
        graph.add_edge("hotel_search", "itinerary_planning")

        # 从行程规划节点添加条件路由
        graph.add_conditional_edges(
            "itinerary_planning",
            self._route_after_planning,
            {
                "success": END,
                "error": "error_handler"
            }
        )

        # 错误处理节点直接结束
        graph.add_edge("error_handler", END)

        return graph

    def _route_after_planning(self, state: TripPlanState) -> Literal["success", "error"]:
        """
        决定行程规划后的路由

        如果有行程计划，则成功；否则进入错误处理
        """
        # 如果有行程计划并且状态是完成的，则成功
        if state.get("itinerary") and state.get("status") == "completed":
            return "success"

        # 否则进入错误处理
        return "error"

    async def plan_trip(self, request: TripRequest) -> TripPlan:
        """
        执行旅行规划

        Args:
            request: 旅行请求

        Returns:
            旅行计划

        Raises:
            Exception: 如果规划失败
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🚀 开始 LangGraph 旅行规划...")
            logger.info(f"目的地: {request.city}")
            logger.info(f"日期: {request.start_date} 至 {request.end_date}")
            logger.info(f"天数: {request.travel_days}天")
            logger.info(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
            logger.info(f"{'='*60}\n")

            # 构建初始状态
            initial_state: TripPlanState = {
                "city": request.city,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "travel_days": request.travel_days,
                "preferences": request.preferences,
                "accommodation": request.accommodation,
                "transportation": request.transportation,
                "free_text_input": request.free_text_input,
                "attractions": [],
                "weather_data": {},
                "hotels": [],
                "itinerary": None,
                "budget": None,
                "errors": [],
                "execution_log": [],
                "status": "processing"
            }

            # 执行图
            logger.info("📊 开始执行 LangGraph 工作流...")
            final_state = await self.app.ainvoke(initial_state)

            # 记录执行日志
            if final_state.get("execution_log"):
                logger.info("\n📋 执行日志:")
                for log_entry in final_state["execution_log"]:
                    node = log_entry.get("node", "unknown")
                    status = log_entry.get("status", "unknown")
                    logger.info(f"  - {node}: {status}")

            # 记录错误信息
            if final_state.get("errors"):
                logger.warning("\n⚠️  错误信息:")
                for error in final_state["errors"]:
                    logger.warning(f"  - {error}")

            # 检查是否有行程计划
            if final_state.get("itinerary"):
                trip_plan = TripPlan(**final_state["itinerary"])

                logger.info(f"\n{'='*60}")
                logger.info(f"✅ 旅行计划生成完成!")
                logger.info(f"   城市: {trip_plan.city}")
                logger.info(f"   天数: {len(trip_plan.days)}天")
                if trip_plan.budget:
                    logger.info(f"   总预算: {trip_plan.budget.total}元")
                logger.info(f"{'='*60}\n")

                return trip_plan
            else:
                # 如果没有行程计划，抛出异常
                error_msg = "未能生成行程计划"
                if final_state.get("errors"):
                    error_msg += f": {'; '.join(final_state['errors'])}"
                raise Exception(error_msg)

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
