"""LangGraph 状态定义"""

from typing import TypedDict, List, Dict, Optional, Annotated
from operator import add


class TripPlanState(TypedDict, total=False):
    """
    旅行规划的状态定义

    使用 TypedDict 提供类型安全的状态管理
    total=False 表示所有字段都是可选的，便于部分更新
    """

    # === 输入字段 ===
    city: str                        # 目的地城市
    start_date: str                  # 开始日期 (YYYY-MM-DD)
    end_date: str                    # 结束日期 (YYYY-MM-DD)
    travel_days: int                 # 旅行天数
    preferences: List[str]           # 偏好列表 (如: ["历史文化", "美食"])
    accommodation: str               # 住宿类型
    transportation: str              # 交通方式
    free_text_input: Optional[str]   # 额外需求

    # === Agent结果 (中间状态) ===
    attractions: List[Dict]          # 景点列表
    weather_data: Dict               # 天气信息
    hotels: List[Dict]               # 酒店列表

    # === 最终输出 ===
    itinerary: Optional[Dict]        # 完整行程计划 (TripPlan的字典形式)
    budget: Optional[Dict]           # 预算信息

    # === 元数据（使用 Annotated 支持并发追加）===
    errors: Annotated[List[str], add]                # 错误列表（并发追加）
    execution_log: Annotated[List[Dict], add]        # 执行日志（并发追加）
    status: str                      # 当前状态: processing/completed/failed
