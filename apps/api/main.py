"""
FastAPI 后端 - 金融数据对话式分析
==================================

基于 finance_agent.py 实现，提供 SSE 流式响应接口
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入 finance_agent 模块
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "notebooks"))
from finance_agent import (
    FinanceChatAgent, 
    DataFetcher, 
    TimeSeriesAnalyzer,
    NLPAgent,
    ReportGenerator
)

app = FastAPI(title="小易猜猜 API", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ============================================================
# 数据模型
# ============================================================

class ChatRequest(BaseModel):
    message: str

# 步骤定义
STEPS = [
    {"id": "1", "name": "数据获取与预处理"},
    {"id": "2", "name": "时序特征分析"},
    {"id": "3", "name": "异常检测"},
    {"id": "4", "name": "模型训练与评估"},
    {"id": "5", "name": "预测生成"},
    {"id": "6", "name": "结果可视化"},
    {"id": "7", "name": "分析完成"},
]

# ============================================================
# 数据格式转换函数
# ============================================================

def format_sse(event_type: str, data: Any) -> str:
    """格式化 SSE 消息"""
    if isinstance(data, dict):
        payload = {'type': event_type, **data}
    else:
        payload = {'type': event_type, 'data': data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def df_to_table(df, title: str = "历史时序数据", limit: int = 20) -> Dict[str, Any]:
    """将 DataFrame 转换为表格格式"""
    import pandas as pd
    
    # 获取最近 N 条数据
    recent_df = df.tail(limit).copy()
    
    # 检测列名
    date_col = "ds" if "ds" in recent_df.columns else "日期"
    value_col = "y" if "y" in recent_df.columns else "收盘"
    
    headers = ["日期", "收盘价"]
    rows = []
    
    for _, row in recent_df.iterrows():
        date_val = row[date_col]
        if isinstance(date_val, pd.Timestamp):
            date_str = date_val.strftime("%Y-%m-%d")
        elif hasattr(date_val, 'strftime'):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)
        
        value = row[value_col] if value_col in recent_df.columns else 0
        if isinstance(value, (int, float)):
            value_str = f"{value:.2f}"
        else:
            value_str = str(value)
        
        rows.append([date_str, value_str])
    
    return {
        "type": "table",
        "title": title,
        "headers": headers,
        "rows": rows
    }

def df_to_chart(df, title: str = "历史价格趋势") -> Dict[str, Any]:
    """将 DataFrame 转换为图表格式"""
    import pandas as pd
    
    date_col = "ds" if "ds" in df.columns else "日期"
    value_col = "y" if "y" in df.columns else "收盘"
    
    # 采样数据（如果数据点太多）
    if len(df) > 200:
        step = len(df) // 200
        df_sampled = df.iloc[::step].copy()
    else:
        df_sampled = df.copy()
    
    labels = []
    for _, row in df_sampled.iterrows():
        date_val = row[date_col]
        if isinstance(date_val, pd.Timestamp):
            labels.append(date_val.strftime("%Y-%m-%d"))
        elif hasattr(date_val, 'strftime'):
            labels.append(date_val.strftime("%Y-%m-%d"))
        else:
            labels.append(str(date_val))
    
    data = [
        float(row[value_col]) if isinstance(row[value_col], (int, float)) else 0.0
        for _, row in df_sampled.iterrows()
    ]
    
    return {
        "type": "chart",
        "title": title,
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "收盘价",
                "data": data,
                "color": "#8b5cf6"
            }]
        }
    }

def forecast_to_chart(historical_df, forecast: List[Dict[str, Any]], title: str = "价格预测趋势图") -> Dict[str, Any]:
    """将历史数据和预测结果合并为图表格式"""
    import pandas as pd
    
    # 历史数据
    hist_labels = []
    for _, row in historical_df.iterrows():
        date_val = row["ds"]
        if isinstance(date_val, pd.Timestamp):
            hist_labels.append(date_val.strftime("%Y-%m-%d"))
        elif hasattr(date_val, 'strftime'):
            hist_labels.append(date_val.strftime("%Y-%m-%d"))
        else:
            hist_labels.append(str(date_val))
    
    hist_data = [float(row["y"]) for _, row in historical_df.iterrows()]
    
    # 预测数据
    forecast_labels = [f["date"] for f in forecast]
    forecast_values = [f["value"] for f in forecast]
    
    # 合并标签
    all_labels = hist_labels + forecast_labels
    
    # 历史数据：前面是实际数据，后面是 null
    hist_data_full = hist_data + [None] * len(forecast)
    
    # 预测数据：前面是 null，后面是预测数据
    forecast_data_full = [None] * len(hist_data) + forecast_values
    
    return {
        "type": "chart",
        "title": title,
        "data": {
            "labels": all_labels,
            "datasets": [
                {
                    "label": "历史价格",
                    "data": hist_data_full,
                    "color": "#8b5cf6"
                },
                {
                    "label": "预测价格",
                    "data": forecast_data_full,
                    "color": "#06b6d4"
                }
            ]
        }
    }

def detect_anomalies(df, threshold: float = 2.0) -> Dict[str, Any]:
    """异常检测（使用 Z-score 方法）"""
    import numpy as np
    
    values = df["y"].values
    mean = np.mean(values)
    std = np.std(values)
    
    if std == 0:
        return {"count": 0, "anomalies": []}
    
    z_scores = np.abs((values - mean) / std)
    anomaly_indices = np.where(z_scores > threshold)[0]
    
    anomalies = []
    for idx in anomaly_indices:
        date = df.iloc[idx]["ds"]
        value = values[idx]
        change = ((value - mean) / mean) * 100
        
        anomalies.append({
            "date": date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date),
            "change": round(change, 2)
        })
    
    return {
        "count": len(anomalies),
        "anomalies": anomalies[:10]  # 最多返回10个
    }

# ============================================================
# API 接口
# ============================================================

@app.options("/api/chat/stream")
async def options_chat_stream():
    """处理 CORS 预检请求"""
    return {"message": "OK"}

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """对话流式接口"""
    
    async def generate():
        try:
            # 初始化 Agent
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                yield format_sse("error", {"message": "DEEPSEEK_API_KEY 未设置"})
                return
            
            agent = FinanceChatAgent(api_key)
            user_input = request.message
            
            # 初始化步骤状态
            steps = [{"id": s["id"], "name": s["name"], "status": "pending"} for s in STEPS]
            
            # ========== 步骤1: 数据获取与预处理 ==========
            steps[0]["status"] = "running"
            steps[0]["message"] = "解析用户需求..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # NLP 解析
            parsed = await asyncio.to_thread(agent.nlp.parse, user_input)
            data_config = parsed["data_config"]
            analysis_config = parsed["analysis_config"]
            
            steps[0]["message"] = "获取数据中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # 获取数据
            raw_df = await asyncio.to_thread(DataFetcher.fetch, data_config)
            df = await asyncio.to_thread(DataFetcher.prepare, raw_df, data_config)
            
            # 发送时序数据（表格）
            table_content = df_to_table(df, "历史时序数据（最近20条）", limit=20)
            yield format_sse("content", {"content": table_content})
            await asyncio.sleep(0.1)
            
            # 发送时序数据（图表）
            chart_content = df_to_chart(df, f"历史价格趋势（{len(df)}天）")
            yield format_sse("content", {"content": chart_content})
            await asyncio.sleep(0.1)
            
            steps[0]["status"] = "completed"
            steps[0]["message"] = f"已获取历史数据 {len(df)} 天"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤2: 时序特征分析 ==========
            steps[1]["status"] = "running"
            steps[1]["message"] = "分析中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)
            
            steps[1]["status"] = "completed"
            steps[1]["message"] = f"趋势: {features['trend']}, 波动性: {features['volatility']}"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤3: 异常检测 ==========
            steps[2]["status"] = "running"
            steps[2]["message"] = "检测中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            anomalies = await asyncio.to_thread(detect_anomalies, df)
            
            steps[2]["status"] = "completed"
            steps[2]["message"] = f"检测到 {anomalies['count']} 个异常波动点"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤4: 模型训练与评估 ==========
            steps[3]["status"] = "running"
            steps[3]["message"] = "训练模型中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            horizon = analysis_config.get("forecast_horizon", 30)
            forecast_result = await asyncio.to_thread(TimeSeriesAnalyzer.forecast_prophet, df, horizon)
            
            steps[3]["status"] = "completed"
            steps[3]["message"] = f"Prophet 模型最优 (MAE: {forecast_result['metrics']['mae']})"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤5: 预测生成 ==========
            steps[4]["status"] = "running"
            steps[4]["message"] = "生成预测中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            steps[4]["status"] = "completed"
            steps[4]["message"] = f"生成未来 {horizon} 天预测"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤6: 结果可视化 ==========
            steps[5]["status"] = "running"
            steps[5]["message"] = "生成图表中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # 发送模型对比表格
            model_table = {
                "type": "table",
                "title": "模型性能对比",
                "headers": ["模型", "MAE"],
                "rows": [
                    ["Prophet", forecast_result["metrics"]["mae"]]
                ]
            }
            yield format_sse("content", {"content": model_table})
            await asyncio.sleep(0.1)
            
            # 发送预测图表
            forecast_chart = forecast_to_chart(df, forecast_result["forecast"])
            yield format_sse("content", {"content": forecast_chart})
            await asyncio.sleep(0.1)
            
            steps[5]["status"] = "completed"
            steps[5]["message"] = "图表已生成"
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # ========== 步骤7: 分析完成 ==========
            steps[6]["status"] = "running"
            steps[6]["message"] = "生成报告中..."
            yield format_sse("step", {"steps": steps})
            await asyncio.sleep(0.1)
            
            # 生成报告
            user_question = analysis_config.get("user_question", user_input)
            report = await asyncio.to_thread(agent.reporter.generate, user_question, features, forecast_result)
            
            # 发送文本内容（分析报告）
            text_content = {
                "type": "text",
                "text": report
            }
            yield format_sse("content", {"content": text_content})
            await asyncio.sleep(0.1)
            
            steps[6]["status"] = "completed"
            steps[6]["message"] = "分析报告已生成"
            yield format_sse("step", {"steps": steps})
            
        except Exception as e:
            # 错误处理
            error_msg = {
                "type": "text",
                "text": f"处理过程中出现错误: {str(e)}"
            }
            yield format_sse("content", {"content": error_msg})
            import traceback
            print(f"Error: {traceback.format_exc()}")
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/")
async def root():
    return {"message": "小易猜猜 API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

