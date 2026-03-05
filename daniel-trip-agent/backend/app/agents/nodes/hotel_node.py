"""酒店搜索节点 - LangGraph Node实现"""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from .. import TripPlanState
from ...tools.amap_tools import amap_search_hotels
from ...config import settings
import json
import re
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
        "高档型酒店": ["星级酒店", "酒店"],
        "民宿客栈": ["民宿", "客栈", "酒店"],
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


def parse_hotels_from_agent_output(agent_result: Dict) -> List[Dict[str, Any]]:
    """从Agent输出中解析酒店列表"""
    hotels = []

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
                            if "酒店列表" in data:
                                hotels.extend(data["酒店列表"])
                    except json.JSONDecodeError:
                        continue
                # 也尝试从普通消息中提取JSON
                elif hasattr(message, "content"):
                    content = str(message.content)
                    # 尝试提取JSON块
                    json_match = re.search(r'\{[\s\S]*"酒店列表"[\s\S]*\}', content)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                            if "酒店列表" in data:
                                hotels.extend(data["酒店列表"])
                        except json.JSONDecodeError:
                            continue

    except Exception as e:
        print(f"解析酒店结果时出错: {str(e)}")

    # 去重（基于名称）
    seen_names = set()
    unique_hotels = []
    for hotel in hotels:
        name = hotel.get("名称", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_hotels.append(hotel)

    return unique_hotels


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

        # 构建prompt
        prompt = HOTEL_SEARCH_PROMPT.format(
            city=city,
            accommodation=accommodation,
            travel_days=travel_days
        )

        # 创建LLM
        import os
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or settings.openai_base_url
        model = os.getenv("LLM_MODEL_ID") or os.getenv("OPENAI_MODEL") or settings.openai_model

        llm = ChatOpenAI(
            model=model,
            temperature=0,
            api_key=api_key,
            base_url=base_url
        )

        # 创建ReAct Agent
        tools = [amap_search_hotels]
        agent = create_agent(llm, tools)

        # 执行Agent
        result = await agent.ainvoke({
            "messages": [("user", prompt)]
        })

        # 解析酒店结果
        hotels_raw = parse_hotels_from_agent_output(result)

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
