"""
模型选择模块
============

基于滚动回测的模型选择器
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from app.core.workflows.forecast import _run_single_model_forecast


async def select_best_model(
    df: pd.DataFrame,
    candidate_models: List[str],
    horizon: int,
    n_windows: int = 3,
    min_train_size: int = 60
) -> Dict:
    """
    基于滚动回测选择最佳模型

    Args:
        df: 输入数据 DataFrame，包含 ds 和 y 列
        candidate_models: 候选模型列表，如 ["prophet", "xgboost", "randomforest"]
        horizon: 预测天数
        n_windows: 滚动窗口数量，默认 3
        min_train_size: 最小训练集大小，默认 60

    Returns:
        {
            "best_model": str,
            "baseline": "seasonal_naive",
            "metrics": {
                "prophet": 12.3,
                "xgboost": 10.1,
                "seasonal_naive": 11.8
            },
            "is_better_than_baseline": bool
        }
    """
    if df.empty or len(df) < min_train_size + horizon:
        raise ValueError(
            f"数据量不足：需要至少 {min_train_size + horizon} 条数据，"
            f"当前只有 {len(df)} 条"
        )

    # 自动包含 seasonal_naive 作为 baseline
    all_models = list(set(candidate_models + ["seasonal_naive"]))
    baseline = "seasonal_naive"

    # 从 df 尾部生成 n_windows 个 rolling split
    total_len = len(df)
    window_size = horizon  # 每个窗口的测试集大小
    
    # 计算每个窗口的起始位置（从尾部向前）
    # 窗口1：训练集 [0: total_len - window_size], 测试集 [total_len - window_size: total_len]
    # 窗口2：训练集 [0: total_len - window_size * 2], 测试集 [total_len - window_size * 2: total_len - window_size]
    # ...
    splits = []
    for i in range(n_windows):
        test_end = total_len - i * window_size
        test_start = test_end - window_size
        
        # 确保有足够的训练数据
        if test_start < min_train_size:
            break
            
        train_df = df.iloc[:test_start].copy()
        test_df = df.iloc[test_start:test_end].copy()
        
        splits.append((train_df, test_df))

    if not splits:
        raise ValueError(
            f"无法生成足够的滚动窗口：需要至少 {min_train_size + window_size * n_windows} 条数据"
        )

    # 对每个模型，在每个 split 上计算 MAE
    model_maes: Dict[str, List[float]] = {model: [] for model in all_models}

    print(f"[ModelSelection] 开始模型选择，共 {len(splits)} 个滚动窗口，评估 {len(all_models)} 个模型")
    
    for window_idx, (train_df, test_df) in enumerate(splits, 1):
        print(f"[ModelSelection] 窗口 {window_idx}/{len(splits)}: 训练集 {len(train_df)} 条，测试集 {len(test_df)} 条")
        
        # 对每个模型进行预测
        for model_name in all_models:
            try:
                # 运行模型预测
                forecast_result = await _run_single_model_forecast(
                    train_df,
                    model_name,
                    horizon,
                    prophet_params={} if model_name == "prophet" else None
                )

                # 获取预测点
                forecast_points = forecast_result.points
                
                # 构建预测值字典（按日期）
                forecast_dict = {
                    point.date: point.value
                    for point in forecast_points
                }

                # 构建真实值字典（按日期）
                actual_dict = {
                    row["ds"].strftime("%Y-%m-%d"): row["y"]
                    for _, row in test_df.iterrows()
                }

                # 计算重叠部分的 MAE
                common_dates = set(forecast_dict.keys()) & set(actual_dict.keys())
                
                if not common_dates:
                    # 如果没有重叠日期，跳过这个窗口
                    print(f"[ModelSelection] 模型 {model_name.upper()} 在窗口 {window_idx} 上无重叠日期，跳过")
                    continue

                errors = []
                for date in sorted(common_dates):
                    pred = forecast_dict[date]
                    actual = actual_dict[date]
                    errors.append(abs(actual - pred))

                if errors:
                    mae = np.mean(errors)
                    model_maes[model_name].append(mae)
                    print(f"[ModelSelection] 模型 {model_name.upper()} 在窗口 {window_idx} 上运行成功，MAE: {mae:.4f}")

            except Exception as e:
                # 如果模型运行失败，跳过这个窗口
                print(f"[ModelSelection] 模型 {model_name.upper()} 在窗口 {window_idx} 上运行失败: {e}")
                continue

    # 对每个模型取平均 MAE
    print(f"[ModelSelection] 计算各模型平均 MAE...")
    model_avg_maes: Dict[str, float] = {}
    for model_name, maes in model_maes.items():
        if maes:
            avg_mae = float(np.mean(maes))
            model_avg_maes[model_name] = avg_mae
            print(f"[ModelSelection] 模型 {model_name.upper()}: 平均 MAE = {avg_mae:.4f} (基于 {len(maes)} 个窗口)")
        else:
            # 如果某个模型在所有窗口上都失败，设为很大的值
            model_avg_maes[model_name] = float('inf')
            print(f"[ModelSelection] 模型 {model_name.upper()}: 在所有窗口上运行失败")

    # 先从候选模型中选出最佳模型（不包括 baseline）
    candidate_model_maes = {
        model: mae for model, mae in model_avg_maes.items() 
        if model != baseline
    }
    
    if not candidate_model_maes or all(mae == float('inf') for mae in candidate_model_maes.values()):
        # 如果所有候选模型都失败，返回 baseline
        best_model = baseline
        print(f"[ModelSelection] 所有候选模型都失败，使用 baseline: {baseline}")
    else:
        # 只在候选模型中选择最佳模型
        best_model = min(candidate_model_maes.items(), key=lambda x: x[1])[0]
        best_mae = candidate_model_maes[best_model]
        print(f"[ModelSelection] 从候选模型中选出最佳模型: {best_model.upper()} (平均 MAE: {best_mae:.4f})")

    # 获取 baseline 的 MAE
    baseline_mae = model_avg_maes.get(baseline, float('inf'))
    best_mae = model_avg_maes.get(best_model, float('inf'))
    
    # 检查最佳模型是否优于 baseline
    is_better_than_baseline = (
        best_model != baseline and
        best_mae != float('inf') and
        baseline_mae != float('inf') and
        best_mae < baseline_mae
    )

    # 格式化 metrics（将 inf 转换为 None 或很大的数字）
    formatted_metrics = {}
    for model_name, mae in model_avg_maes.items():
        if mae == float('inf'):
            formatted_metrics[model_name] = None
        else:
            formatted_metrics[model_name] = round(mae, 4)

    # 打印最终选择结果
    if baseline_mae != float('inf'):
        print(f"[ModelSelection] Baseline ({baseline}): MAE = {baseline_mae:.4f}")
    if is_better_than_baseline:
        print(f"[ModelSelection] 最佳模型优于 baseline ({best_mae:.4f} < {baseline_mae:.4f})")
    elif best_model == baseline:
        print(f"[ModelSelection] 最佳模型即为 baseline")
    else:
        print(f"[ModelSelection] 最佳模型不优于 baseline ({best_mae:.4f} >= {baseline_mae:.4f})")

    return {
        "best_model": best_model,
        "baseline": baseline,
        "metrics": formatted_metrics,
        "is_better_than_baseline": is_better_than_baseline
    }
