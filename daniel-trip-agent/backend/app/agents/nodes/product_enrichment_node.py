"""商品数据回填节点。"""

from __future__ import annotations

import copy
import re
from typing import Any

from .. import TripPlanState


def _norm_name(value: str) -> str:
    """简化名称用于商品匹配。"""
    value = re.sub(r"[（(].*?[）)]", "", value or "")
    value = re.sub(r"\s+", "", value)
    for suffix in ("景区", "风景区", "旅游区", "酒店", "大酒店"):
        value = value.replace(suffix, "")
    return value.lower()


def _match_product(name: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = _norm_name(name)
    if not target:
        return None

    for product in products:
        product_name = _norm_name(product.get("name", ""))
        if product_name and product_name == target:
            return product

    for product in products:
        product_name = _norm_name(product.get("name", ""))
        if product_name and (target in product_name or product_name in target):
            return product

    return None


def _best_hotel_product(hotel: dict[str, Any] | None, products: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not products:
        return None
    if hotel:
        matched = _match_product(hotel.get("name", ""), products)
        if matched:
            return matched
    return products[0]


def _hotel_price_is_valid(product: dict[str, Any]) -> bool:
    """只有通过解析校验的 FlyAI 酒店价格才覆盖原始预算。"""
    return bool(product.get("price_valid")) and product.get("price") is not None


def _recalculate_budget(itinerary: dict[str, Any]) -> None:
    days = itinerary.get("days", []) or []
    total_attractions = 0
    total_hotels = 0
    total_meals = 0

    for day in days:
        for attraction in day.get("attractions", []) or []:
            total_attractions += int(attraction.get("ticket_price") or 0)
        hotel = day.get("hotel")
        if hotel:
            total_hotels += int(hotel.get("estimated_cost") or 0)
        for meal in day.get("meals", []) or []:
            total_meals += int(meal.get("estimated_cost") or 0)

    budget = itinerary.get("budget") or {}
    total_transportation = int(budget.get("total_transportation") or len(days) * 100)
    budget.update(
        {
            "total_attractions": total_attractions,
            "total_hotels": total_hotels,
            "total_meals": total_meals,
            "total_transportation": total_transportation,
            "total": total_attractions + total_hotels + total_meals + total_transportation,
        }
    )
    itinerary["budget"] = budget


def product_enrichment_node(state: TripPlanState) -> TripPlanState:
    """用 FlyAI 商品数据回填行程中的图片、价格和预订链接。"""
    itinerary = state.get("itinerary")
    if not itinerary:
        return {
            "execution_log": [
                {
                    "node": "product_enrichment",
                    "status": "skipped",
                    "reason": "no_itinerary",
                }
            ]
        }

    enriched = copy.deepcopy(itinerary)
    hotel_products = state.get("hotel_products", []) or []
    ticket_products = state.get("ticket_products", []) or []
    hotel_updates = 0
    ticket_updates = 0

    for day in enriched.get("days", []) or []:
        hotel = day.get("hotel")
        product = _best_hotel_product(hotel, hotel_products)
        if hotel and product:
            price_is_valid = _hotel_price_is_valid(product)
            price = product.get("price") if price_is_valid else None
            hotel.update(
                {
                    "name": product.get("name") or hotel.get("name", ""),
                    "address": product.get("address") or hotel.get("address", ""),
                    "price_range": product.get("price_text") if price_is_valid else hotel.get("price_range", ""),
                    "rating": str(product.get("score") or hotel.get("rating", "")),
                    "type": product.get("star") or hotel.get("type", ""),
                    "estimated_cost": int(price or hotel.get("estimated_cost") or 0),
                    "image_url": product.get("image_url") or hotel.get("image_url"),
                    "booking_url": product.get("booking_url") or hotel.get("booking_url"),
                    "source": product.get("source") or hotel.get("source"),
                }
            )
            hotel_updates += 1

        for attraction in day.get("attractions", []) or []:
            product = _match_product(attraction.get("name", ""), ticket_products)
            if not product:
                continue

            ticket_price = product.get("ticket_price")
            if ticket_price is not None:
                attraction["ticket_price"] = int(ticket_price)
            if product.get("image_url"):
                attraction["image_url"] = product["image_url"]
            if product.get("booking_url"):
                attraction["booking_url"] = product["booking_url"]
            attraction["source"] = product.get("source") or attraction.get("source")
            ticket_updates += 1

    _recalculate_budget(enriched)

    return {
        "itinerary": enriched,
        "budget": enriched.get("budget"),
        "execution_log": [
            {
                "node": "product_enrichment",
                "status": "success",
                "hotel_updates": hotel_updates,
                "ticket_updates": ticket_updates,
            }
        ],
    }


__all__ = ["product_enrichment_node"]
