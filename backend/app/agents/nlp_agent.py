"""
NLP Agent 模块
==============

负责将用户自然语言输入解析为结构化的数据配置
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any
from openai import OpenAI


# AKShare API 文档说明
AKSHARE_API_DOCS = """
## AKShare 数据接口

### 股票数据
- stock_zh_a_hist: A股历史行情
  参数: symbol(代码), period(daily/weekly/monthly), start_date, end_date, adjust(qfq/hfq/"")
  
### 指数数据  
- stock_zh_index_daily_em: 指数历史数据
  参数: symbol (sh000001=上证, sz399001=深证, sz399006=创业板)

### 常用代码
- 平安银行: 000001, 贵州茅台: 600519, 比亚迪: 002594
- 上证指数: sh000001, 沪深300: sh000300
"""


class NLPAgent:
    """自然语言解析 Agent"""
    
    def __init__(self, api_key: str):
        """
        初始化 NLP Agent
        
        Args:
            api_key: DeepSeek API Key
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def parse(self, user_query: str) -> Dict[str, Any]:
        """
        解析用户输入，返回数据配置和分析配置
        
        Args:
            user_query: 用户自然语言输入
            
        Returns:
            包含 data_config 和 analysis_config 的字典
        """
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)
        
        system_prompt = f"""你是金融数据助手。将用户需求转换为 AKShare 数据获取配置。

{AKSHARE_API_DOCS}

返回 JSON 格式:
{{
    "data_config": {{
        "api_function": "stock_zh_a_hist",
        "params": {{"symbol": "000001", "period": "daily", "start_date": "YYYYMMDD", "end_date": "YYYYMMDD", "adjust": ""}},
        "data_type": "stock",
        "target_column": "收盘"
    }},
    "analysis_config": {{
        "forecast_horizon": 30,
        "model": "prophet",
        "user_question": "用户问题的核心"
    }}
}}

注意:
- 默认获取最近1年数据
- 日期格式 YYYYMMDD
- 今天: {today.strftime('%Y-%m-%d')}
- 一年前: {one_year_ago.strftime('%Y-%m-%d')}
- model 字段固定返回 "prophet"（实际模型选择由外部参数控制）
- 只返回 JSON
"""
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
