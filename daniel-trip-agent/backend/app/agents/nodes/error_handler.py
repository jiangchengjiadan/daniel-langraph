"""错误处理节点 - LangGraph Node实现"""

from .. import TripPlanState
from ...models.schemas import TripPlan, DayPlan, Attraction, Meal,WeatherInfo as Weather, Budget, Hotel
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _date_for_day(start_date: str, day_idx: int) -> str:
    """根据开始日期生成第 N 天日期。"""
    try:
        return (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=day_idx)).strftime("%Y-%m-%d")
    except ValueError:
        return start_date if day_idx == 0 else ""


def _parse_location(value: Any) -> Dict[str, float]:
    """兼容高德 POI 的 'lng,lat' 字符串和对象坐标。"""
    if isinstance(value, dict):
        return {
            "longitude": float(value.get("longitude") or value.get("lng") or 0.0),
            "latitude": float(value.get("latitude") or value.get("lat") or 0.0),
        }

    if isinstance(value, str) and "," in value:
        lng, lat = value.split(",", 1)
        try:
            return {"longitude": float(lng), "latitude": float(lat)}
        except ValueError:
            pass

    return {"longitude": 0.0, "latitude": 0.0}


def _estimate_ticket_price(name: str, category: str = "") -> int:
    """给缺少票价的 POI 做教学演示用估算，避免 fallback 预算全为 0。"""
    text = f"{name} {category}"
    if any(keyword in text for keyword in ["故宫", "长城", "颐和园", "圆明园", "天坛"]):
        return 60
    if any(keyword in text for keyword in ["景区", "风景名胜", "遗址", "古迹", "塔", "宫"]):
        return 50
    if any(keyword in text for keyword in ["博物馆", "美术馆", "艺术馆", "展览"]):
        return 30
    if any(keyword in text for keyword in ["寺", "观", "教堂"]):
        return 20
    if any(keyword in text for keyword in ["公园", "广场", "街区", "商业街"]):
        return 0
    return 30


def _fallback_attraction_from_poi(poi: Dict[str, Any], city: str) -> Attraction:
    """把采集节点返回的 POI 转成前端可展示的 Attraction。"""
    name = poi.get("name") or poi.get("名称") or f"{city}景点"
    category = poi.get("type") or poi.get("类型") or "景点"
    ticket_price = poi.get("ticket_price")
    if ticket_price in (None, "", 0):
        ticket_price = _estimate_ticket_price(name, category)

    return Attraction(
        name=name,
        address=poi.get("address") or poi.get("地址") or f"{city}市区",
        location=_parse_location(poi.get("location") or poi.get("坐标")),
        visit_duration=120,
        description=f"{name}是{city}适合本次偏好的推荐地点，建议预留约2小时游览。",
        category=category,
        rating=poi.get("rating") or poi.get("评分"),
        ticket_price=int(ticket_price),
    )


def _fallback_hotel_from_poi(poi: Optional[Dict[str, Any]], city: str, accommodation: str) -> Hotel:
    """把酒店 POI 转成前端可展示的 Hotel。"""
    if accommodation in {"豪华酒店", "高档型酒店", "五星级酒店"}:
        price_range = "800-1500元"
        estimated_cost = 1000
    elif accommodation in {"舒适型酒店", "商务酒店"}:
        price_range = "400-700元"
        estimated_cost = 500
    elif accommodation in {"民宿", "民宿客栈"}:
        price_range = "200-500元"
        estimated_cost = 350
    else:
        price_range = "200-400元"
        estimated_cost = 300

    if not poi:
        return Hotel(
            name=f"{city}{accommodation}",
            address=f"{city}市中心",
            location={"longitude": 0.0, "latitude": 0.0},
            price_range=price_range,
            rating="4.0",
            distance="市中心位置",
            type=accommodation,
            estimated_cost=estimated_cost
        )

    return Hotel(
        name=poi.get("name") or poi.get("名称") or f"{city}{accommodation}",
        address=poi.get("address") or poi.get("地址") or f"{city}市中心",
        location=_parse_location(poi.get("location") or poi.get("坐标")),
        price_range=price_range,
        rating=str(poi.get("rating") or poi.get("评分") or "4.0"),
        distance="靠近主要游览区域",
        type=accommodation,
        estimated_cost=estimated_cost
    )


def _weather_for_day(weather_data: Dict[str, Any], start_date: str, day_idx: int) -> Weather:
    """从采集到的天气中取对应天，缺失时使用稳定兜底值。"""
    target_date = _date_for_day(start_date, day_idx)
    forecasts = weather_data.get("forecasts", []) if isinstance(weather_data, dict) else []
    source = forecasts[day_idx] if day_idx < len(forecasts) else {}

    return Weather(
        date=target_date,
        day_weather=source.get("day_weather") or "晴",
        night_weather=source.get("night_weather") or "多云",
        day_temp=source.get("day_temp") or 25,
        night_temp=source.get("night_temp") or 15,
        wind_direction=source.get("day_wind") or source.get("wind_direction") or "南风",
        wind_power=source.get("day_power") or source.get("wind_power") or "1-3级"
    )


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
    collected_attractions = state.get("attractions", []) or []
    collected_hotels = state.get("hotels", []) or []
    weather_data = state.get("weather_data", {}) or {}

    # 创建每天的计划
    days = []
    for day_idx in range(travel_days):
        start = day_idx * 2
        poi_slice = collected_attractions[start:start + 3] or collected_attractions[:3]
        if poi_slice:
            attractions = [_fallback_attraction_from_poi(poi, city) for poi in poi_slice]
        else:
            attractions = [
                Attraction(
                    name=f"{city}代表景点",
                    address=f"{city}核心游览区域",
                    location={"longitude": 0.0, "latitude": 0.0},
                    visit_duration=120,
                    description=f"探索{city}代表性景点，了解当地历史与文化。",
                    category="城市观光",
                    ticket_price=30
                ),
                Attraction(
                    name=f"{city}特色街区",
                    address=f"{city}老城区",
                    location={"longitude": 0.0, "latitude": 0.0},
                    visit_duration=90,
                    description=f"漫步{city}特色街区，体验当地生活和饮食。",
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

        hotel = _fallback_hotel_from_poi(
            collected_hotels[day_idx % len(collected_hotels)] if collected_hotels else None,
            city,
            accommodation
        )

        day_plan = DayPlan(
            date=_date_for_day(start_date, day_idx),
            day_index=day_idx,
            description=f"第{day_idx + 1}天：探索{city}",
            transportation=transportation,
            accommodation=accommodation,
            hotel=hotel,
            attractions=attractions,
            meals=meals
        )

        days.append(day_plan)

    weather_info = [_weather_for_day(weather_data, start_date, i) for i in range(travel_days)]

    # 创建预算信息
    total_attractions = sum(
        attraction.ticket_price
        for day in days
        for attraction in day.attractions
    )
    total_hotels = sum((day.hotel.estimated_cost if day.hotel else 400) for day in days)
    total_meals = sum(meal.estimated_cost for day in days for meal in day.meals)
    total_transportation = 100 * travel_days
    budget = Budget(
        total_attractions=total_attractions,
        total_hotels=total_hotels,
        total_meals=total_meals,
        total_transportation=total_transportation,
        total=total_attractions + total_hotels + total_meals + total_transportation
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

        # 返回增量更新。errors 和 execution_log 在 State 中使用 reducer 追加，
        # 这里不要返回完整 state，否则会把已有列表重复合并。
        return {
            "itinerary": fallback_plan.model_dump(),
            "budget": fallback_plan.budget.model_dump() if fallback_plan.budget else None,
            "status": "completed",
            "errors": ["注意：由于部分信息获取失败，已生成备用计划。建议出行前核实相关信息。"],
            "execution_log": [log_entry]
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
            "status": "failed",
            "errors": [error_msg],
            "execution_log": [log_entry]
        }


__all__ = ["error_handler_node", "create_fallback_plan"]
