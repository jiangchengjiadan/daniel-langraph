"""错误处理节点 - LangGraph Node实现"""

from .. import TripPlanState
from ...models.schemas import TripPlan, DayPlan, Attraction, Meal,WeatherInfo as Weather, Budget, Hotel
from typing import Dict, List


def create_fallback_plan(state: TripPlanState) -> TripPlan:
    """
    创建备用行程计划

    当某些Agent失败或返回数据不完整时，生成一个基本的备用计划

    Args:
        state: 当前状态

    Returns:
        备用的TripPlan对象
    """
    city = state.get("city", "未知城市")
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")
    travel_days = state.get("travel_days", 3)
    transportation = state.get("transportation", "公共交通")
    accommodation = state.get("accommodation", "经济型酒店")

    # 创建每天的计划
    days = []
    for day_idx in range(travel_days):
        # 基本的景点推荐
        attractions = [
            Attraction(
                name=f"{city}市中心",
                address=f"{city}市中心区域",
                location={"longitude": 0.0, "latitude": 0.0},
                visit_duration=120,
                description=f"探索{city}的城市中心区域，感受当地文化氛围",
                category="城市观光",
                ticket_price=0
            ),
            Attraction(
                name=f"{city}特色街区",
                address=f"{city}老城区",
                location={"longitude": 0.0, "latitude": 0.0},
                visit_duration=90,
                description=f"漫步{city}的特色街区，体验当地生活",
                category="文化体验",
                ticket_price=0
            )
        ]

        # 基本的餐饮推荐
        meals = [
            Meal(
                type="breakfast",
                name="当地特色早餐",
                description=f"品尝{city}的地道早餐",
                estimated_cost=25
            ),
            Meal(
                type="lunch",
                name="当地特色午餐",
                description=f"享用{city}的特色菜肴",
                estimated_cost=50
            ),
            Meal(
                type="dinner",
                name="当地特色晚餐",
                description=f"品尝{city}的美食",
                estimated_cost=80
            )
        ]

        # 基本的酒店推荐
        hotel = Hotel(
            name=f"{city}{accommodation}",
            address=f"{city}市中心",
            location={"longitude": 0.0, "latitude": 0.0},
            price_range="300-500元",
            rating="4.0",
            distance="市中心位置",
            type=accommodation,
            estimated_cost=400
        )

        day_plan = DayPlan(
            date=start_date if day_idx == 0 else "",  # 简化处理
            day_index=day_idx,
            description=f"第{day_idx + 1}天：探索{city}",
            transportation=transportation,
            accommodation=accommodation,
            hotel=hotel,
            attractions=attractions,
            meals=meals
        )

        days.append(day_plan)

    # 创建天气信息（默认值）
    weather_info = [
        Weather(
            date=start_date if i == 0 else "",
            day_weather="晴",
            night_weather="晴",
            day_temp=25,
            night_temp=15,
            wind_direction="南风",
            wind_power="1-3级"
        )
        for i in range(travel_days)
    ]

    # 创建预算信息
    budget = Budget(
        total_attractions=0,
        total_hotels=400 * travel_days,
        total_meals=155 * travel_days,
        total_transportation=100,
        total=400 * travel_days + 155 * travel_days + 100
    )

    # 创建行程计划
    trip_plan = TripPlan(
        city=city,
        start_date=start_date,
        end_date=end_date,
        days=days,
        weather_info=weather_info,
        overall_suggestions=f"这是一个基本的{city}旅行计划。由于部分信息获取失败，建议您出行前查阅最新的景点和天气信息，或咨询当地旅游局获取更详细的建议。",
        budget=budget
    )

    return trip_plan


def error_handler_node(state: TripPlanState) -> TripPlanState:
    """
    错误处理节点

    功能：当其他节点失败时，生成备用计划并记录错误信息

    Args:
        state: 当前状态，可能包含错误信息

    Returns:
        更新后的状态，包含备用的itinerary
    """
    try:
        errors = state.get("errors", [])
        print(f"[ERROR_HANDLER] 进入错误处理节点")
        print(f"[ERROR_HANDLER] 错误列表: {errors}")

        # 生成备用计划
        fallback_plan = create_fallback_plan(state)

        # 构建执行日志
        log_entry = {
            "node": "error_handler",
            "status": "fallback",
            "original_errors": errors,
            "message": "使用备用计划"
        }

        # 添加警告信息到错误列表
        errors_with_warning = [
            *errors,
            "注意：由于部分信息获取失败，已生成备用计划。建议出行前核实相关信息。"
        ]

        # 返回更新后的状态
        return {
            **state,
            "itinerary": fallback_plan.model_dump(),
            "budget": fallback_plan.budget.model_dump() if fallback_plan.budget else None,
            "status": "completed_with_fallback",
            "errors": errors_with_warning,
            "execution_log": [
                *state.get("execution_log", []),
                log_entry
            ]
        }

    except Exception as e:
        # 即使错误处理节点本身失败，也要返回一个最小的状态
        error_msg = f"错误处理节点失败: {str(e)}"
        print(f"[ERROR] {error_msg}")

        log_entry = {
            "node": "error_handler",
            "status": "failed",
            "error": str(e)
        }

        return {
            **state,
            "status": "failed",
            "errors": [*state.get("errors", []), error_msg],
            "execution_log": [
                *state.get("execution_log", []),
                log_entry
            ]
        }


__all__ = ["error_handler_node", "create_fallback_plan"]
