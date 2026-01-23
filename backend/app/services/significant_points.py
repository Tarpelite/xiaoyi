"""
显著点检测服务
==================

基于金融时序分析的显著日期识别算法
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class SignificantPointService:
    """
    显著点识别服务
    
    结合多维度指标识别股票历史中的关键时刻：
    - 价格波动 (Z-Score)
    - 拐点检测 (局部极值)
    - 成交量异常
    - 新闻热度
    """
    
    def __init__(self, window: int = 20):
        """
        初始化
        
        Args:
            window: 滚动窗口大小（默认20个交易日）
        """
        self.window = window
    
    def calculate_points(
        self, 
        df: pd.DataFrame, 
        news_counts: Dict[str, int], 
        top_k: int = 5
    ) -> List[Dict]:
        """
        计算显著点
        
        Args:
            df: 包含 ['date', 'close', 'volume'] 的 DataFrame
            news_counts: 日期到新闻数量的映射，例如 {"2026-01-20": 15, ...}
            top_k: 返回前 K 个最显著的点
            
        Returns:
            显著点列表，格式:
            [
                {
                    "date": "2024-01-03",
                    "score": 3.45,
                    "type": "negative",  # 或 "positive"
                    "reason": "价格异常波动、阶段性见顶",
                    "is_pivot": True
                },
                ...
            ]
        """
        if df.empty or len(df) < self.window:
            return []
        
        df = df.copy()
        
        # 1. 计算收益率和滚动统计
        df['returns'] = df['close'].pct_change()
        df['rolling_mu'] = df['returns'].rolling(window=self.window).mean()
        df['rolling_std'] = df['returns'].rolling(window=self.window).std()
        
        # 2. 计算 Z-Score (标准化波动)
        # 避免除零
        df['rolling_std'] = df['rolling_std'].replace(0, df['rolling_std'].mean() if df['rolling_std'].mean() > 0 else 0.01)
        df['z_score'] = (df['returns'] - df['rolling_mu']) / df['rolling_std']
        df['s_vol'] = df['z_score'].abs()
        
        # 3. 计算成交量倍率
        rolling_vol_mean = df['volume'].rolling(window=self.window).mean()
        rolling_vol_mean = rolling_vol_mean.replace(0, df['volume'].mean() if df['volume'].mean() > 0 else 1)
        df['s_vlm'] = df['volume'] / rolling_vol_mean
        
        # 4. 局部极值检测（拐点）
        df['is_min'] = df['close'] == df['close'].rolling(window=7, center=True).min()
        df['is_max'] = df['close'] == df['close'].rolling(window=7, center=True).max()
        df['s_pivot'] = (df['is_min'] | df['is_max']).astype(int) * 2.0  # 拐点权重加倍
        
        # 5. 整合新闻密度（使用 log1p 平滑）
        df['s_news'] = df['date'].apply(lambda x: np.log1p(news_counts.get(str(x)[:10], 0)))
        
        # 6. 最终综合评分
        # 权重：波动(0.4) + 拐点(0.3) + 成交量(0.2) + 新闻(0.1)
        df['final_score'] = (
            df['s_vol'].fillna(0) * 0.4 + 
            df['s_pivot'].fillna(0) * 0.3 + 
            df['s_vlm'].fillna(0) * 0.2 + 
            df['s_news'].fillna(0) * 0.1
        )
        
        # 7. 过滤掉 NaN 和无效数据
        df = df.dropna(subset=['final_score', 'returns'])
        
        # 8. 平静股处理：如果所有分数都很低，切换到"新闻挖掘模式"
        max_score = df['final_score'].max()
        if max_score < 1.0:
            # 暗盘异动：只标记新闻最多的日子
            if news_counts:
                top_news_dates = sorted(news_counts.items(), key=lambda x: x[1], reverse=True)[:top_k]
                df_filtered = df[df['date'].astype(str).str[:10].isin([d[0] for d in top_news_dates])]
            else:
                df_filtered = df.nlargest(top_k, 'final_score')
        else:
            # 正常模式：选择评分最高的点
            df_filtered = df.nlargest(top_k, 'final_score')
        
        # 9. 生成结果
        results = []
        for _, row in df_filtered.iterrows():
            reason = self._generate_reason(row, news_counts)
            results.append({
                "date": str(row['date'])[:10],  # 统一格式为 YYYY-MM-DD
                "score": round(float(row['final_score']), 2),
                "type": "positive" if row['returns'] > 0 else "negative",
                "reason": reason,
                "is_pivot": bool(row['s_pivot'] > 0)
            })
        
        # 按日期排序
        return sorted(results, key=lambda x: x['date'])
    
    def _generate_reason(self, row, news_counts: Dict[str, int]) -> str:
        """
        生成显著点的原因描述
        
        Args:
            row: DataFrame 行
            news_counts: 新闻数量映射
            
        Returns:
            原因字符串，例如 "价格异常波动、阶段性见顶、成交量激增"
        """
        reasons = []
        
        # 波动异常
        if row['s_vol'] > 2:
            reasons.append("价格异常波动")
        
        # 拐点
        if row['is_max']:
            reasons.append("阶段性见顶")
        if row['is_min']:
            reasons.append("阶段性筑底")
        
        # 成交量
        if row['s_vlm'] > 2:
            reasons.append("成交量激增")
        
        # 新闻热度
        date_str = str(row['date'])[:10]
        if news_counts.get(date_str, 0) > 5:
            reasons.append("舆情热度爆发")
        
        return "、".join(reasons) if reasons else "趋势关键节点"
    
    def generate_anomaly_zones(
        self, 
        significant_points: List[Dict],
        df: pd.DataFrame
    ) -> List[Dict]:
        """
        从显著点生成异常区域（用于前端 ReferenceArea）
        
        Args:
            significant_points: calculate_points 返回的显著点列表
            df: 原始价格数据
            
        Returns:
            异常区域列表，格式:
            [
                {
                    "startDate": "2024-01-02",
                    "endDate": "2024-01-04",
                    "summary": "价格异常波动、阶段性见顶",
                    "sentiment": "negative"
                },
                ...
            ]
        """
        zones = []
        dates_list = sorted(df['date'].astype(str).str[:10].tolist())
        
        for point in significant_points:
            if not point['is_pivot']:
                continue  # 只为拐点创建区域
            
            date = point['date']
            
            # 找到该日期的索引
            try:
                idx = dates_list.index(date)
            except ValueError:
                continue
            
            # 扩展半个交易日（前后各1天）
            start_idx = max(0, idx - 1)
            end_idx = min(len(dates_list) - 1, idx + 1)
            
            zones.append({
                "startDate": dates_list[start_idx],
                "endDate": dates_list[end_idx],
                "summary": point['reason'],
                "sentiment": point['type']  # "positive" or "negative"
            })
        
        return zones
