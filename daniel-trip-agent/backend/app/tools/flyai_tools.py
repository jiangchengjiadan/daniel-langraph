"""FlyAI/飞猪商品搜索工具封装。

FlyAI 当前公开接入方式是 @fly-ai/flyai-cli。这里把 CLI 输出归一化为
项目内部结构，作为高德 MCP 的商品增强数据源。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from ..config import settings


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _local_flyai_bundle() -> Path | None:
    """查找项目内安装的 @fly-ai/flyai-cli bundle。"""
    candidates = [
        _repo_root() / "frontend" / "node_modules" / "@fly-ai" / "flyai-cli" / "dist" / "flyai-bundle.cjs",
        _repo_root() / "node_modules" / "@fly-ai" / "flyai-cli" / "dist" / "flyai-bundle.cjs",
        _repo_root() / "backend" / "node_modules" / "@fly-ai" / "flyai-cli" / "dist" / "flyai-bundle.cjs",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _flyai_command_prefix() -> list[str] | None:
    """返回可执行的 FlyAI 命令前缀。"""
    configured = os.getenv("FLYAI_CLI") or settings.flyai_cli
    if configured:
        configured_path = Path(configured)
        if configured_path.suffix == ".cjs" or configured_path.exists():
            return ["node", str(configured_path)]
        if shutil.which(configured):
            return [configured]

    local_bundle = _local_flyai_bundle()
    if local_bundle:
        return ["node", str(local_bundle)]

    return None


def _parse_price(value: Any) -> int | None:
    """从 '¥123起'、'123' 等价格文本中提取整数。"""
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None

    match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    return int(float(match.group(0)))


async def _run_flyai(command: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """执行 FlyAI CLI 并返回 itemList。"""
    if not settings.enable_flyai:
        return []

    prefix = _flyai_command_prefix()
    if not prefix:
        print("⚠️ FlyAI CLI 未安装，跳过商品增强", flush=True)
        return []

    args = [command]
    for key, value in params.items():
        if value is None or value == "":
            continue
        args.extend([f"--{key}", str(value)])

    try:
        proc = await asyncio.create_subprocess_exec(
            *prefix,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.flyai_timeout)

        if stderr:
            print(f"⚠️ FlyAI stderr: {stderr.decode(errors='ignore')[:500]}", flush=True)

        if proc.returncode != 0:
            print(f"⚠️ FlyAI命令失败: {command}, returncode={proc.returncode}", flush=True)
            return []

        payload = json.loads(stdout.decode().strip() or "{}")
        if payload.get("status") not in (0, "0", None):
            print(f"⚠️ FlyAI返回异常: {payload.get('message')}", flush=True)
            return []

        items = payload.get("data", {}).get("itemList", [])
        return items if isinstance(items, list) else []
    except asyncio.TimeoutError:
        print(f"⚠️ FlyAI命令超时: {command}", flush=True)
        return []
    except Exception as exc:
        print(f"⚠️ FlyAI调用失败: {command}: {exc}", flush=True)
        return []


def _hotel_star_for_accommodation(accommodation: str) -> str | None:
    if accommodation in {"豪华酒店", "高档型酒店", "五星级酒店"}:
        return "5"
    if accommodation in {"舒适型酒店", "商务酒店"}:
        return "4"
    return None


async def search_hotel_products(
    city: str,
    accommodation: str,
    check_in: str,
    check_out: str,
) -> list[dict[str, Any]]:
    """搜索酒店商品，并归一化为内部结构。"""
    params = {
        "dest-name": city,
        "key-words": accommodation,
        "check-in-date": check_in,
        "check-out-date": check_out,
        "hotel-stars": _hotel_star_for_accommodation(accommodation),
        "sort": "rate_desc",
    }

    items = await _run_flyai("search-hotels", params)
    products = []
    for item in items:
        price = _parse_price(item.get("price"))
        products.append(
            {
                "name": item.get("name", ""),
                "address": item.get("address", ""),
                "price": price,
                "price_text": item.get("price", ""),
                "score": item.get("score", ""),
                "score_desc": item.get("scoreDesc", ""),
                "star": item.get("star", ""),
                "brand_name": item.get("brandName", ""),
                "image_url": item.get("mainPic"),
                "booking_url": item.get("detailUrl"),
                "source": "flyai",
                "raw": item,
            }
        )
    return [product for product in products if product["name"]]


async def search_ticket_products(city: str, attraction_names: list[str]) -> list[dict[str, Any]]:
    """按景点名称搜索门票商品。"""
    products = []
    seen_names = set()

    for name in attraction_names[:12]:
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        items = await _run_flyai(
            "search-poi",
            {
                "city-name": city,
                "keyword": name,
            },
        )
        for item in items[:3]:
            ticket_info = item.get("ticketInfo") or {}
            price = _parse_price(ticket_info.get("price"))
            free_status = item.get("freePoiStatus")
            if price is None and free_status == "FREE":
                price = 0

            products.append(
                {
                    "name": item.get("name", ""),
                    "address": item.get("address", ""),
                    "category": item.get("category", ""),
                    "ticket_price": price,
                    "ticket_name": ticket_info.get("ticketName", ""),
                    "image_url": item.get("mainPic"),
                    "booking_url": item.get("jumpUrl"),
                    "free_status": free_status,
                    "source": "flyai",
                    "query": name,
                    "raw": item,
                }
            )

    return [product for product in products if product["name"]]


__all__ = ["search_hotel_products", "search_ticket_products"]
