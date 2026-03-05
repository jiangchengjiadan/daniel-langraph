"""天气查询节点 - LangGraph Node实现"""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from .. import TripPlanState
from ...tools.amap_tools import amap_query_weather
from ...config import settings
import json
import re
from typing import Dict, Any


# === Prompt模板 ===

WEATHER_QUERY_PROMPT = """你是天气查询专家，负责查询目的地城市的天气信息。

**查询信息**
- 目的地城市：{city}
- 出行日期：{start_date} 至 {end_date}

**任务要求**
1. 必须使用 amap_query_weather 工具查询天气
2. 获取该城市的实时天气和未来几天的天气预报
3. 总结天气情况，包括温度范围、天气状况、是否适合出行

请开始查询天气信息。
"""


# === 辅助函数 ===

def parse_weather_from_agent_output(agent_result: Dict) -> Dict[str, Any]:
    """从Agent输出中解析天气信息"""
    weather_data = {}

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
                            # 如果找到天气数据就返回
                            if "城市" in data or "实时天气" in data or "天气预报" in data:
                                weather_data = data
                                break
                    except json.JSONDecodeError:
                        continue
                # 也尝试从普通消息中提取JSON
                elif hasattr(message, "content"):
                    content = str(message.content)
                    # 尝试提取JSON块
                    json_match = re.search(r'\{[\s\S]*"城市"[\s\S]*\}', content)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                            if "城市" in data or "实时天气" in data:
                                weather_data = data
                                break
                        except json.JSONDecodeError:
                            continue

    except Exception as e:
        print(f"解析天气结果时出错: {str(e)}")

    return weather_data


def format_weather_for_state(weather_data: Dict) -> Dict[str, Any]:
    """将天气数据格式化为状态中的标准格式"""
    formatted = {
        "city": weather_data.get("城市", ""),
        "update_time": weather_data.get("更新时间", ""),
        "live": {},
        "forecasts": []
    }

    # 处理实时天气
    if "实时天气" in weather_data:
        live = weather_data["实时天气"]
        formatted["live"] = {
            "weather": live.get("天气", ""),
            "temperature": live.get("温度", ""),
            "wind_direction": live.get("风向", ""),
            "wind_power": live.get("风力", ""),
            "humidity": live.get("湿度", "")
        }

    # 处理天气预报
    if "天气预报" in weather_data and isinstance(weather_data["天气预报"], list):
        for cast in weather_data["天气预报"]:
            formatted["forecasts"].append({
                "date": cast.get("日期", ""),
                "week": cast.get("星期", ""),
                "day_weather": cast.get("白天天气", ""),
                "night_weather": cast.get("夜间天气", ""),
                "day_temp": cast.get("白天温度", ""),
                "night_temp": cast.get("夜间温度", ""),
                "day_wind": cast.get("白天风向", ""),
                "night_wind": cast.get("夜间风向", ""),
                "day_power": cast.get("白天风力", ""),
                "night_power": cast.get("夜间风力", "")
            })

    return formatted


# === 节点函数 ===

async def weather_query_node(state: TripPlanState) -> TripPlanState:
    """
    天气查询节点

    功能：查询目的地城市的天气信息

    Args:
        state: 当前状态，包含city、start_date、end_date

    Returns:
        更新后的状态，包含weather_data
    """
    try:
        # 提取状态信息
        city = state.get("city", "")
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")

        if not city:
            raise ValueError("城市信息缺失")

        # 构建prompt
        prompt = WEATHER_QUERY_PROMPT.format(
            city=city,
            start_date=start_date,
            end_date=end_date
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
        tools = [amap_query_weather]
        agent = create_agent(llm, tools)

        # 执行Agent
        result = await agent.ainvoke({
            "messages": [("user", prompt)]
        })

        # 解析天气结果
        weather_raw = parse_weather_from_agent_output(result)

        # 格式化为标准格式
        weather_data = format_weather_for_state(weather_raw) if weather_raw else {}

        # 构建执行日志
        log_entry = {
            "node": "weather_query",
            "status": "success",
            "city": city,
            "has_live": bool(weather_data.get("live")),
            "forecast_days": len(weather_data.get("forecasts", []))
        }

        # 返回更新后的状态（只返回更新的字段）
        return {
            "weather_data": weather_data,
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }

    except Exception as e:
        # 错误处理
        error_msg = f"天气查询失败: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 构建错误日志
        log_entry = {
            "node": "weather_query",
            "status": "failed",
            "error": str(e),
            "city": state.get("city", "")
        }

        # 返回带有错误信息的状态（只返回更新的字段）
        return {
            "weather_data": {},
            "errors": [error_msg],  # 使用 Annotated，只返回新增项
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }


__all__ = ["weather_query_node"]
