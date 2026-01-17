"""
Session 数据模型
================

定义统一的会话和消息数据结构

架构说明:
- Session: 一整个多轮对话，包含多个 Message
- Message: 一轮 QA，包含用户问题和助手回答
- UnifiedIntent: 统一意图识别结果，一次 LLM 调用返回所有信息
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


# ========== 枚举类型 ==========

class MessageStatus(str, Enum):
    """消息状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class StepStatus(str, Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


# ========== 基础数据类型 ==========

class TimeSeriesPoint(BaseModel):
    """时序数据点"""
    date: str
    value: float
    is_prediction: bool = False


class StockInfo(BaseModel):
    """股票信息 (股票 RAG 匹配结果)"""
    stock_code: str        # "600519"
    stock_name: str        # "贵州茅台"
    market: str            # "SH" | "SZ"


class RAGSource(BaseModel):
    """RAG 来源 (研报)"""
    filename: str          # "茅台2024研报.pdf"
    page: int              # 页码
    content_snippet: str   # 摘要片段
    score: float = 0.0     # 相关度分数


class SummarizedNewsItem(BaseModel):
    """LLM 总结后的新闻条目"""
    summarized_title: str       # LLM 总结的标题
    summarized_content: str     # LLM 总结的摘要
    original_title: str         # 原标题
    url: str                    # 来源链接
    published_date: str         # 格式化后的时间，如 "01-16 14:00"
    source_type: str            # "search" | "domain_info"
    source_name: str = ""       # 来源名称，如 "东方财富"、"新浪财经"


class ReportItem(BaseModel):
    """研报条目 (LLM 提取的观点)"""
    title: str                  # 研报标题
    viewpoint: str              # LLM 提取的观点
    source: RAGSource           # 来源信息


class StepDetail(BaseModel):
    """步骤详情"""
    id: str
    name: str
    status: StepStatus = StepStatus.PENDING
    message: str = ""


class ThinkingLogEntry(BaseModel):
    """思考日志条目 - 记录每个 LLM 调用的原始输出"""
    step_id: str                    # 步骤 ID，如 "intent", "sentiment", "report"
    step_name: str                  # 步骤名称，如 "意图识别", "情感分析", "报告生成"
    content: str                    # LLM 原始输出内容
    timestamp: str                  # ISO 格式时间戳


# ========== 意图识别相关 ==========

class UnifiedIntent(BaseModel):
    """
    统一意图识别结果

    一次 LLM 调用返回所有信息，包含:
    - 核心分支判断 (is_in_scope, is_forecast)
    - 工具开关 (enable_rag, enable_search, enable_domain_info)
    - 股票相关 (stock_mention)
    - 初步关键词 (raw_*_keywords，股票匹配后会被优化)
    - 预测参数 (仅 is_forecast=true 时使用)
    """
    # 核心分支判断
    is_in_scope: bool = Field(..., description="是否在服务范围内 (金融/股票相关)")
    is_forecast: bool = Field(default=False, description="是否需要预测")

    # 工具开关
    enable_rag: bool = Field(default=False, description="研报检索")
    enable_search: bool = Field(default=False, description="网络搜索 (Tavily)")
    enable_domain_info: bool = Field(default=False, description="领域信息 (AkShare news)")

    # 股票相关
    stock_mention: Optional[str] = Field(default=None, description="用户提到的股票名称/代码")
    stock_full_name: Optional[str] = Field(default=None, description="LLM 生成的股票官方全称 (如 '中石油' -> '中国石油')")

    # 初步关键词 (LLM 提取，股票匹配后会被优化)
    raw_search_keywords: List[str] = Field(default_factory=list)
    raw_rag_keywords: List[str] = Field(default_factory=list)
    raw_domain_keywords: List[str] = Field(default_factory=list)

    # 预测参数 (仅 is_forecast=true 时使用)
    forecast_model: str = Field(default="prophet")
    history_days: int = Field(default=365)
    forecast_horizon: int = Field(default=30)

    # 原因说明
    reason: str = Field(default="")

    # 超出范围时的友好回复
    out_of_scope_reply: Optional[str] = Field(default=None)


class ResolvedKeywords(BaseModel):
    """股票匹配后的最终关键词"""
    search_keywords: List[str] = Field(default_factory=list)
    rag_keywords: List[str] = Field(default_factory=list)
    domain_keywords: List[str] = Field(default_factory=list)


class StockMatchResult(BaseModel):
    """股票匹配结果"""
    success: bool
    stock_info: Optional[StockInfo] = None
    confidence: float = 0.0
    suggestions: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


# ========== 核心数据模型 ==========

class MessageData(BaseModel):
    """
    单轮 QA 数据 (Message)

    每轮对话的完整分析结果，独立存储于 Redis
    """
    # 基础信息
    message_id: str
    session_id: str
    created_at: str
    updated_at: str

    # 用户输入
    user_query: str = ""

    # 状态
    status: MessageStatus = MessageStatus.PENDING
    steps: int = 0
    total_steps: int = 0
    step_details: List[StepDetail] = Field(default_factory=list)

    # 意图识别
    intent: str = "pending"  # forecast/rag/news/chat/out_of_scope
    unified_intent: Optional[UnifiedIntent] = None

    # 股票匹配
    stock_match: Optional[StockMatchResult] = None
    resolved_keywords: Optional[ResolvedKeywords] = None

    # 时序数据 (仅预测)
    time_series_original: List[TimeSeriesPoint] = Field(default_factory=list)
    time_series_full: List[TimeSeriesPoint] = Field(default_factory=list)
    prediction_done: bool = False
    prediction_start_day: Optional[str] = None

    # 新闻和研报
    news_list: List[SummarizedNewsItem] = Field(default_factory=list)
    report_list: List[ReportItem] = Field(default_factory=list)
    rag_sources: List[RAGSource] = Field(default_factory=list)

    # 情感分析
    emotion: Optional[float] = None  # -1 到 1
    emotion_des: Optional[str] = None

    # 结论
    conclusion: str = ""
    error_message: Optional[str] = None

    # 思考日志 (累积显示所有 LLM 调用的原始输出)
    thinking_logs: List[ThinkingLogEntry] = Field(default_factory=list)


class SessionData(BaseModel):
    """
    会话数据 (Session) - 多轮对话容器

    存储全局信息和消息列表，每个消息的详细数据在 MessageData 中
    """
    # 基础信息
    session_id: str
    title: str = "New Chat"  # 会话标题，默认为首条消息摘要
    created_at: str
    updated_at: str

    # 全局配置
    context: str = ""
    model_name: Optional[str] = Field(default=None, description="使用的预测模型名称")

    # 消息管理
    message_ids: List[str] = Field(default_factory=list)
    current_message_id: Optional[str] = None

    # 对话历史 (文本形式，用于 LLM 上下文)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


# ========== API 请求/响应模型 ==========

class CreateAnalysisRequest(BaseModel):
    """创建分析任务请求"""
    message: str = Field(..., description="用户问题")
    session_id: str = Field(..., description="会话ID（必填，通过 POST /api/sessions 创建）")
    model: str = Field(default="prophet", description="预测模型")
    force_intent: Optional[str] = Field(default=None, description="强制指定意图")


class AnalysisStatusResponse(BaseModel):
    """分析状态响应"""
    session_id: str
    message_id: str
    status: MessageStatus
    steps: int
    total_steps: int = 0
    data: MessageData


# ========== 新闻相关模型 ==========

class NewsItem(BaseModel):
    """原始新闻条目 (合并前)"""
    title: str
    content: str
    url: str
    published_date: str     # 格式化后的时间，如 "01-16 14:00"
    source_type: str        # "search" | "domain_info"
    source_name: str = ""   # 来源名称，如 "东方财富"、"新浪财经"
    score: float = 0.0


class NewsSummaryResult(BaseModel):
    """新闻总结结果"""
    summary_text: str
    news_items: List[SummarizedNewsItem]
    total_before_dedup: int
    total_after_dedup: int


# ========== Backtest API Models ==========

class BacktestRequest(BaseModel):
    """
    回测请求模型

    用于交互式时间旅行回测功能
    """
    session_id: str = Field(description="会话ID")
    message_id: str = Field(description="消息ID")
    split_date: str = Field(description="分割点日期 (ISO格式: YYYY-MM-DD)")
    forecast_horizon: Optional[int] = Field(default=None, description="预测天数（可选，默认预测到原始数据末尾）")


class BacktestMetrics(BaseModel):
    """回测指标"""
    mae: float = Field(description="平均绝对误差 (Mean Absolute Error)")
    rmse: float = Field(description="均方根误差 (Root Mean Squared Error)")
    mape: float = Field(description="平均绝对百分比误差 (Mean Absolute Percentage Error)")
    calculation_time_ms: int = Field(description="计算耗时（毫秒）")


class BacktestResponse(BaseModel):
    """
    回测响应模型

    Returns:
        metrics: 预测误差指标
        backtest_data: 回测预测结果
        ground_truth: 实际历史数据（用于对比）
    """
    metrics: BacktestMetrics
    backtest_data: List[TimeSeriesPoint] = Field(description="回测预测结果")
    ground_truth: List[TimeSeriesPoint] = Field(description="实际历史数据")
    split_date: str = Field(description="分割点日期")
    split_index: int = Field(description="分割点索引")
