"""FlyAI 酒店商品搜索节点。"""

from .. import TripPlanState
from ...tools.flyai_tools import search_hotel_products


async def hotel_product_search_node(state: TripPlanState) -> TripPlanState:
    """查询酒店商品价格、图片和预订链接。"""
    city = state.get("city", "")
    accommodation = state.get("accommodation", "")
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")

    try:
        products = await search_hotel_products(
            city=city,
            accommodation=accommodation,
            check_in=start_date,
            check_out=end_date,
        )
        return {
            "hotel_products": products,
            "execution_log": [
                {
                    "node": "hotel_product_search",
                    "status": "success",
                    "count": len(products),
                }
            ],
        }
    except Exception as exc:
        error_msg = f"酒店商品搜索失败: {exc}"
        print(f"[ERROR] {error_msg}", flush=True)
        return {
            "hotel_products": [],
            "errors": [error_msg],
            "execution_log": [
                {
                    "node": "hotel_product_search",
                    "status": "failed",
                    "error": str(exc),
                }
            ],
        }


__all__ = ["hotel_product_search_node"]
