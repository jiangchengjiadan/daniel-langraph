"""行程规划节点 - LangGraph Node实现"""

from langchain_openai import ChatOpenAI
from .. import TripPlanState
from ...models.schemas import TripPlan
from ...config import settings
import asyncio
import json
import os
import re
from typing import Dict, Optional, Any


# === Prompt模板 ===

PLANNER_PROMPT_TEMPLATE = """你是行程规划专家。你的任务是根据景点信息、天气信息和酒店信息,生成详细的旅行计划。

**基本信息**
- 城市：{city}
- 日期：{start_date} 至 {end_date}
- 天数：{travel_days}天
- 交通：{transportation}
- 住宿：{accommodation}
- 偏好：{preferences}
{free_text_input}

**景点信息**
{attractions}

**天气信息**
{weather}

**酒店信息**
{hotels}

**任务要求**
1. ⚠️ 必须生成完整的 {travel_days} 天行程计划，不能少于这个天数！
2. 每天安排2-3个景点
3. 每天包含早中晚三餐推荐
4. 推荐具体的酒店（从提供的酒店列表中选择）
5. 计算详细预算
6. 提供实用的旅行建议
7. 考虑天气情况调整行程

**JSON格式要求**
请严格按照以下JSON格式返回旅行计划:
```json
{{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述（注意：第一天的day_index必须是0，即start_date这一天对应day_index=0）",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {{
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {{"longitude": 116.397128, "latitude": 39.916527}},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      }},
      "attractions": [
        {{
          "name": "景点名称",
          "address": "详细地址",
          "location": {{"longitude": 116.397128, "latitude": 39.916527}},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }}
      ],
      "meals": [
        {{"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30}},
        {{"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50}},
        {{"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}}
      ]
    }}
  ],
  "weather_info": [
    {{
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }}
  ],
  "overall_suggestions": "总体建议",
  "budget": {{
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }}
}}
```

**重要提示**
1. ⚠️⚠️⚠️ days 数组必须包含完整的 {travel_days} 天行程，不能只生成部分天数！每一天都要包含！
2. ⚠️⚠️⚠️ day_index 必须从 0 开始！第一天(start_date)的 day_index = 0，第二天 day_index = 1，依此类推！
3. weather_info数组必须包含每一天的天气信息
4. 温度必须是纯数字(不要带°C等单位)
5. 每天必须包含早中晚三餐
6. 必须包含完整的预算信息
7. 返回的必须是有效的JSON,不要有任何其他文本
8. 酒店要从提供的列表中选择,如果列表为空则自行推荐
9. 景点要从提供的列表中选择,如果列表为空则自行推荐

请开始生成**完整 {travel_days} 天**的行程计划。
"""


# === 辅助函数 ===

def format_attractions_for_prompt(attractions: list) -> str:
    """将景点列表格式化为prompt文本"""
    if not attractions:
        return "（暂无景点信息，请根据城市自行推荐合适的景点）"

    lines = []
    for idx, attr in enumerate(attractions[:15], 1):  # 最多使用15个景点
        line = f"{idx}. {attr.get('name', '未知')} - {attr.get('address', '未知')}"
        if attr.get('type'):
            line += f" ({attr['type']})"
        lines.append(line)

    return "\n".join(lines)


def format_weather_for_prompt(weather_data: dict) -> str:
    """将天气数据格式化为prompt文本"""
    if not weather_data:
        return "（暂无天气信息）"

    lines = []

    # 实时天气
    if "live" in weather_data and weather_data["live"]:
        live = weather_data["live"]
        lines.append("实时天气：")
        lines.append(f"  天气：{live.get('weather', '未知')}")
        lines.append(f"  温度：{live.get('temperature', '未知')}")
        lines.append(f"  湿度：{live.get('humidity', '未知')}")
        lines.append("")

    # 天气预报
    if "forecasts" in weather_data and weather_data["forecasts"]:
        lines.append("天气预报：")
        for idx, cast in enumerate(weather_data["forecasts"][:7], 1):  # 最多7天
            lines.append(f"{idx}. {cast.get('date', '未知')} - {cast.get('day_weather', '未知')} {cast.get('day_temp', '?')} ~ {cast.get('night_temp', '?')}")

    return "\n".join(lines) if lines else "（暂无天气信息）"


def format_hotels_for_prompt(hotels: list) -> str:
    """将酒店列表格式化为prompt文本"""
    if not hotels:
        return "（暂无酒店信息，请根据城市自行推荐合适的酒店）"

    lines = []
    for idx, hotel in enumerate(hotels[:10], 1):  # 最多使用10个酒店
        line = f"{idx}. {hotel.get('name', '未知')} - {hotel.get('address', '未知')}"
        if hotel.get('rating'):
            line += f" (评分: {hotel['rating']})"
        lines.append(line)

    return "\n".join(lines)


def extract_json_from_llm_response(content: str) -> Optional[Dict[str, Any]]:
    """从LLM响应中提取JSON"""
    try:
        # 尝试直接解析
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取```json```代码块
    json_match = re.search(r'```json\s*\n([\s\S]*?)\n```', content)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取```代码块
    json_match = re.search(r'```\s*\n([\s\S]*?)\n```', content)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取大括号内容
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def parse_temperature(temp_str: str) -> Optional[int]:
    """解析温度字符串为整数"""
    if isinstance(temp_str, (int, float)):
        return int(temp_str)

    if isinstance(temp_str, str):
        # 移除°C等单位
        temp_str = temp_str.replace("°C", "").replace("°", "").replace("C", "").strip()
        try:
            return int(float(temp_str))
        except (ValueError, TypeError):
            pass

    return None


def normalize_trip_plan_data(data: Dict) -> Dict:
    """标准化行程计划数据"""
    # 处理温度字段
    if "weather_info" in data and isinstance(data["weather_info"], list):
        for weather in data["weather_info"]:
            if "day_temp" in weather:
                weather["day_temp"] = parse_temperature(weather["day_temp"])
            if "night_temp" in weather:
                weather["night_temp"] = parse_temperature(weather["night_temp"])

    # 修正 day_index：确保第一天是0，后续天数依次递增
    if "days" in data and isinstance(data["days"], list):
        for idx, day in enumerate(data["days"]):
            if "day_index" in day:
                # 强制修正为从0开始的连续索引
                day["day_index"] = idx
                print(f"✅ 修正第{idx + 1}天的day_index为: {idx}")

    return data


# === 节点函数 ===

async def itinerary_planning_node(state: TripPlanState) -> TripPlanState:
    """
    行程规划节点

    功能：根据收集的景点、天气、酒店信息生成完整的旅行计划

    Args:
        state: 当前状态，包含attractions、weather_data、hotels等

    Returns:
        更新后的状态，包含itinerary和budget
    """
    try:
        # 提取状态信息
        city = state.get("city", "")
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        travel_days = state.get("travel_days", 3)
        preferences = state.get("preferences", [])
        accommodation = state.get("accommodation", "")
        transportation = state.get("transportation", "")
        free_text_input = state.get("free_text_input", "")
        attractions = state.get("attractions", [])
        weather_data = state.get("weather_data", {})
        hotels = state.get("hotels", [])

        if not city:
            raise ValueError("城市信息缺失")

        # 格式化数据为prompt
        attractions_text = format_attractions_for_prompt(attractions)
        weather_text = format_weather_for_prompt(weather_data)
        hotels_text = format_hotels_for_prompt(hotels)

        # 构建完整prompt
        free_text_section = f"\n**额外需求**\n{free_text_input}" if free_text_input else ""

        prompt = PLANNER_PROMPT_TEMPLATE.format(
            city=city,
            start_date=start_date,
            end_date=end_date,
            travel_days=travel_days,
            preferences="、".join(preferences) if preferences else "无特殊偏好",
            accommodation=accommodation,
            transportation=transportation,
            free_text_input=free_text_section,
            attractions=attractions_text,
            weather=weather_text,
            hotels=hotels_text
        )

        # 创建LLM（不需要工具）
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or settings.openai_base_url
        model = os.getenv("LLM_MODEL_ID") or os.getenv("OPENAI_MODEL") or settings.openai_model
        llm_timeout = int(os.getenv("LLM_TIMEOUT", "60"))

        llm = ChatOpenAI(
            model=model,
            temperature=0.7,  # 稍高的temperature让计划更有创意
            api_key=api_key,
            base_url=base_url,
            request_timeout=llm_timeout
        )

        # 调用LLM生成计划
        print(f"📋 开始调用LLM生成最终行程: model={model}, timeout={llm_timeout}s", flush=True)
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=llm_timeout + 5)
        print("✅ LLM最终行程生成完成，开始提取JSON", flush=True)

        # 提取JSON
        itinerary_dict = extract_json_from_llm_response(response.content)

        if not itinerary_dict:
            raise ValueError("无法从LLM响应中提取有效的JSON")

        # 标准化数据
        print("🔧 开始标准化行程数据", flush=True)
        itinerary_dict = normalize_trip_plan_data(itinerary_dict)

        # 验证Pydantic模型
        print("🔍 开始校验TripPlan数据", flush=True)
        trip_plan = TripPlan(**itinerary_dict)
        print(f"✅ TripPlan数据校验通过: {len(trip_plan.days)}天", flush=True)

        # 构建执行日志
        log_entry = {
            "node": "itinerary_planning",
            "status": "success",
            "days": len(trip_plan.days),
            "total_budget": trip_plan.budget.total if trip_plan.budget else 0
        }

        # 返回更新后的状态（只返回更新的字段）
        return {
            "itinerary": trip_plan.model_dump(),
            "budget": trip_plan.budget.model_dump() if trip_plan.budget else None,
            "status": "completed",
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }

    except Exception as e:
        # 错误处理
        error_msg = f"行程规划失败: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 构建错误日志
        log_entry = {
            "node": "itinerary_planning",
            "status": "failed",
            "error": str(e)
        }

        # 返回带有错误信息的状态（只返回更新的字段）
        return {
            "itinerary": None,
            "budget": None,
            "status": "failed",
            "errors": [error_msg],  # 使用 Annotated，只返回新增项
            "execution_log": [log_entry]  # 使用 Annotated，只返回新增项
        }


__all__ = ["itinerary_planning_node"]
