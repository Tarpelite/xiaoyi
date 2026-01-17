/**
 * SSE Streaming Analysis API Client (V2)
 * =======================================
 * 
 * 使用新的 /v2/stream/analysis endpoint
 * 通过useSSEStream hook处理真正的实时流式传输
 */

import { useSSEStream, SSEStreamOptions } from '@/hooks/useSSEStream'

export interface StreamAnalysisV2Options {
    message: string
    sessionId?: string | null
    model?: string
    context?: string
    onThinkingChunk?: (chunk: string, accumulated: string) => void
    onThinkingComplete?: (fullThinking: string) => void
    onIntentDetermined?: (intent: any) => void
    onStepUpdate?: (step: number, status: string, message: string) => void
    onError?: (error: string) => void
    onComplete?: () => void
}

/**
 * 使用SSE连接进行流式分析 (V2)
 * 
 * 注意: 这个函数会直接发起POST请求并返回stream URL
 * 应该在组件中使用useSSEStream hook来处理
 */
export async function createStreamAnalysisV2(
    message: string,
    options: {
        sessionId?: string | null
        model?: string
        context?: string
    } = {}
): Promise<string> {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

    const requestBody = {
        message,
        session_id: options.sessionId || undefined,
        model: options.model || 'prophet',
        context: options.context || '',
    }

    // 我们不能直接用fetch + stream，因为FastAPI SSE需要EventSource
    // 所以我们构造URL并让EventSource连接
    const params = new URLSearchParams({
        message,
        ...(options.sessionId && { session_id: options.sessionId }),
        model: options.model || 'prophet',
        context: options.context || ''
    })

    // 注意: SSE通常是GET请求，但我们用的是POST
    // 我们需要换一种方式：先创建session，然后连接stream
    // 或者修改backend支持GET + query params

    // 暂时返回POST endpoint的URL
    // 实际使用时需要backend调整为支持GET或使用不同策略
    return `${API_BASE}/v2/stream/analysis?${params.toString()}`
}

/**
 * Hook: 直接在组件中使用SSE流式分析
 * 
 * 这个设计更符合React hooks模式
 */
export function useStreamAnalysis(
    message: string | null,
    options: Omit<StreamAnalysisV2Options, 'message'> = {}
) {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

    // 构建SSE URL (注意: POST不适合EventSource，这里暂时用GET params)
    const sseUrl = message
        ? `${API_BASE}/v2/stream/analysis?${new URLSearchParams({
            message,
            ...(options.sessionId && { session_id: options.sessionId }),
            model: options.model || 'prophet',
            context: options.context || ''
        }).toString()}`
        : null

    const sseOptions: SSEStreamOptions = {
        onThinkingChunk: (data) => {
            options.onThinkingChunk?.(data.chunk, data.accumulated)
        },
        onThinkingComplete: (data) => {
            options.onThinkingComplete?.(data.thinking_content)
        },
        onIntentDetermined: (data) => {
            options.onIntentDetermined?.(data)
        },
        onStepUpdate: (data) => {
            options.onStepUpdate?.(data.step, data.status, data.message)
        },
        onError: (data) => {
            options.onError?.(data.error)
        },
        onAnalysisComplete: () => {
            options.onComplete?.()
        },
    }

    return useSSEStream(sseUrl, sseOptions)
}
