/**
 * SSE (Server-Sent Events) Stream Hook
 * =====================================
 * 
 * 管理SSE连接，接收服务器推送的事件，支持自动重连
 * 
 * 核心功能:
 * - EventSource连接管理
 * - 事件类型路由
 * - 自动重连机制 (指数退避)
 * - 连接状态跟踪
 */

import { useEffect, useRef, useState, useCallback } from 'react'

// SSE事件类型定义
export interface SSEEvent {
    type: string
    timestamp: string
    session_id: string
    message_id: string
    data: any
}

export interface ThinkingChunkData {
    chunk: string
    accumulated: string
}

export interface IntentData {
    is_in_scope: boolean
    is_forecast: boolean
    enable_rag: boolean
    enable_search: boolean
    enable_domain_info: boolean
    stock_mention?: string
    stock_full_name?: string
    reason: string
}

export interface StepUpdateData {
    step: number
    status: string
    message: string
}

export interface ErrorData {
    error: string
    error_code: string
    retry_able: boolean
    suggested_action: string
}

// Hook选项
export interface SSEStreamOptions {
    onSessionCreated?: (data: any) => void
    onThinkingChunk?: (data: ThinkingChunkData) => void
    onThinkingComplete?: (data: { thinking_content: string; total_length: number }) => void
    onIntentDetermined?: (data: IntentData) => void
    onStepUpdate?: (data: StepUpdateData) => void
    onChatChunk?: (data: { chunk: string; accumulated: string }) => void
    onChatComplete?: (data: { chat_response: string }) => void
    onConclusionComplete?: (data: { conclusion: string }) => void
    onAnalysisComplete?: () => void
    onError?: (data: ErrorData) => void
    onHeartbeat?: () => void
    onConnectionChange?: (status: 'connecting' | 'open' | 'closed' | 'error') => void
    autoReconnect?: boolean
    maxRetries?: number
    retryDelay?: number  // 初始重试延迟(ms)
}

export interface SSEStreamResult {
    status: 'connecting' | 'open' | 'closed' | 'error'
    error: string | null
    retryCount: number
    close: () => void
}

/**
 * SSE流式连接Hook
 * 
 * @param url SSE endpoint URL (不传则不连接)
 * @param options 事件回调和配置
 * @returns 连接状态和控制函数
 */
export function useSSEStream(
    url: string | null,
    options: SSEStreamOptions = {}
): SSEStreamResult {
    const {
        onSessionCreated,
        onThinkingChunk,
        onThinkingComplete,
        onIntentDetermined,
        onStepUpdate,
        onChatChunk,
        onChatComplete,
        onConclusionComplete,
        onAnalysisComplete,
        onError,
        onHeartbeat,
        onConnectionChange,
        autoReconnect = true,
        maxRetries = 3,
        retryDelay = 1000,
    } = options

    const [status, setStatus] = useState<'connecting' | 'open' | 'closed' | 'error'>('closed')
    const [error, setError] = useState<string | null>(null)
    const [retryCount, setRetryCount] = useState(0)

    const eventSourceRef = useRef<EventSource | null>(null)
    const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const isMountedRef = useRef(true)

    // 更新状态的辅助函数
    const updateStatus = useCallback((newStatus: typeof status) => {
        if (isMountedRef.current) {
            setStatus(newStatus)
            onConnectionChange?.(newStatus)
        }
    }, [onConnectionChange])

    // 连接SSE
    const connect = useCallback(() => {
        if (!url || !isMountedRef.current) return

        console.log(`[SSE] Connecting to ${url}...`)
        updateStatus('connecting')
        setError(null)

        const es = new EventSource(url)
        eventSourceRef.current = es

        // 连接打开
        es.onopen = () => {
            console.log('[SSE] Connection established')
            updateStatus('open')
            setRetryCount(0)  // 重置重试计数
        }

        // 为每个命名事件添加监听器 (EventSource需要显式监听命名事件)
        const handleEvent = (eventType: string, callback?: (data: any) => void) => {
            es.addEventListener(eventType, (event: MessageEvent) => {
                try {
                    const data = JSON.parse(event.data) as SSEEvent
                    console.log(`[SSE] Received ${eventType}:`, data.data)
                    callback?.(data.data)
                } catch (e) {
                    console.error(`[SSE] Failed to parse ${eventType}:`, e)
                }
            })
        }

        // 注册所有事件类型
        handleEvent('session_created', onSessionCreated)
        handleEvent('thinking_chunk', onThinkingChunk)
        handleEvent('thinking_complete', onThinkingComplete)
        handleEvent('intent_determined', onIntentDetermined)
        handleEvent('step_update', onStepUpdate)
        handleEvent('chat_chunk', onChatChunk)
        handleEvent('chat_complete', onChatComplete)
        handleEvent('conclusion_complete', onConclusionComplete)
        handleEvent('analysis_complete', onAnalysisComplete)
        handleEvent('error', onError)
        handleEvent('heartbeat', onHeartbeat)

        // 通用消息处理 (保留作为fallback)
        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data) as SSEEvent
                console.log('[SSE] Received generic message:', data.type)
            } catch (e) {
                console.error('[SSE] Failed to parse event:', e)
            }
        }

        // 错误处理
        es.onerror = (event) => {
            console.error('[SSE] Connection error:', event)
            es.close()
            updateStatus('error')
            setError('SSE connection failed')

            // 自动重连
            if (autoReconnect && retryCount < maxRetries && isMountedRef.current) {
                const delay = Math.min(retryDelay * Math.pow(2, retryCount), 10000)
                console.log(`[SSE] Reconnecting in ${delay}ms... (attempt ${retryCount + 1}/${maxRetries})`)

                retryTimeoutRef.current = setTimeout(() => {
                    setRetryCount(prev => prev + 1)
                    connect()
                }, delay)
            } else if (retryCount >= maxRetries) {
                console.error('[SSE] Max retries reached, giving up')
                updateStatus('error')
            }
        }

    }, [url, updateStatus, autoReconnect, maxRetries, retryDelay, retryCount,
        onSessionCreated, onThinkingChunk, onThinkingComplete, onIntentDetermined,
        onStepUpdate, onChatChunk, onChatComplete, onConclusionComplete,
        onAnalysisComplete, onError, onHeartbeat])

    // 关闭连接
    const close = useCallback(() => {
        console.log('[SSE] Closing connection')
        if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current)
            retryTimeoutRef.current = null
        }
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }
        updateStatus('closed')
    }, [updateStatus])

    // 组件挂载时连接
    useEffect(() => {
        isMountedRef.current = true

        if (url) {
            connect()
        }

        // 清理函数
        return () => {
            isMountedRef.current = false
            close()
        }
    }, [url])  // 只在URL变化时重连

    return {
        status,
        error,
        retryCount,
        close,
    }
}
