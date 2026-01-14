/**
 * BacktestControls Component  
 * ===========================
 * 
 * 简化版回测控件 - 仅显示MAE和重置按钮
 * 滑块已集成到图表内部
 */

import React from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'

interface BacktestControlsProps {
    mae: number | null
    isLoading: boolean
    onReset: () => void
}

export function BacktestControls({
    mae,
    isLoading,
    onReset
}: BacktestControlsProps) {
    if (!mae && !isLoading) {
        return null
    }

    return (
        <div className="flex items-center justify-between px-2 py-2 bg-purple-900/10 rounded-lg border border-purple-500/20 mb-2">
            <div className="flex items-center gap-3">
                {isLoading && (
                    <div className="flex items-center gap-2 text-xs text-purple-400">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        计算中...
                    </div>
                )}
                {mae !== null && (
                    <div className="text-xs text-gray-400">
                        预测误差 (MAE): <span className="text-purple-400 font-mono font-bold">{mae.toFixed(4)}</span>
                    </div>
                )}
            </div>
            <button
                onClick={onReset}
                disabled={isLoading}
                className="px-2 py-1 text-xs bg-purple-600/20 hover:bg-purple-600/40 disabled:opacity-50 text-purple-300 rounded transition-colors flex items-center gap-1"
            >
                <RefreshCw className="w-3 h-3" />
                重置回测
            </button>
        </div>
    )
}
