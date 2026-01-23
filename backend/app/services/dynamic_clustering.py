"""
动态聚类服务
==================

基于自适应阈值的智能股价异常区域识别算法
替代固定天数的简单逻辑，提供专业的量化分析能力
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from datetime import datetime, timedelta


class DynamicClusteringService:
    """
    动态聚类服务
    
    采用自适应阈值算法识别股价异常区域：
    1. 计算每日综合得分 S = (|Return| × 0.4) + (Vol_Ratio × 0.3) + (News_Density × 0.3)
    2. 使用90/75分位数作为聚类阈值
    3. 智能合并相邻区域（1-10天限制）
    4. 平静期fallback到Top 2点位
    """
    
    def __init__(self, lookback: int = 60, max_zone_days: int = 10):
        """
        初始化
        
        Args:
            lookback: 计算分位数的回溯天数（默认60）
            max_zone_days: 单个区域最大天数（默认10）
        """
        self.lookback = lookback
        self.max_zone_days = max_zone_days
    
    def calculate_daily_scores(
        self, 
        df: pd.DataFrame, 
        news_counts: Dict[str, int]
    ) -> pd.DataFrame:
        """
        计算每日综合得分
        
        Args:
            df: 包含 ['date', 'close', 'volume'] 的 DataFrame
            news_counts: 日期到新闻数量的映射
            
        Returns:
            扩展后的DataFrame，新增 'daily_score' 列
        """
        if df.empty or len(df) < 2:
            df['daily_score'] = 0
            return df
        
        df = df.copy()
        
        # 1. 计算收益率（绝对值）
        df['returns'] = df['close'].pct_change().fillna(0)
        df['abs_return'] = df['returns'].abs()
        
        # 2. 计算成交量比率（相对于20日均线）
        rolling_vol_mean = df['volume'].rolling(window=min(20, len(df))).mean()
        rolling_vol_mean = rolling_vol_mean.replace(0, df['volume'].mean() if df['volume'].mean() > 0 else 1)
        df['vol_ratio'] = df['volume'] / rolling_vol_mean
        
        # 3. 新闻密度（log1p平滑）
        df['news_density'] = df['date'].apply(
            lambda x: np.log1p(news_counts.get(str(x)[:10], 0))
        )
        
        # 4. 标准化各指标到0-1范围
        for col in ['abs_return', 'vol_ratio', 'news_density']:
            col_max = df[col].max()
            if col_max > 0:
                df[f'{col}_norm'] = df[col] / col_max
            else:
                df[f'{col}_norm'] = 0
        
        # 5. 综合得分 S = Return×0.4 + VolRatio×0.3 + NewsDensity×0.3
        df['daily_score'] = (
            df['abs_return_norm'].fillna(0) * 0.4 +
            df['vol_ratio_norm'].fillna(0) * 0.3 +
            df['news_density_norm'].fillna(0) * 0.3
        )
        
        return df
    
    def adaptive_clustering(
        self, 
        df: pd.DataFrame
    ) -> List[Dict]:
        """
        自适应阈值聚类
        
        Args:
            df: 包含 'daily_score' 的 DataFrame
            
        Returns:
            初步聚类区域列表
        """
        if df.empty or 'daily_score' not in df.columns:
            return []
        
        scores = df['daily_score'].values
        dates = df['date'].astype(str).str[:10].tolist()
        returns = df['returns'].fillna(0).values
        
        # 计算自适应阈值
        valid_scores = scores[~np.isnan(scores)]
        if len(valid_scores) < 10:
            # 数据太少，使用固定阈值
            t_high = 0.8
            t_low = 0.6
        else:
            # 使用最近lookback天计算分位数（提高到95/85以减少zone数量）
            recent_scores = valid_scores[-self.lookback:] if len(valid_scores) > self.lookback else valid_scores
            t_high = np.percentile(recent_scores, 95)  # 从90提高到95
            t_low = np.percentile(recent_scores, 85)   # 从75提高到85
            
            # 确保阈值有意义（过滤噪音）
            t_high = max(t_high, 0.3)
            t_low = max(t_low, 0.2)
        
        # 聚类逻辑
        zones = []
        i = 0
        
        while i < len(scores):
            if scores[i] > t_high:
                # 启动一个新区域
                zone_start = i
                zone_end = i
                
                # 向后扩展（只要分数 > t_low）
                j = i + 1
                while j < len(scores) and scores[j] > t_low and (j - zone_start) < self.max_zone_days:
                    zone_end = j
                    j += 1
                
                # 向前扩展（只要分数 > t_low）
                j = i - 1
                while j >= 0 and scores[j] > t_low and (zone_end - j) < self.max_zone_days:
                    zone_start = j
                    j -= 1
                
                # 计算区域内平均收益率
                zone_returns = returns[zone_start:zone_end+1]
                avg_return = float(np.mean(zone_returns))
                
                zones.append({
                    "start_idx": zone_start,
                    "end_idx": zone_end,
                    "startDate": dates[zone_start],
                    "endDate": dates[zone_end],
                    "avg_score": float(np.mean(scores[zone_start:zone_end+1])),
                    "avg_return": avg_return,
                    "zone_type": "cluster"
                })
                
                i = zone_end + 1
            else:
                i += 1
        
        return zones
    
    def fallback_top_points(
        self, 
        df: pd.DataFrame, 
        k: int = 2
    ) -> List[Dict]:
        """
        平静期fallback：强制标注Top K点位
        
        Args:
            df: 包含 'daily_score' 的 DataFrame
            k: 返回前K个点（默认2）
            
        Returns:
            fallback区域列表
        """
        if df.empty or len(df) < k:
            return []
        
        # 按得分降序排列
        df_sorted = df.nlargest(k, 'daily_score')
        
        zones = []
        dates = df['date'].astype(str).str[:10].tolist()
        
        for _, row in df_sorted.iterrows():
            idx = df.index.get_loc(row.name)
            zones.append({
                "start_idx": idx,
                "end_idx": idx,
                "startDate": str(row['date'])[:10],
                "endDate": str(row['date'])[:10],
                "avg_score": float(row['daily_score']),
                "avg_return": float(row['returns']) if 'returns' in row else 0.0,
                "zone_type": "fallback"
            })
        
        return zones
    
    def calculate_impact(self, zone: Dict, max_score: float) -> float:
        """
        计算区域影响力（0-1归一化）
        
        Args:
            zone: 区域字典
            max_score: 全局最大得分
            
        Returns:
            影响力得分（0-1）
        """
        if max_score <= 0:
            return 0.5
        
        # 基于平均得分归一化
        impact = min(zone['avg_score'] / max_score, 1.0)
        
        # 确保最小值为0.3（增强可见性）
        return max(impact, 0.3)
    
    def generate_zones(
        self, 
        df: pd.DataFrame, 
        news_counts: Dict[str, int]
    ) -> List[Dict]:
        """
        生成最终异常区域列表
        
        完整流程：
        1. 计算每日得分
        2. 自适应聚类
        3. 如果没有聚类结果，使用fallback
        4. 计算impact
        5. 确定zone_type和sentiment
        
        Args:
            df: 价格数据 DataFrame
            news_counts: 新闻计数字典
            
        Returns:
            异常区域列表，格式见implementation_plan.md
        """
        # Step 1: 计算得分
        df_with_scores = self.calculate_daily_scores(df, news_counts)
        
        # Step 2: 聚类
        zones = self.adaptive_clustering(df_with_scores)
        
        # Step 3: Fallback检测
        if len(zones) == 0:
            zones = self.fallback_top_points(df_with_scores, k=2)
            is_calm = True
        else:
            is_calm = False
        
        # Step 4: 计算impact和enrichment
        max_score = df_with_scores['daily_score'].max() if not df_with_scores.empty else 1.0
        
        enriched_zones = []
        for zone in zones:
            zone['impact'] = self.calculate_impact(zone, max_score)
            zone['sentiment'] = 'positive' if zone['avg_return'] >= 0 else 'negative'
            
            # 平静期标记
            if is_calm:
                zone['zone_type'] = 'calm'
            
            enriched_zones.append(zone)
        
        # Step 5: 按impact排序，取top 10
        enriched_zones.sort(key=lambda x: x['impact'], reverse=True)
        top_zones = enriched_zones[:10]
        
        # Step 6: 移除内部索引字段
        for zone in top_zones:
            zone.pop('start_idx', None)
            zone.pop('end_idx', None)
        
        return top_zones
