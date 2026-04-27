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


def _is_masked_price_text(value: Any) -> bool:
    """识别 1**、2xx 等被脱敏或不完整的价格文本。"""
    if not isinstance(value, str):
        return False

    normalized = value.strip().lower().replace(",", "")
    if not normalized:
        return False

    return bool(re.search(r"\d[\d.,]*\s*[*xX]+", normalized))


def _parse_price(value: Any) -> int | None:
    """从 '¥123起'、'123' 等价格文本中提取整数。"""
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    if _is_masked_price_text(value):
        return None

    match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    return int(float(match.group(0)))


def _clean_poi_keyword(name: str) -> str:
    """减少 FlyAI search-poi 返回过宽结果导致的大响应。"""
    name = re.sub(r"[（(].*?[）)]", "", name or "")
    name = re.sub(r"\s+", " ", name).strip()
    return name[:30]


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

    max_attempts = 2
    last_error: str | None = None
    safe_params = {key: value for key, value in params.items() if value not in (None, "")}

    print(f"🔎 FlyAI调用开始: {command}, params={safe_params}", flush=True)

    for attempt in range(1, max_attempts + 1):
        print(f"🔁 FlyAI调用尝试: {command} 第{attempt}/{max_attempts}次", flush=True)
        result, retryable_error = await _run_flyai_once(prefix, args, command, attempt, max_attempts)
        if result is not None:
            print(f"✅ FlyAI调用成功: {command}, items={len(result)}", flush=True)
            return result

        last_error = retryable_error
        if attempt < max_attempts:
            print(f"↩️ FlyAI准备重试: {command}, reason={retryable_error}", flush=True)
            await asyncio.sleep(0.5 * attempt)

    print(f"ℹ️ FlyAI增强跳过: {command} 连续{max_attempts}次未返回可用数据 ({last_error})", flush=True)
    return []


async def _run_flyai_once(
    prefix: list[str],
    args: list[str],
    command: str,
    attempt: int,
    max_attempts: int,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """执行一次 FlyAI CLI。返回 None 表示可重试失败。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *prefix,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.flyai_timeout)

        if stderr:
            print(f"⚠️ FlyAI stderr: {stderr.decode(errors='replace')[:500]}", flush=True)

        if proc.returncode != 0:
            return None, f"returncode={proc.returncode}"

        payload_text = stdout.decode("utf-8", errors="replace").strip()
        try:
            payload = json.loads(payload_text or "{}")
        except json.JSONDecodeError as exc:
            print(f"ℹ️ FlyAI返回非完整JSON: {command} 第{attempt}/{max_attempts}次 ({exc})", flush=True)
            return None, f"invalid json: {exc}"
        if payload.get("status") not in (0, "0", None):
            return None, f"status={payload.get('status')}, message={payload.get('message')}"

        items = payload.get("data", {}).get("itemList", [])
        return (items if isinstance(items, list) else []), None
    except asyncio.TimeoutError:
        return None, "timeout"
    except Exception as exc:
        return None, str(exc)


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
        price_text = item.get("price", "")
        price = _parse_price(price_text)
        products.append(
            {
                "name": item.get("name", ""),
                "address": item.get("address", ""),
                "price": price,
                "price_text": price_text,
                "price_valid": price is not None,
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
                "keyword": _clean_poi_keyword(name),
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
