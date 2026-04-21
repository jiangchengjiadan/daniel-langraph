"""LangGraph 实现基本验证脚本"""

import sys
import os
from app.agents import TripPlanState
# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """测试所有模块导入"""
    print("=" * 60)
    print("测试1: 检查模块导入")
    print("=" * 60)

    try:
        print("✓ 导入 state 模块...")
        from app.agents import TripPlanState
        print("  - TripPlanState 导入成功")

        print("✓ 导入 tools 模块...")
        from app.tools.amap_mcp_tools import (
            amap_search_attractions,
            amap_query_weather,
            amap_search_hotels,
            AMAP_TOOLS
        )
        print(f"  - 3个工具导入成功: {len(AMAP_TOOLS)} 个工具")

        print("✓ 导入 nodes 模块...")
        from app.agents.nodes import (
            attraction_search_node,
            weather_query_node,
            hotel_search_node,
            itinerary_planning_node,
            error_handler_node
        )
        print("  - 5个节点函数导入成功")

        print("✓ 导入 langgraph_planner 模块...")
        from app.agents.langgraph_planner import (
            LangGraphTripPlanner,
            get_langgraph_trip_planner
        )
        print("  - LangGraphTripPlanner 导入成功")

        print("\n✅ 所有模块导入成功!\n")
        return True

    except Exception as e:
        print(f"\n❌ 导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_planner_initialization():
    """测试规划器初始化"""
    print("=" * 60)
    print("测试2: 规划器初始化")
    print("=" * 60)

    try:
        from app.agents.langgraph_planner import get_langgraph_trip_planner

        print("✓ 初始化 LangGraph 规划器...")
        planner = get_langgraph_trip_planner()
        print("  - 规划器实例创建成功")
        print(f"  - 类型: {type(planner).__name__}")

        # 检查图是否编译成功
        if hasattr(planner, 'app') and planner.app:
            print("  - StateGraph 编译成功")

        print("\n✅ 规划器初始化成功!\n")
        return True

    except Exception as e:
        print(f"\n❌ 初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_state_structure():
    """测试状态结构"""
    print("=" * 60)
    print("测试3: 状态结构验证")
    print("=" * 60)

    try:
        from app.agents.state import TripPlanState

        # 创建测试状态
        test_state: TripPlanState = {
            "city": "北京",
            "start_date": "2025-06-01",
            "end_date": "2025-06-03",
            "travel_days": 3,
            "preferences": ["历史文化"],
            "accommodation": "经济型酒店",
            "transportation": "公共交通",
            "free_text_input": None,
            "attractions": [],
            "weather_data": {},
            "hotels": [],
            "itinerary": None,
            "budget": None,
            "errors": [],
            "execution_log": [],
            "status": "processing"
        }

        print("✓ 测试状态创建成功")
        print(f"  - 城市: {test_state['city']}")
        print(f"  - 天数: {test_state['travel_days']}")
        print(f"  - 偏好: {test_state['preferences']}")

        print("\n✅ 状态结构验证成功!\n")
        return True

    except Exception as e:
        print(f"\n❌ 状态验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("LangGraph 实现基本验证")
    print("=" * 60 + "\n")

    results = []

    # 测试1: 模块导入
    results.append(("模块导入", test_imports()))

    # 测试2: 规划器初始化
    results.append(("规划器初始化", test_planner_initialization()))

    # 测试3: 状态结构
    results.append(("状态结构", test_state_structure()))

    # 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请检查错误信息")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
