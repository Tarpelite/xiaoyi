from typing import Dict, Any
from pydantic import BaseModel, model_validator
from app.core.config import settings

class AgentConfig(BaseModel):
    """Configuration for a specific Agent"""
    
    # 基础模型配置
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.3
    max_tokens: int = 2000
    
    # 上下文窗口配置
    history_window: int = 6

class AgentsSettings(BaseModel):
    """All Agents Configuration Manager"""
    
    # 默认全局配置
    default: AgentConfig = AgentConfig()
    
    # agent具体配置
    # 意图识别 Agent
    intent: AgentConfig = AgentConfig(
        temperature=0.1,
        max_tokens=1000,
        model="deepseek-chat"
    )
    
    # 报告生成 Agent
    report: AgentConfig = AgentConfig(
        temperature=0.3, 
        max_tokens=3000,
        history_window=5
    )
    
    # 新闻总结 Agent
    news_summary: AgentConfig = AgentConfig(
        temperature=0.1,
        max_tokens=1500
    )
    
    # 建议生成 Agent:
    suggestion: AgentConfig = AgentConfig(
        temperature=0.5,
        max_tokens=500
    )
    
    # 情感分析 Agent
    sentiment: AgentConfig = AgentConfig(
        temperature=0.1,
        max_tokens=500
    )

    # 错误解释 Agent
    error_explainer: AgentConfig = AgentConfig(
        temperature=0.3,
        max_tokens=1000
    )

    # 事件总结 Agent
    event_summary: AgentConfig = AgentConfig(
        temperature=0.2,
        max_tokens=1000
    )


# 全局单例
agent_settings = AgentsSettings()