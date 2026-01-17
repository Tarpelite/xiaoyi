"""
步骤定义模块
=============

定义各意图对应的步骤列表

步骤设计原则:
- 预测流程: 5-6 个阶段 (准备 → 数据获取 → 分析 → 预测 → 报告)
- 非预测流程: 2-4 个阶段 (准备 → 信息检索 → 回答生成)
- 纯对话: 1 个阶段
"""

from typing import List, Dict

# ========== 预测分析流程 (6步) ==========
# 阶段 1: 准备阶段 (意图识别 + 股票验证)
# 阶段 2: 股票验证 (当 stock_mention 非空时)
# 阶段 3: 数据获取 (并行: 历史数据 + 新闻 + 研报)
# 阶段 4: 分析处理 (并行: 特征分析 + 情绪分析)
# 阶段 5: 模型预测
# 阶段 6: 报告生成

FORECAST_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "股票验证"},
    {"id": "3", "name": "数据获取"},
    {"id": "4", "name": "分析处理"},
    {"id": "5", "name": "模型预测"},
    {"id": "6", "name": "报告生成"},
]

# ========== 非预测对话流程 (3-4步) ==========
# 阶段 1: 意图识别 + 关键词提取
# 阶段 2: 股票验证 (若 stock_mention 非空)
# 阶段 3: 信息检索 (并行: RAG + Search + Domain Info)
# 阶段 4: 回答生成

# 涉及股票的非预测流程 (4步)
CHAT_WITH_STOCK_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "股票验证"},
    {"id": "3", "name": "信息检索"},
    {"id": "4", "name": "生成回答"},
]

# 不涉及股票的非预测流程 (3步)
CHAT_WITHOUT_STOCK_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "信息检索"},
    {"id": "3", "name": "生成回答"},
]

# RAG 研报检索流程 (3步)
RAG_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "研报检索"},
    {"id": "3", "name": "生成回答"},
]

# 新闻搜索流程 (3步)
NEWS_STEPS = [
    {"id": "1", "name": "意图识别"},
    {"id": "2", "name": "新闻搜索"},
    {"id": "3", "name": "新闻总结"},
]

# ========== 纯对话流程 (1步) ==========
# 所有工具开关都是 false，直接生成回答

CHAT_STEPS = [
    {"id": "1", "name": "生成回答"},
]

# ========== 超出范围流程 (1步) ==========
OUT_OF_SCOPE_STEPS = [
    {"id": "1", "name": "意图识别"},
]


def get_steps_for_intent(intent: str, has_stock: bool = False) -> List[Dict[str, str]]:
    """
    根据意图获取对应的步骤列表

    Args:
        intent: 意图类型
            - forecast: 预测分析
            - rag: 研报检索
            - news: 新闻搜索
            - chat: 纯对话
            - out_of_scope: 超出范围
        has_stock: 是否涉及股票 (用于 chat 意图)

    Returns:
        步骤列表
    """
    if intent == "forecast":
        return FORECAST_STEPS
    elif intent == "rag":
        return RAG_STEPS
    elif intent == "news":
        return NEWS_STEPS
    elif intent == "out_of_scope":
        return OUT_OF_SCOPE_STEPS
    elif intent == "chat":
        # 根据是否涉及股票选择步骤
        if has_stock:
            return CHAT_WITH_STOCK_STEPS
        else:
            return CHAT_STEPS
    else:
        # 默认使用纯对话步骤
        return CHAT_STEPS


def get_step_count(intent: str, has_stock: bool = False) -> int:
    """
    获取意图对应的步骤数量

    Args:
        intent: 意图类型
        has_stock: 是否涉及股票

    Returns:
        步骤数量
    """
    return len(get_steps_for_intent(intent, has_stock))
