import json
from typing import Any, Dict, List, Optional
import pandas as pd

def format_sse(event_type: str, data: Any) -> str:
    """格式化 SSE 消息"""
    if isinstance(data, dict):
        payload = {'type': event_type, **data}
    else:
        payload = {'type': event_type, 'data': data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def df_to_table(df, title: str = "历史时序数据", limit: int = 20) -> Dict[str, Any]:
    """将 DataFrame 转换为表格格式"""
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

STEPS = [
    {"id": "1", "name": "数据获取与预处理"},
    {"id": "2", "name": "时序特征分析"},
    {"id": "3", "name": "异常检测"},
    {"id": "4", "name": "模型训练与评估"},
    {"id": "5", "name": "预测生成"},
    {"id": "6", "name": "结果可视化"},
    {"id": "7", "name": "分析完成"},
]
