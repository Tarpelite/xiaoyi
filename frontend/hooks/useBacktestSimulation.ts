/**
 * useBacktestSimulation Hook
 * ==========================
 * 
 * 交互式时间旅行回测功能的核心Hook
 * 
 * 功能:
 * - 防抖触发回测请求 (600ms)
 * - AbortController处理竞态条件
 * - 状态管理 (splitDate, loading, metrics等)
 * - 数据合并逻辑
 */

import { useState, useRef, useMemo, useCallback } from 'react'
import type { TimeSeriesPoint } from '@/lib/api/analysis'

// ========== Types ==========

interface BacktestMetrics {
    mae: number
    rmse: number
    mape: number
    calculation_time_ms: number
}

interface BacktestState {
    splitDate: string | null
    isBacktesting: boolean
    isLoading: boolean
    metrics: BacktestMetrics | null
    backtestData: TimeSeriesPoint[] | null
    groundTruth: TimeSeriesPoint[] | null
    error: string | null
}

interface BacktestChartData {
    history: TimeSeriesPoint[]
    groundTruth: TimeSeriesPoint[]
    prediction: TimeSeriesPoint[]
    splitIndex: number
}

interface UseBacktestSimulationProps {
    sessionId: string
    messageId: string
    originalData: TimeSeriesPoint[]
}

// ========== Initial State ==========

const initialState: BacktestState = {
    splitDate: null,
    isBacktesting: false,
    isLoading: false,
    metrics: null,
    backtestData: null,
    groundTruth: null,
    error: null
}

// ========== Hook ==========

export function useBacktestSimulation({
    sessionId,
    messageId,
    originalData
}: UseBacktestSimulationProps) {
    const [state, setState] = useState<BacktestState>(initialState)
    const abortControllerRef = useRef<AbortController | null>(null)
    const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)

    // API Base URL
    const API_BASE_URL = typeof window !== 'undefined'
        ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
        : 'http://localhost:8000'

    /**
     * 触发回测 (带防抖)
     */
    const triggerBacktest = useCallback((splitDate: string) => {
        // 清除之前的防抖计时器
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current)
        }

        // Optimistic UI: 立即更新splitDate
        setState(prev => ({ ...prev, splitDate, error: null }))

        // 防抖600ms后触发实际请求
        debounceTimerRef.current = setTimeout(async () => {
            // 取消之前的请求
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }

            abortControllerRef.current = new AbortController()
            setState(prev => ({ ...prev, isLoading: true }))

            try {
                const response = await fetch(`${API_BASE_URL}/api/analysis/backtest`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionId,
                        message_id: messageId,
                        split_date: splitDate
                    }),
                    signal: abortControllerRef.current.signal
                })

                if (!response.ok) {
                    const errorData = await response.json()
                    throw new Error(errorData.detail || '回测失败')
                }

                const data = await response.json()

                setState({
                    splitDate,
                    isBacktesting: true,
                    isLoading: false,
                    metrics: data.metrics,
                    backtestData: data.backtest_data,
                    groundTruth: data.ground_truth,
                    error: null
                })
            } catch (error: any) {
                if (error.name !== 'AbortError') {
                    setState(prev => ({
                        ...prev,
                        isLoading: false,
                        error: error.message || '回测失败'
                    }))
                }
            }
        }, 600)
    }, [sessionId, messageId])

    /**
     * 重置回测状态
     */
    const resetBacktest = useCallback(() => {
        // 取消进行中的请求
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current)
        }
        setState(initialState)
    }, [])

    /**
     * 合并图表数据
     * 
     * 返回格式:
     * - history: 分割点之前的历史数据
     * - groundTruth: 分割点之后的实际数据
     * - prediction: 回测预测数据
     */
    const chartData = useMemo<BacktestChartData | null>(() => {
        if (!state.isBacktesting || !state.splitDate) {
            return null
        }

        const splitIndex = originalData.findIndex(p => p.date >= state.splitDate!)

        if (splitIndex === -1) {
            return null
        }

        return {
            history: originalData.slice(0, splitIndex),
            groundTruth: state.groundTruth || [],
            prediction: state.backtestData || [],
            splitIndex
        }
    }, [state.isBacktesting, state.splitDate, state.backtestData, state.groundTruth, originalData])

    // 清理effect
    useCallback(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current)
            }
        }
    }, [])

    return {
        // 状态
        splitDate: state.splitDate,
        isBacktesting: state.isBacktesting,
        isLoading: state.isLoading,
        metrics: state.metrics,
        error: state.error,

        // 数据
        chartData,

        // 操作
        triggerBacktest,
        resetBacktest
    }
}
