"""景点搜索节点 - LangGraph Node实现"""

from langchain_openai import ChatOpenAI
from .. import TripPlanState
from ...tools.amap_mcp_tools import amap_search_attractions
from ...config import settings
import asyncio
import json
import re
from typing import Dict, List, Any


# === Prompt模板 ===

ATTRACTION_SEARCH_PROMPT = """你是景点搜索专家，负责根据用户的旅行偏好搜索合适的景点。

**用户信息**
- 目的地城市：{city}
- 旅行偏好：{preferences}
- 旅行天数：{travel_days}天

**任务要求**
1. 必须使用 amap_search_attractions 工具搜索景点
2. 根据用户偏好选择合适的搜索关键词（如"历史文化"→"博物馆"、"古迹"）
3. 至少搜索 {min_attractions} 个不同类型的景点
4. 确保景点类型多样化，不要只搜索一个类别
5. 返回的景点应该适合 {travel_days} 天的行程安排

**搜索策略**
- 如果偏好是"历史文化"，搜索：博物馆、古迹、历史景点
- 如果偏好是"自然风光"，搜索：公园、山、景区、风景名胜
- 如果偏好是"美食"，搜索：餐馆、小吃店、特色美食
- 如果偏好是"购物"，搜索：购物、百货、商业街
- 如果偏好是"娱乐"，搜索：游乐场、娱乐场所、剧院

请开始搜索景点，并总结搜索结果。
"""


# === 辅助函数 ===

def extract_keywords_from_preferences(preferences: List[str]) -> List[str]:
    """从偏好中提取搜索关键词"""
    preference_to_keywords = {
        "历史文化": ["博物馆", "古迹", "历史景点"],
        "自然风光": ["公园", "山", "景区", "风景名胜"],
        "美食": ["餐馆", "小吃店", "特色美食"],
        "购物": ["购物", "百货", "商业街"],
        "娱乐": ["游乐场", "娱乐场所", "剧院"],
        "艺术": ["美术馆", "艺术馆", "画廊"],
        "宗教": ["寺庙", "教堂", "清真寺"],
        "现代建筑": ["地标", "建筑", "摩天大楼"],
    }

    keywords = []
    for pref in preferences:
        if pref in preference_to_keywords:
            keywords.extend(preference_to_keywords[pref])

    # 如果没有匹配的偏好，使用通用关键词
    if not keywords:
        keywords = ["景点", "旅游景点"]

    return keywords


def parse_attractions_from_agent_output(agent_result: Dict) -> List[Dict[str, Any]]:
    """从Agent输出中解析景点列表"""
    attractions = []

    try:
        # 从agent的messages中提取工具调用结果
        if "messages" in agent_result:
            for message in agent_result["messages"]:
                # 检查是否是工具消息
                if hasattr(message, "type") and message.type == "tool":
                    try:
                        # 解析工具返回的JSON
                        content = message.content
                        if isinstance(content, str):
                            data = json.loads(content)
                            if "景点列表" in data:
                                attractions.extend(data["景点列表"])
                    except json.JSONDecodeError:
                        continue
                # 也尝试从普通消息中提取JSON
                elif hasattr(message, "content"):
                    content = str(message.content)
                    # 尝试提取JSON块
                    json_match = re.search(r'\{[\s\S]*"景点列表"[\s\S]*\}', content)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                            if "景点列表" in data:
                                attractions.extend(data["景点列表"])
                        except json.JSONDecodeError:
                            continue

    except Exception as e:
        print(f"解析景点结果时出错: {str(e)}")

    # 去重（基于名称）
    seen_names = set()
    unique_attractions = []
    for attr in attractions:
        name = attr.get("名称", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_attractions.append(attr)

    return unique_attractions


def format_attraction_for_state(attraction: Dict) -> Dict[str, Any]:
    """将景点格式化为状态中的标准格式"""
    return {
        "name": attraction.get("名称", ""),
        "type": attraction.get("类型", ""),
        "address": attraction.get("地址", ""),
        "location": attraction.get("坐标", ""),
        "city": attraction.get("城市", ""),
        "district": attraction.get("区域", ""),
        "rating": attraction.get("评分"),
        "phone": attraction.get("电话"),
    }


# === 节点函数 ===

async def attraction_search_node(state: TripPlanState) -> TripPlanState:
    """
    景点搜索节点

    功能：根据用户的城市和偏好搜索合适的景点

    Args:
        state: 当前状态，包含city和preferences

    Returns:
        更新后的状态，包含attractions列表
    """
    try:
        # 提取状态信息
        city = state.get("city", "")
        preferences = state.get("preferences", [])
        travel_days = state.get("travel_days", 3)

        if not city:
            raise ValueError("城市信息缺失")

        # 教学版：直接调用高德 MCP 工具，避免采集阶段再引入一个 LLM 工具循环。
        keywords = list(dict.fromkeys(extract_keywords_from_preferences(preferences)))[:6]
        results = await asyncio.gather(
            *[
                amap_search_attractions.ainvoke({"keywords": keyword, "city": city})
                for keyword in keywords
            ]
        )

        attractions_raw = []
        for content in results:
            try:
                data = json.loads(content)
                attractions_raw.extend(data.get("景点列表", []))
            except json.JSONDecodeError:
                continue

        # 格式化为标准格式
        attractions = [format_attraction_for_state(attr) for attr in attractions_raw]

        # 构建执行日志
        log_entry = {
            "node": "attraction_search",
            "status": "success",
            "count": len(attractions),
            "preferences": preferences,
            "city": city
        }

        # 返回更新后的状态（只返回更新的字段，不返回整个state）
        return {
            "attractions": attractions,
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }

    except Exception as e:
        # 错误处理
        error_msg = f"景点搜索失败: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 构建错误日志
        log_entry = {
            "node": "attraction_search",
            "status": "failed",
            "error": str(e),
            "city": state.get("city", ""),
            "preferences": state.get("preferences", [])
        }

        # 返回带有错误信息的状态（只返回更新的字段）
        return {
            "attractions": [],
            "errors": [error_msg],  # 使用 Annotated，只返回新增项
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }


__all__ = ["attraction_search_node"]
