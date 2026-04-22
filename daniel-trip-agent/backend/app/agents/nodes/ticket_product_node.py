"""FlyAI 景点门票商品搜索节点。"""

from .. import TripPlanState
from ...tools.flyai_tools import search_ticket_products


async def ticket_product_search_node(state: TripPlanState) -> TripPlanState:
    """根据高德 MCP 搜到的景点名称查询门票商品。"""
    city = state.get("city", "")
    attractions = state.get("attractions", []) or []
    attraction_names = [item.get("name", "") for item in attractions if item.get("name")]

    try:
        products = await search_ticket_products(city=city, attraction_names=attraction_names)
        return {
            "ticket_products": products,
            "execution_log": [
                {
                    "node": "ticket_product_search",
                    "status": "success",
                    "count": len(products),
                }
            ],
        }
    except Exception as exc:
        error_msg = f"门票商品搜索失败: {exc}"
        print(f"[ERROR] {error_msg}", flush=True)
        return {
            "ticket_products": [],
            "errors": [error_msg],
            "execution_log": [
                {
                    "node": "ticket_product_search",
                    "status": "failed",
                    "error": str(exc),
                }
            ],
        }


__all__ = ["ticket_product_search_node"]
