"""高德地图工具封装 - LangChain Tool适配"""

from langchain_core.tools import tool
from pydantic import BaseModel,Field
from typing import List, Dict, Any
import json
from ..services.amap_service import AmapService


# === 工具输入模型 ===

class AttractionSearchInput(BaseModel):
    """景点搜索输入"""
    keywords: str = Field(..., description="搜索关键词，如'博物馆'、'公园'、'历史古迹'")
    city: str = Field(..., description="城市名称，如'北京'、'上海'")


class WeatherQueryInput(BaseModel):
    """天气查询输入"""
    city: str = Field(..., description="城市名称，如'北京'、'上海'")


class HotelSearchInput(BaseModel):
    """酒店搜索输入"""
    keywords: str = Field(default="酒店", description="搜索关键词，如'经济型酒店'、'五星级酒店'")
    city: str = Field(..., description="城市名称，如'北京'、'上海'")


# === 结果格式化函数 ===

def format_attractions_result(results: List[Dict[str, Any]]) -> str:
    """格式化景点搜索结果"""
    if not results:
        return "未找到相关景点"

    formatted_items = []
    for idx, item in enumerate(results[:10], 1):  # 最多返回10个
        formatted_item = {
            "序号": idx,
            "名称": item.get("name", "未知"),
            "类型": item.get("type", "未知"),
            "地址": item.get("address", "未知"),
            "坐标": item.get("location", "未知"),
            "城市": item.get("cityname", "未知"),
            "区域": item.get("adname", "未知")
        }

        # 添加评分和电话（如果有）
        if item.get("rating"):
            formatted_item["评分"] = item["rating"]
        if item.get("tel"):
            formatted_item["电话"] = item["tel"]

        formatted_items.append(formatted_item)

    return json.dumps({
        "总数": len(results),
        "返回数量": len(formatted_items),
        "景点列表": formatted_items
    }, ensure_ascii=False, indent=2)


def format_weather_result(weather_data: Dict[str, Any]) -> str:
    """格式化天气查询结果"""
    if not weather_data:
        return "未获取到天气信息"

    formatted = {
        "城市": weather_data.get("city", "未知"),
        "更新时间": weather_data.get("reporttime", "未知"),
        "天气预报": []
    }

    # 处理实时天气（如果有）
    if "live" in weather_data:
        live = weather_data["live"]
        formatted["实时天气"] = {
            "天气": live.get("weather", "未知"),
            "温度": f"{live.get('temperature', '未知')}°C",
            "风向": live.get("winddirection", "未知"),
            "风力": f"{live.get('windpower', '未知')}级",
            "湿度": f"{live.get('humidity', '未知')}%"
        }

    # 处理天气预报 - 适配新的 API 格式
    if "casts" in weather_data:
        # 新格式：直接在 weather_data 中
        for cast in weather_data["casts"]:
            formatted["天气预报"].append({
                "日期": cast.get("date", "未知"),
                "星期": cast.get("week", "未知"),
                "白天天气": cast.get("dayweather", "未知"),
                "夜间天气": cast.get("nightweather", "未知"),
                "白天温度": f"{cast.get('daytemp', '未知')}°C",
                "夜间温度": f"{cast.get('nighttemp', '未知')}°C",
                "白天风向": cast.get("daywind", "未知"),
                "夜间风向": cast.get("nightwind", "未知"),
                "白天风力": f"{cast.get('daypower', '未知')}级",
                "夜间风力": f"{cast.get('nightpower', '未知')}级"
            })
    elif "forecasts" in weather_data and weather_data["forecasts"]:
        # 旧格式：在 forecasts 数组中
        forecast = weather_data["forecasts"][0]
        if "casts" in forecast:
            for cast in forecast["casts"]:
                formatted["天气预报"].append({
                    "日期": cast.get("date", "未知"),
                    "星期": cast.get("week", "未知"),
                    "白天天气": cast.get("dayweather", "未知"),
                    "夜间天气": cast.get("nightweather", "未知"),
                    "白天温度": f"{cast.get('daytemp', '未知')}°C",
                    "夜间温度": f"{cast.get('nighttemp', '未知')}°C",
                    "白天风向": cast.get("daywind", "未知"),
                    "夜间风向": cast.get("nightwind", "未知"),
                    "白天风力": f"{cast.get('daypower', '未知')}级",
                    "夜间风力": f"{cast.get('nightpower', '未知')}级"
                })

    return json.dumps(formatted, ensure_ascii=False, indent=2)


def format_hotels_result(results: List[Dict[str, Any]]) -> str:
    """格式化酒店搜索结果"""
    if not results:
        return "未找到相关酒店"

    formatted_items = []
    for idx, item in enumerate(results[:10], 1):  # 最多返回10个
        formatted_item = {
            "序号": idx,
            "名称": item.get("name", "未知"),
            "类型": item.get("type", "未知"),
            "地址": item.get("address", "未知"),
            "坐标": item.get("location", "未知"),
            "城市": item.get("cityname", "未知"),
            "区域": item.get("adname", "未知")
        }

        # 添加评分和电话（如果有）
        if item.get("rating"):
            formatted_item["评分"] = item["rating"]
        if item.get("tel"):
            formatted_item["电话"] = item["tel"]
        if item.get("business_area"):
            formatted_item["商圈"] = item["business_area"]

        formatted_items.append(formatted_item)

    return json.dumps({
        "总数": len(results),
        "返回数量": len(formatted_items),
        "酒店列表": formatted_items
    }, ensure_ascii=False, indent=2)


# === LangChain Tool 定义 ===

@tool("amap_search_attractions", args_schema=AttractionSearchInput)
def amap_search_attractions(keywords: str, city: str) -> str:
    """
    使用高德地图搜索景点信息

    本工具可以搜索指定城市的各类景点，包括博物馆、公园、历史古迹、景区等。
    返回景点的详细信息，包括名称、地址、坐标、类型等。

    Args:
        keywords: 搜索关键词，如'博物馆'、'公园'、'历史古迹'
        city: 城市名称，如'北京'、'上海'

    Returns:
        JSON格式的景点列表，包含名称、地址、坐标等信息

    Examples:
        - amap_search_attractions(keywords="博物馆", city="北京")
        - amap_search_attractions(keywords="公园", city="上海")
    """
    try:
        service = AmapService()
        results = service.search_poi(keywords=keywords, city=city)
        return format_attractions_result(results)
    except Exception as e:
        return json.dumps({
            "错误": f"景点搜索失败: {str(e)}",
            "关键词": keywords,
            "城市": city
        }, ensure_ascii=False)


@tool("amap_query_weather", args_schema=WeatherQueryInput)
def amap_query_weather(city: str) -> str:
    """
    查询指定城市的天气信息

    本工具可以查询城市的实时天气和未来几天的天气预报。
    返回温度、天气状况、风向风力、湿度等详细信息。

    Args:
        city: 城市名称，如'北京'、'上海'

    Returns:
        JSON格式的天气信息，包含实时天气和天气预报

    Examples:
        - amap_query_weather(city="北京")
        - amap_query_weather(city="上海")
    """
    try:
        service = AmapService()
        weather_data = service.get_weather(city=city)
        return format_weather_result(weather_data)
    except Exception as e:
        return json.dumps({
            "错误": f"天气查询失败: {str(e)}",
            "城市": city
        }, ensure_ascii=False)


@tool("amap_search_hotels", args_schema=HotelSearchInput)
def amap_search_hotels(keywords: str, city: str) -> str:
    """
    使用高德地图搜索酒店信息

    本工具可以搜索指定城市的各类酒店，包括经济型、舒适型、高档型等。
    返回酒店的详细信息，包括名称、地址、坐标、评分等。

    Args:
        keywords: 搜索关键词，如'经济型酒店'、'五星级酒店'，默认为'酒店'
        city: 城市名称，如'北京'、'上海'

    Returns:
        JSON格式的酒店列表，包含名称、地址、评分等信息

    Examples:
        - amap_search_hotels(keywords="经济型酒店", city="北京")
        - amap_search_hotels(keywords="酒店", city="上海")
    """
    try:
        service = AmapService()
        results = service.search_poi(keywords=keywords, city=city)
        return format_hotels_result(results)
    except Exception as e:
        return json.dumps({
            "错误": f"酒店搜索失败: {str(e)}",
            "关键词": keywords,
            "城市": city
        }, ensure_ascii=False)


# === 工具列表导出 ===

AMAP_TOOLS = [
    amap_search_attractions,
    amap_query_weather,
    amap_search_hotels
]


__all__ = [
    "amap_search_attractions",
    "amap_query_weather",
    "amap_search_hotels",
    "AMAP_TOOLS"
]
