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
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ========== 枚举类型 ==========

class SessionStatus(str, Enum):
    """会话状态"""
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


class WebSource(BaseModel):
    """网页来源"""
    title: str
    url: str
    source_type: str       # "search" | "domain_info"


class SummarizedNewsItem(BaseModel):
    """LLM 总结后的新闻条目"""
    # LLM 生成的内容 (非原始标题/摘要)
    summarized_title: str       # LLM 总结的标题 (简洁、突出要点)
    summarized_content: str     # LLM 总结的摘要 (1-2句话)

    # 原始信息 (保留用于溯源)
    original_title: str         # 原标题
    url: str                    # 来源链接 (可点击)
    published_date: str
    source_type: str            # "search" | "domain_info"


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
    is_forecast: bool = Field(default=False, description="是否需要预测 (决定走预测流程还是对话流程)")

    # 工具开关 (对话和预测都可能开启)
    enable_rag: bool = Field(default=False, description="研报检索")
    enable_search: bool = Field(default=False, description="网络搜索 (Tavily)")
    enable_domain_info: bool = Field(default=False, description="领域信息 (AkShare news)")

    # 股票相关 (可能为空，支持多股票用逗号分隔)
    stock_mention: Optional[str] = Field(default=None, description="用户提到的股票名称/代码")

    # 初步关键词 (LLM 提取，股票匹配后会被优化)
    raw_search_keywords: List[str] = Field(default_factory=list, description="初步搜索关键词")
    raw_rag_keywords: List[str] = Field(default_factory=list, description="初步研报关键词")
    raw_domain_keywords: List[str] = Field(default_factory=list, description="初步领域关键词")

    # 预测参数 (仅 is_forecast=true 时使用)
    forecast_model: str = Field(default="prophet", description="预测模型")
    history_days: int = Field(default=365, description="历史数据天数")
    forecast_horizon: int = Field(default=30, description="预测天数")

    # 原因说明
    reason: str = Field(default="", description="意图判断原因")

    # 超出范围时的友好回复 (若 is_in_scope=false)
    out_of_scope_reply: Optional[str] = Field(default=None, description="超出范围时的友好回复")


class ResolvedKeywords(BaseModel):
    """
    股票匹配后的最终关键词

    在股票验证阶段生成，将 raw_*_keywords 中的股票简称替换为全称/代码
    """
    search_keywords: List[str] = Field(default_factory=list, description="最终搜索关键词")
    rag_keywords: List[str] = Field(default_factory=list, description="最终研报关键词")
    domain_keywords: List[str] = Field(default_factory=list, description="最终领域关键词")


class StockMatchResult(BaseModel):
    """股票匹配结果"""
    success: bool                       # 是否匹配成功
    stock_info: Optional[StockInfo] = None  # 匹配到的股票信息
    confidence: float = 0.0             # 匹配置信度
    suggestions: List[str] = Field(default_factory=list)  # 模糊匹配时的建议
    error_message: Optional[str] = None # 错误信息 (如已退市)


# ========== Message 数据模型 ==========

class Message(BaseModel):
    """
    一轮 QA 对话

    字段解释方式由 is_forecast 决定:
    - is_forecast=false: conclusion 是连贯的 Markdown 段落，链接内嵌
    - is_forecast=true: conclusion + 结构化数据 (news_items, time_series, emotion 等)
    """
    message_id: str
    session_id: str
    created_at: datetime

    # 用户输入
    user_query: str

    # 意图识别结果
    intent: UnifiedIntent

    # 股票匹配结果 (若 stock_mention 非空)
    stock_match: Optional[StockMatchResult] = None

    # 最终关键词 (股票匹配后)
    resolved_keywords: Optional[ResolvedKeywords] = None

    # 核心标志位 (决定字段解释方式)
    is_forecast: bool = False

    # 统一的响应字段
    conclusion: str = ""  # 主要回答 (Markdown 格式，含内嵌链接)

    # === 以下字段仅 is_forecast=true 时有值 ===

    # 新闻列表 (预测流程展示给用户)
    news_items: Optional[List[SummarizedNewsItem]] = None

    # 研报观点 (预测流程展示给用户)
    report_items: Optional[List[ReportItem]] = None

    # 预测数据
    time_series_original: Optional[List[TimeSeriesPoint]] = None  # 历史数据
    time_series_predicted: Optional[List[TimeSeriesPoint]] = None  # 预测数据

    # 情感分析
    emotion_score: Optional[float] = Field(default=None, ge=-1, le=1)  # -1 到 1
    emotion_summary: Optional[str] = None  # 情感描述

    # 股票信息 (预测时必有)
    stock_info: Optional[StockInfo] = None

    # 模型信息
    model_used: Optional[str] = None      # prophet/xgboost/...
    model_config: Optional[Dict[str, Any]] = None  # 模型参数

    # 步骤状态 (用于前端展示进度)
    step_details: List[StepDetail] = Field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0

    # 状态
    status: SessionStatus = SessionStatus.PENDING
    error_message: Optional[str] = None


# ========== Session 数据模型 ==========

class Session(BaseModel):
    """
    多轮对话会话

    一个 Session 包含多个 Message，每个 Message 是一轮 QA
    """
    session_id: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus = SessionStatus.PENDING

    # 所有消息列表 (按 created_at 排序)
    messages: List[Message] = Field(default_factory=list)

    # 当前正在处理的消息 ID (用于轮询)
    current_message_id: Optional[str] = None

    # 上下文信息 (可选)
    context: str = ""

    # 错误信息
    error_message: Optional[str] = None


# ========== 兼容旧版 AnalysisSession ==========

class AnalysisSession(BaseModel):
    """
    分析会话完整数据模型 (兼容旧版)

    注意: 新代码应使用 Session + Message 模型
    此模型保留用于兼容现有 API
    """
    # 基础信息
    session_id: str
    context: str = ""
    steps: int = 0
    status: SessionStatus = SessionStatus.PENDING
    is_time_series: bool = True

    # 意图相关
    intent: str = "pending"  # pending/forecast/rag/news/chat
    intent_result: Optional[Dict[str, Any]] = None  # 改为 Dict 以兼容新旧格式

    # 动态步骤
    total_steps: int = 0
    step_details: List[StepDetail] = Field(default_factory=list)

    # 时序数据
    time_series_original: List[TimeSeriesPoint] = Field(default_factory=list)
    time_series_full: List[TimeSeriesPoint] = Field(default_factory=list)
    prediction_done: bool = False
    prediction_start_day: Optional[str] = None

    # 新闻和研报
    news_list: List[Dict[str, Any]] = Field(default_factory=list)  # 兼容新旧格式
    report_list: List[Dict[str, Any]] = Field(default_factory=list)
    rag_sources: List[RAGSource] = Field(default_factory=list)
    emotion: Optional[float] = None
    emotion_des: Optional[str] = None

    # 综合报告
    conclusion: str = ""

    # 对话历史
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    # 元数据
    created_at: str
    updated_at: str
    error_message: Optional[str] = None

    # 额外配置
    stock_code: Optional[str] = None
    model_name: str = "prophet"

    # === 新增字段 (用于统一架构) ===

    # 统一意图 (新版)
    unified_intent: Optional[UnifiedIntent] = None

    # 股票匹配结果
    stock_match: Optional[StockMatchResult] = None

    # 最终关键词
    resolved_keywords: Optional[ResolvedKeywords] = None

    # 是否预测流程
    is_forecast: bool = False


# ========== API 请求/响应模型 ==========

class CreateAnalysisRequest(BaseModel):
    """创建分析任务请求"""
    message: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(default=None, description="会话ID，多轮对话时复用")
    model: str = Field(default="prophet", description="预测模型")
    context: str = Field(default="", description="上下文")
    force_intent: Optional[str] = Field(default=None, description="强制指定意图")


class AnalysisStatusResponse(BaseModel):
    """分析状态响应"""
    session_id: str
    message_id: Optional[str] = None  # 新增: 当前消息 ID
    status: SessionStatus
    steps: int
    total_steps: int = 0
    data: AnalysisSession


# ========== 新闻相关模型 ==========

class NewsItem(BaseModel):
    """原始新闻条目 (合并前)"""
    title: str
    content: str
    url: str
    published_date: str
    source_type: str        # "search" | "domain_info"
    score: float = 0.0      # 相关度分数


class NewsSummaryResult(BaseModel):
    """新闻总结结果"""
    # 方式 A: 连贯段落 (用于情感分析输入)
    summary_text: str

    # 方式 B: 总结后的新闻列表 (展示给用户)
    news_items: List[SummarizedNewsItem]

    # 元信息
    total_before_dedup: int  # 去重前数量
    total_after_dedup: int   # 去重后数量
