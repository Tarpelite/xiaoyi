"""
Report Agent 模块
=================

负责生成金融分析报告
"""

import json
from typing import Dict, Any, List, Optional
from openai import OpenAI


class ReportAgent:
    """分析报告生成 Agent"""

    def __init__(self, api_key: str):
        """
        初始化 Report Agent
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

    def generate(
        self,
        user_question: str,
        features: Dict[str, Any],
        forecast_result: Dict[str, Any],
        sentiment_result: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, str]:
        """
        生成分析报告内容

        Returns:
            Dict with 'content' (报告内容) and 'raw_response' (原始 LLM 输出)
        """
        # 提取预测数据
        forecast_summary = forecast_result.get("forecast", [])
        forecast_preview = forecast_summary[:7]
        
        # 1. 安全计算预测趋势（确保数值为 float）
        try:
            if len(forecast_summary) >= 7:
                start_val = float(forecast_summary[0]["value"])
                end_val_7d = float(forecast_summary[6]["value"])
                end_val_total = float(forecast_summary[-1]["value"])
                
                short_term_change = end_val_7d - start_val
                long_term_change = end_val_total - start_val
                
                st_pct = (short_term_change / start_val * 100) if start_val != 0 else 0
                lt_pct = (long_term_change / start_val * 100) if start_val != 0 else 0
            else:
                short_term_change = long_term_change = st_pct = lt_pct = 0
        except (ValueError, TypeError, KeyError):
            short_term_change = long_term_change = st_pct = lt_pct = 0
        
        # 2. 构建情绪分析块（以自然段形式描述，而非要点）
        # sentiment_result 可能是 dict 或对象
        sentiment_section = ""
        if sentiment_result:
            # 支持 dict 和对象两种格式
            if isinstance(sentiment_result, dict):
                score = float(sentiment_result.get("score", 0))
                description = sentiment_result.get("description", "")
            else:
                score = float(sentiment_result.score)
                description = sentiment_result.description
            
            # 根据分数判断情绪标签
            if score > 0.6:
                sentiment_label = "极度看涨"
            elif score > 0.3:
                sentiment_label = "偏乐观"
            elif score > -0.3:
                sentiment_label = "中性"
            elif score > -0.6:
                sentiment_label = "偏悲观"
            else:
                sentiment_label = "极度看跌"
            
            sentiment_section = f"""
## 市场情绪分析
整体市场情绪为**{sentiment_label}**，情绪得分为{score:.2f}（范围-1到1）。{description}
"""

        system_prompt = """你是资深的金融分析师。你的任务是生成自然段格式的分析报告，而非要点列表。

**核心要求：**
1. 使用自然段陈述，语气连贯流畅，避免使用"-"、"•"等列表符号
2. 将要点式内容改写为连贯的自然段落
3. 在关键数据、重要结论处使用 **加粗** 标记
4. 保持专业严谨，基于数据和技术指标
5. 逻辑清晰，层层递进
6. 明确风险点，给出实用建议"""

        # 3. 构建 Prompt (对 features 中的数值进行 float 强制转换)
        try:
            f_latest = float(features.get('latest', 0))
            f_mean = float(features.get('mean', 1)) # 避免除以0
            change_pct = (f_latest - f_mean) / f_mean * 100
            
            prompt = f"""用户问题: {user_question}

## 数据特征分析
数据时间范围为{features.get('date_range', '未知')}，共包含{features.get('data_points', 0)}个有效数据点。价格在{float(features.get('min', 0)):.2f}元至{float(features.get('max', 0)):.2f}元区间内波动，当前价位为**{f_latest:.2f}元**，略{'高于' if change_pct > 0 else '低于' if change_pct < 0 else '等于'}均值{f_mean:.2f}元（偏离幅度{abs(change_pct):.2f}%）。

从技术面来看，趋势方向为**{features.get('trend', '横盘')}**，波动程度为**{features.get('volatility', '低')}**，整体呈现出相对稳定的市场特征。

{sentiment_section}
## 预测结果
采用**{str(forecast_result.get('model', 'unknown')).upper()}模型**进行预测，模型的历史回测精度为MAE={float(forecast_result.get('metrics', {}).get('mae', 0)):.4f}，预测期限为{len(forecast_summary)}天。

根据预测结果，短期（7天）内预计变化为{short_term_change:+.2f}元（{st_pct:+.2f}%），长期（{len(forecast_summary)}天）累计变化为{long_term_change:+.2f}元（{lt_pct:+.2f}%）。

## 报告要求

**重要：请生成自然段格式的报告，不要使用要点列表。**

### 示例（Question + Case）

**问题：** 分析某股票下季度走势

**要点式报告（错误示例）：**
```
- 历史走势：价格在100-120区间波动
- 技术指标：趋势平稳，波动性低
- 预测结果：预计上涨5%
- 建议：谨慎乐观
```

**自然段报告（正确示例）：**
```
基于过去一年的数据分析，该股票呈现出**平稳偏弱的震荡格局**，价格在100-120元区间内波动，整体波动性较低，反映出市场情绪相对谨慎。从技术面来看，当前价位处于均值附近，趋势方向为横盘整理，这种低波动状态往往预示着市场正在寻找方向性突破。

根据Prophet模型的预测分析，预计未来90天该股票将呈现**温和上涨趋势**，累计涨幅约**5%**，目标价位在125-130元区间。这一预测基于模型的历史回测表现（MAE=2.5），具有一定的参考价值。然而，考虑到当前市场环境的不确定性，建议投资者采取**谨慎乐观**的态度，可以采取分批建仓的策略，在关键支撑位附近逐步布局，同时保留一定现金仓位以应对可能的回调风险。
```

### 你的任务

请基于上述数据，生成一份自然段格式的分析报告，包含以下内容（以自然段形式呈现，不要用列表）：
1. 历史走势与基本面分析（1-2段）
2. 市场情绪与技术面评估（1段）
3. 模型预测解读（1-2段）
4. 投资建议（1段）
5. 风险提示（1段）

**要求：**
- 总字数控制在600-800字
- 使用自然段陈述，语气连贯
- 关键数据和结论使用 **加粗** 标记
- 避免使用"-"、"•"、"1."等列表符号
"""
        except (ValueError, TypeError) as e:
            # 如果转换依然失败，回退到无格式模式
            prompt = f"数据分析请求: {user_question}\n数据详情: {str(features)}\n预测详情: {str(forecast_result)}"

        # 4. 消息发送
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history[-5:])
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.3,
            )
            raw_content = response.choices[0].message.content
            return {
                "content": raw_content,
                "raw_response": raw_content  # 报告内容即原始输出
            }
        except Exception as e:
            error_msg = f"生成报告时发生 API 错误: {str(e)}"
            return {
                "content": error_msg,
                "raw_response": error_msg
            }