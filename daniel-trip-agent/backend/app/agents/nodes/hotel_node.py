"""酒店搜索节点 - LangGraph Node实现"""

from .. import TripPlanState
from ...tools.amap_mcp_tools import amap_search_hotels
import asyncio
import json
from typing import Dict, List, Any


# === Prompt模板 ===

HOTEL_SEARCH_PROMPT = """你是酒店搜索专家，负责根据用户的住宿需求搜索合适的酒店。

**用户信息**
- 目的地城市：{city}
- 住宿类型：{accommodation}
- 旅行天数：{travel_days}天

**任务要求**
1. 必须使用 amap_search_hotels 工具搜索酒店
2. 根据住宿类型选择合适的搜索关键词：
   - "经济型酒店" → "快捷酒店"、"酒店"
   - "舒适型酒店" → "商务酒店"、"酒店"
   - "高档型酒店" → "星级酒店"、"酒店"
   - "民宿客栈" → "民宿"、"客栈"、"酒店"
3. 至少搜索 5 家不同的酒店
4. 确保酒店位置分布合理，方便游览主要景点
5. 返回的酒店应包含地址、评分、联系方式等信息

请开始搜索酒店，并总结搜索结果。
"""


# === 辅助函数 ===

def get_hotel_keywords(accommodation: str) -> List[str]:
    """根据住宿类型获取搜索关键词"""
    accommodation_to_keywords = {
        "经济型酒店": ["快捷酒店", "酒店"],
        "舒适型酒店": ["商务酒店", "酒店"],
        "高档型酒店": ["五星级酒店", "豪华酒店", "星级酒店"],
        "豪华酒店": ["五星级酒店", "豪华酒店", "高端酒店"],
        "五星级酒店": ["五星级酒店", "豪华酒店"],
        "民宿客栈": ["民宿", "客栈", "酒店"],
        "民宿": ["民宿", "客栈"],
    }

    # 尝试精确匹配
    if accommodation in accommodation_to_keywords:
        return accommodation_to_keywords[accommodation]

    # 尝试模糊匹配
    for key, keywords in accommodation_to_keywords.items():
        if key in accommodation or accommodation in key:
            return keywords

    # 默认返回通用关键词
    return ["酒店", "宾馆"]


def hotel_matches_accommodation(hotel: Dict[str, Any], accommodation: str) -> bool:
    """过滤明显不符合住宿偏好的酒店。"""
    name = hotel.get("名称", "")
    hotel_type = hotel.get("类型", "")
    text = f"{name} {hotel_type}"

    budget_words = ["青年", "青旅", "旅舍", "客栈", "民宿", "公寓", "招待所"]
    luxury_words = ["五星", "豪华", "高端", "国际", "大酒店", "酒店", "度假", "万豪", "希尔顿", "洲际", "凯悦", "香格里拉", "丽思", "威斯汀"]

    if accommodation in {"豪华酒店", "高档型酒店", "五星级酒店"}:
        if any(word in text for word in budget_words):
            return False
        return any(word in text for word in luxury_words)

    if accommodation in {"民宿", "民宿客栈"}:
        return any(word in text for word in ["民宿", "客栈", "公寓", "旅舍"])

    return True


def dedupe_and_filter_hotels(hotels: List[Dict[str, Any]], accommodation: str) -> List[Dict[str, Any]]:
    """按名称去重，并按住宿偏好过滤。"""
    seen_names = set()
    filtered = []
    for hotel in hotels:
        name = hotel.get("名称", "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        if hotel_matches_accommodation(hotel, accommodation):
            filtered.append(hotel)

    return filtered


def format_hotel_for_state(hotel: Dict) -> Dict[str, Any]:
    """将酒店格式化为状态中的标准格式"""
    return {
        "name": hotel.get("名称", ""),
        "type": hotel.get("类型", ""),
        "address": hotel.get("地址", ""),
        "location": hotel.get("坐标", ""),
        "city": hotel.get("城市", ""),
        "district": hotel.get("区域", ""),
        "rating": hotel.get("评分"),
        "phone": hotel.get("电话"),
        "business_area": hotel.get("商圈"),
    }


# === 节点函数 ===

async def hotel_search_node(state: TripPlanState) -> TripPlanState:
    """
    酒店搜索节点

    功能：根据用户的住宿需求搜索合适的酒店

    Args:
        state: 当前状态，包含city和accommodation

    Returns:
        更新后的状态，包含hotels列表
    """
    try:
        # 提取状态信息
        city = state.get("city", "")
        accommodation = state.get("accommodation", "酒店")
        travel_days = state.get("travel_days", 3)

        if not city:
            raise ValueError("城市信息缺失")

        # 教学版：直接调用高德 MCP 工具，避免采集阶段再引入一个 LLM 工具循环。
        keywords = list(dict.fromkeys(get_hotel_keywords(accommodation)))[:3]
        results = await asyncio.gather(
            *[
                amap_search_hotels.ainvoke({"keywords": keyword, "city": city})
                for keyword in keywords
            ]
        )

        hotels_raw = []
        for content in results:
            try:
                data = json.loads(content)
                hotels_raw.extend(data.get("酒店列表", []))
            except json.JSONDecodeError:
                continue

        hotels_raw = dedupe_and_filter_hotels(hotels_raw, accommodation)

        # 格式化为标准格式
        hotels = [format_hotel_for_state(hotel) for hotel in hotels_raw]

        # 构建执行日志
        log_entry = {
            "node": "hotel_search",
            "status": "success",
            "count": len(hotels),
            "accommodation": accommodation,
            "city": city
        }

        # 返回更新后的状态（只返回更新的字段）
        return {
            "hotels": hotels,
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }

    except Exception as e:
        # 错误处理
        error_msg = f"酒店搜索失败: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 构建错误日志
        log_entry = {
            "node": "hotel_search",
            "status": "failed",
            "error": str(e),
            "city": state.get("city", ""),
            "accommodation": state.get("accommodation", "")
        }

        # 返回带有错误信息的状态（只返回更新的字段）
        return {
            "hotels": [],
            "errors": [error_msg],  # 使用 Annotated，只返回新增项
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }


__all__ = ["hotel_search_node"]
