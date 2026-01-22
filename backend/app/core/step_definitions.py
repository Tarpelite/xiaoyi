"""
步骤定义模块
=============

定义各意图对应的步骤列表

步骤设计原则:
- 预测流程: 6 个阶段
- 非预测流程: 3-4 个阶段（根据是否有股票）
- 超出范围: 1 个阶段
"""

from typing import List, Dict

# 预测分析流程 (6步)
FORECAST_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "股票验证"},
    {"id": "3", "name": "数据获取"},
    {"id": "4", "name": "分析处理"},
    {"id": "5", "name": "模型预测"},
    {"id": "6", "name": "报告生成"},
]

# 非预测流程 - 有股票 (4步)
CHAT_WITH_STOCK_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "股票验证"},
    {"id": "3", "name": "信息检索"},
    {"id": "4", "name": "生成回答"},
]

# 非预测流程 - 无股票 (3步)
CHAT_WITHOUT_STOCK_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "信息检索"},
    {"id": "3", "name": "生成回答"},
]

# 超出范围流程 (1步)
OUT_OF_SCOPE_STEPS = [
    {"id": "1", "name": "意图识别"},
]


def get_steps_for_intent(is_forecast: bool, is_in_scope: bool, has_stock: bool) -> List[Dict[str, str]]:
    """
    根据意图获取对应的步骤列表

    Args:
        is_forecast: 是否为预测任务
        is_in_scope: 是否在服务范围内
        has_stock: 是否涉及股票

    Returns:
        步骤列表
    """
    if not is_in_scope:
        return OUT_OF_SCOPE_STEPS
    elif is_forecast:
        return FORECAST_STEPS
    elif has_stock:
        return CHAT_WITH_STOCK_STEPS
    else:
        return CHAT_WITHOUT_STOCK_STEPS


def get_step_count(is_forecast: bool, is_in_scope: bool, has_stock: bool) -> int:
    """
    获取意图对应的步骤数量

    Args:
        is_forecast: 是否为预测任务
        is_in_scope: 是否在服务范围内
        has_stock: 是否涉及股票

    Returns:
        步骤数量
    """
    return len(get_steps_for_intent(is_forecast, is_in_scope, has_stock))
