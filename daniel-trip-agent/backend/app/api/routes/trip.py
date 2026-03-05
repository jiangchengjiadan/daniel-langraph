"""旅行规划API路由"""

import os
from fastapi import APIRouter, HTTPException
from ...models.schemas import (
    TripRequest,
    TripPlanResponse,
    ErrorResponse
)
import logging

logger = logging.getLogger(__name__)

# 环境变量控制：是否使用 LangGraph 实现（默认使用）
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() == "true"

# 根据环境变量选择实现
if USE_LANGGRAPH:
    logger.info("🔧 使用 LangGraph 实现")
    from ...agents.langgraph_planner import get_langgraph_trip_planner

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
async def plan_trip(request: TripRequest):
    """
    生成旅行计划

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"📥 收到旅行规划请求:")
        logger.info(f"   城市: {request.city}")
        logger.info(f"   日期: {request.start_date} - {request.end_date}")
        logger.info(f"   天数: {request.travel_days}")
        logger.info(f"   实现方式: {'LangGraph' if USE_LANGGRAPH else 'HelloAgents'}")
        logger.info(f"{'='*60}\n")

        # 根据环境变量选择实现
        if USE_LANGGRAPH:
            # 使用 LangGraph 实现
            logger.info("🔄 获取 LangGraph 规划器实例...")
            planner = get_langgraph_trip_planner()

            logger.info("🚀 使用 LangGraph 生成旅行计划...")
            trip_plan = await planner.plan_trip(request)

        logger.info("✅ 旅行计划生成成功,准备返回响应\n")

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except Exception as e:
        logger.error(f"❌ 生成旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        # 根据环境变量选择实现进行健康检查
        if USE_LANGGRAPH:
            planner = get_langgraph_trip_planner()
            return {
                "status": "healthy",
                "service": "trip-planner",
                "implementation": "LangGraph",
                "version": "2.0"
            }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )

