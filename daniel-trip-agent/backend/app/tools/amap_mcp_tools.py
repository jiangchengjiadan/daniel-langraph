"""高德地图 MCP 工具封装 - LangChain Tool 适配"""

from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import AsyncExitStack
from typing import Any, Dict, List

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import BaseModel, Field

from ..config import settings
from .amap_tools import (
    format_attractions_result,
    format_hotels_result,
    format_weather_result,
)


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


_mcp_client: MultiServerMCPClient | None = None
_mcp_tools_by_name: dict[str, Any] | None = None
_mcp_exit_stack: AsyncExitStack | None = None
_mcp_tools_lock = asyncio.Lock()
_mcp_call_lock = asyncio.Lock()


def _amap_mcp_api_key() -> str:
    """获取高德 MCP Server 需要的 API Key。"""
    return (
        os.getenv("AMAP_MAPS_API_KEY")
        or os.getenv("AMAP_API_KEY")
        or settings.amap_maps_api_key
        or settings.amap_api_key
        or ""
    )


def _mcp_connection_config() -> dict[str, dict[str, Any]]:
    """构建官方高德 MCP Server 的 stdio 连接配置。"""
    api_key = _amap_mcp_api_key()
    if not api_key:
        raise ValueError("高德地图API Key未配置，请设置 AMAP_MAPS_API_KEY 或 AMAP_API_KEY")

    return {
        "amap": {
            "transport": "stdio",
            "command": os.getenv("AMAP_MCP_COMMAND", "npx"),
            "args": [
                "-y",
                os.getenv("AMAP_MCP_PACKAGE", "@amap/amap-maps-mcp-server"),
            ],
            "env": {
                "AMAP_MAPS_API_KEY": api_key,
            },
        }
    }


async def _get_mcp_tools_by_name() -> dict[str, Any]:
    """延迟加载 MCP tools，避免应用启动时就拉起 npx 子进程。"""
    global _mcp_client, _mcp_tools_by_name, _mcp_exit_stack

    if _mcp_tools_by_name is not None:
        return _mcp_tools_by_name

    async with _mcp_tools_lock:
        if _mcp_tools_by_name is not None:
            return _mcp_tools_by_name

        _mcp_client = MultiServerMCPClient(_mcp_connection_config())
        _mcp_exit_stack = AsyncExitStack()
        session = await _mcp_exit_stack.enter_async_context(_mcp_client.session("amap"))
        tools = await load_mcp_tools(session)
        _mcp_tools_by_name = {tool.name: tool for tool in tools}
        print(f"✅ 高德 MCP 工具加载成功: {', '.join(_mcp_tools_by_name)}", flush=True)
        return _mcp_tools_by_name


async def _call_amap_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """调用指定高德 MCP tool。"""
    tools_by_name = await _get_mcp_tools_by_name()
    tool = tools_by_name.get(tool_name)

    if tool is None:
        available = ", ".join(sorted(tools_by_name))
        raise ValueError(f"高德 MCP 工具不存在: {tool_name}; 可用工具: {available}")

    timeout = int(os.getenv("AMAP_MCP_TIMEOUT", "30"))
    async with _mcp_call_lock:
        return await asyncio.wait_for(tool.ainvoke(arguments), timeout=timeout)


def _stringify_mcp_result(result: Any) -> str:
    """将 MCP tool 返回值归一化为字符串。"""
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        if result.get("type") == "text" and "text" in result:
            return str(result["text"])
        if "text" in result and len(result) <= 2:
            return str(result["text"])
        if "data" in result and len(result) <= 2:
            return _stringify_mcp_result(result["data"])
        return json.dumps(result, ensure_ascii=False)

    if hasattr(result, "content"):
        return _stringify_mcp_result(result.content)

    if isinstance(result, list):
        parts = []
        for item in result:
            if hasattr(item, "text"):
                parts.append(str(item.text))
            elif hasattr(item, "data"):
                parts.append(json.dumps(item.data, ensure_ascii=False))
            else:
                parts.append(_stringify_mcp_result(item))
        return "\n".join(part for part in parts if part)

    return str(result)


def _parse_json_from_text(text: str) -> Any:
    """从 MCP 返回文本中提取 JSON。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"```json\s*\n([\s\S]*?)\n```", text)
    if json_match:
        return json.loads(json_match.group(1))

    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if json_match:
        return json.loads(json_match.group(1))

    raise ValueError(f"无法解析高德 MCP 返回结果: {text[:200]}")


def _extract_pois(data: Any) -> list[dict[str, Any]]:
    """兼容高德 MCP text search 的常见返回结构。"""
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in ("pois", "POIs", "data", "results", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_pois(value)
            if nested:
                return nested

    return []


def _normalize_pois_for_formatter(pois: list[dict[str, Any]], city: str) -> list[dict[str, Any]]:
    """将高德 MCP POI 字段映射到现有 formatter 期望的 HTTP API 字段。"""
    normalized = []
    for poi in pois:
        item = dict(poi)
        item.setdefault("type", item.get("typecode", ""))
        item.setdefault("cityname", city)
        item.setdefault("adname", item.get("district", ""))
        item.setdefault("location", item.get("location", ""))
        normalized.append(item)
    return normalized


def _normalize_weather_data(data: Any) -> dict[str, Any]:
    """兼容高德 MCP weather 的常见返回结构。"""
    if not isinstance(data, dict):
        return {}

    if "casts" in data or "live" in data:
        return data

    if "forecasts" in data and isinstance(data["forecasts"], list):
        return {
            "city": data.get("city", ""),
            "reporttime": data.get("reporttime", ""),
            "casts": data["forecasts"],
        }

    for key in ("data", "result", "weather"):
        value = data.get(key)
        if isinstance(value, dict):
            normalized = _normalize_weather_data(value)
            if normalized:
                return normalized

    return data


@tool("amap_search_attractions", args_schema=AttractionSearchInput)
async def amap_search_attractions(keywords: str, city: str) -> str:
    """
    通过高德 MCP Server 搜索景点信息。

    内部调用官方高德 MCP 工具 maps_text_search，并将结果格式化为当前旅行规划节点使用的 JSON。
    """
    try:
        result = await _call_amap_mcp_tool("maps_text_search", {"keywords": keywords, "city": city})
        data = _parse_json_from_text(_stringify_mcp_result(result))
        pois = _normalize_pois_for_formatter(_extract_pois(data), city)
        return format_attractions_result(pois)
    except Exception as e:
        return json.dumps(
            {"错误": f"景点搜索失败: {str(e)}", "关键词": keywords, "城市": city},
            ensure_ascii=False,
        )


@tool("amap_query_weather", args_schema=WeatherQueryInput)
async def amap_query_weather(city: str) -> str:
    """
    通过高德 MCP Server 查询天气信息。

    内部调用官方高德 MCP 工具 maps_weather，并将结果格式化为当前旅行规划节点使用的 JSON。
    """
    try:
        result = await _call_amap_mcp_tool("maps_weather", {"city": city})
        data = _parse_json_from_text(_stringify_mcp_result(result))
        return format_weather_result(_normalize_weather_data(data))
    except Exception as e:
        return json.dumps({"错误": f"天气查询失败: {str(e)}", "城市": city}, ensure_ascii=False)


@tool("amap_search_hotels", args_schema=HotelSearchInput)
async def amap_search_hotels(keywords: str, city: str) -> str:
    """
    通过高德 MCP Server 搜索酒店信息。

    内部调用官方高德 MCP 工具 maps_text_search，并将结果格式化为当前旅行规划节点使用的 JSON。
    """
    try:
        result = await _call_amap_mcp_tool("maps_text_search", {"keywords": keywords, "city": city})
        data = _parse_json_from_text(_stringify_mcp_result(result))
        pois = _normalize_pois_for_formatter(_extract_pois(data), city)
        return format_hotels_result(pois)
    except Exception as e:
        return json.dumps(
            {"错误": f"酒店搜索失败: {str(e)}", "关键词": keywords, "城市": city},
            ensure_ascii=False,
        )


AMAP_TOOLS = [
    amap_search_attractions,
    amap_query_weather,
    amap_search_hotels,
]


__all__ = [
    "amap_search_attractions",
    "amap_query_weather",
    "amap_search_hotels",
    "AMAP_TOOLS",
]
