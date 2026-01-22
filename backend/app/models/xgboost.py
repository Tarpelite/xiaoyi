"""
XGBoost 预测模型
================

基于 XGBoost 的时序预测实现
"""

from typing import Dict, Any, List
from datetime import timedelta
import pandas as pd
import numpy as np
from .base import BaseForecaster
from .analyzer import TimeSeriesAnalyzer
import xgboost as xgb
from app.utils.trading_calendar import get_next_trading_days
from app.schemas.session_schema import ForecastResult, ForecastMetrics, TimeSeriesPoint

class XGBoostForecaster(BaseForecaster):
    """XGBoost 时序预测器"""

    def forecast(self, df: pd.DataFrame, horizon: int = 30) -> ForecastResult:
        """
        使用 XGBoost 模型进行时序预测

        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数

        Returns:
            ForecastResult: 统一的预测结果

        Raises:
            ImportError: 未安装 xgboost
            ValueError: 数据量不足
        """
        # 检查数据量
        if len(df) < 60:
            raise ValueError(f"XGBoost 需要至少60条历史数据，当前只有 {len(df)} 条")

        # 创建特征
        feature_df = TimeSeriesAnalyzer.create_features(df, max_lag=min(30, len(df) // 2))

        # 准备训练数据
        feature_cols = [col for col in feature_df.columns if col not in ["ds", "y"]]
        X = feature_df[feature_cols].values
        y = feature_df["y"].values

        # 划分训练集和验证集 (80/20 split)
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # 训练模型
        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )

        # 兼容不同版本的 XGBoost
        try:
            # 尝试新版本方式 (XGBoost 2.0+)
            try:
                early_stop = xgb.callback.EarlyStopping(rounds=10, save_best=True)
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[early_stop],
                    verbose=False
                )
            except (AttributeError, TypeError):
                # 如果 callback 方式失败，尝试旧版本方式
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=10,
                    verbose=False
                )
        except TypeError:
            # 如果两种方式都失败，不使用 early stopping
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )

        # 计算残差用于置信区间
        train_pred = model.predict(X)
        residuals = y - train_pred
        std_error = np.std(residuals)

        # 递归预测未来值
        forecast_points = self._recursive_forecast(
            model, feature_df, df, horizon, feature_cols, std_error
        )

        # 计算验证集指标
        val_pred = model.predict(X_val)
        mae = np.mean(np.abs(y_val - val_pred))
        rmse = np.sqrt(np.mean((y_val - val_pred) ** 2))

        return ForecastResult(
            points=forecast_points,
            metrics=ForecastMetrics(
                mae=round(float(mae), 4),
                rmse=round(float(rmse), 4)
            ),
            model="xgboost"
        )
    
    def _recursive_forecast(
        self,
        model,
        feature_df: pd.DataFrame,
        df: pd.DataFrame,
        horizon: int,
        feature_cols: list,
        std_error: float
    ) -> List[TimeSeriesPoint]:
        """递归预测未来值"""
        forecast_points = []
        last_date = df["ds"].iloc[-1]
        last_values = df["y"].values[-30:].tolist()

        # 获取未来交易日
        trading_days = get_next_trading_days(last_date, horizon)

        for i in range(horizon):
            future_date = trading_days[i]

            # 准备特征
            future_features = pd.Series(index=feature_df.columns, dtype=float)

            # 滞后特征
            if i == 0:
                future_features["lag_1"] = df["y"].iloc[-1]
            else:
                future_features["lag_1"] = forecast_points[-1].value

            for lag in [7, 14, 30]:
                lag_col = f"lag_{lag}"
                if lag_col in feature_cols:
                    if i + 1 >= lag:
                        if i + 1 - lag < len(forecast_points):
                            future_features[lag_col] = forecast_points[i + 1 - lag].value
                        else:
                            idx = len(last_values) - (lag - (i + 1))
                            future_features[lag_col] = last_values[idx] if idx >= 0 else last_values[0]
                    else:
                        idx = len(last_values) - (lag - i - 1)
                        future_features[lag_col] = last_values[idx] if idx >= 0 else last_values[0]

            # 移动平均
            all_values = last_values + [p.value for p in forecast_points]
            for window in [7, 14, 30]:
                ma_col = f"ma_{window}"
                std_col = f"std_{window}"
                if ma_col in feature_cols:
                    window_values = all_values[-window:] if len(all_values) >= window else all_values
                    future_features[ma_col] = np.mean(window_values)
                    future_features[std_col] = np.std(window_values) if len(window_values) > 1 else 0

            # 时间特征
            future_features["day_of_week"] = future_date.dayofweek
            future_features["day_of_month"] = future_date.day
            future_features["month"] = future_date.month
            future_features["quarter"] = future_date.quarter
            future_features["trend"] = len(df) + i + 1

            # 填充缺失值
            for col in feature_cols:
                if pd.isna(future_features[col]):
                    future_features[col] = feature_df[col].iloc[-1] if col in feature_df.columns else 0

            # 预测
            X_future = future_features[feature_cols].values.reshape(1, -1)
            pred_value = model.predict(X_future)[0]

            forecast_points.append(TimeSeriesPoint(
                date=future_date.strftime("%Y-%m-%d"),
                value=round(float(pred_value), 2),
                is_prediction=True
            ))

        return forecast_points
