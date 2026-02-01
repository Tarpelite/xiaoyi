/**
 * Analysis API Client - 异步任务版本
 *
 * 架构:
 * - Session: 整个多轮对话 (复用同一 session_id)
 * - Message: 每轮 QA (每次查询创建新 message_id)
 *
 * 核心 API:
 * - createAnalysis(): 创建后台任务
 * - resumeStream(): 追赶历史事件 + 订阅实时事件 (SSE)
 * - getSessionHistory(): 刷新后恢复已完成的历史消息
 */

export interface CreateAnalysisRequest {
  message: string
  model?: string | null  // 可选，null 表示自动选择
  context?: string
  session_id?: string  // 多轮对话时传入
}

export interface CreateAnalysisResponse {
  session_id: string
  message_id: string
  status: string
}

export interface TimeSeriesPoint {
  date: string
  value: number
  is_prediction: boolean
}

export interface NewsItem {
  summarized_title: string
  summarized_content: string
  original_title: string
  url: string
  published_date: string    // 格式化后的时间，如 "01-16 14:00"
  source_type: string       // "search" | "domain_info"
  source_name: string       // 来源名称，如 "东方财富"、"sina.com.cn"
}

export interface RAGSource {
  filename: string        // "茅台2024研报.pdf"
  page: number           // 页码
  content_snippet: string // 摘要片段
  score: number          // 相关度分数 (0-1)
}

export interface ReportItem {
  title: string
  viewpoint: string      // LLM 提取的观点
  source: RAGSource      // 来源信息
}

export interface EmotionData {
  score: number  // -1 到 1
  description: string
}

export interface ThinkingLogEntry {
  step_id: string        // 步骤 ID，如 "intent", "sentiment", "report"
  step_name: string      // 步骤名称，如 "意图识别", "情感分析", "报告生成"
  content: string        // LLM 原始输出内容
  timestamp: string      // ISO 格式时间戳
}

export interface UnifiedIntent {
  is_in_scope: boolean
  is_forecast: boolean
  enable_rag: boolean
  enable_search: boolean
  enable_domain_info: boolean
  stock_mention: string | null
  raw_search_keywords: string[]
  raw_rag_keywords: string[]
  raw_domain_keywords: string[]
  forecast_model: string
  history_days: number
  forecast_horizon: number
  reason: string
  out_of_scope_reply: string | null
}

/**
 * 消息数据 (单轮 QA 的分析结果)
 */
export interface MessageData {
  message_id: string
  session_id: string
  user_query: string

  steps: number
  total_steps: number
  status: 'pending' | 'processing' | 'completed' | 'error'

  // 意图识别
  intent: string  // "forecast" | "chat" | "rag" | "news" | "out_of_scope" | "pending"
  unified_intent: UnifiedIntent | null

  time_series_original: TimeSeriesPoint[]
  time_series_full: TimeSeriesPoint[]
  prediction_done: boolean
  prediction_start_day: string | null

  news_list: NewsItem[]
  report_list: ReportItem[]
  rag_sources: RAGSource[]  // RAG 研报来源
  emotion: number | null
  emotion_des: string | null

  // 异常区域（关键转折点标注）
  anomaly_zones: Array<{
    startDate: string
    endDate: string
    summary: string
    sentiment: 'positive' | 'negative'
  }>
  anomaly_zones_ticker: string | null

  // 历史语义区间 (Added)
  semantic_zones?: Array<any>

  // 预测语义区间 (Added)
  prediction_semantic_zones?: Array<any>

  // 异常点（显著转折点）
  anomalies?: Array<{
    date: string
    price: number
    score: number
    description: string
    method: string
  }>

  conclusion: string

  // 思考日志 (累积显示所有 LLM 调用的原始输出)
  thinking_logs: ThinkingLogEntry[]

  created_at: string
  updated_at: string
  error_message: string | null
}

// 兼容旧版类型别名
export type AnalysisSessionData = MessageData

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * 创建分析任务（后台独立运行）
 *
 * 任务通过后端 BackgroundTasks 独立运行，不依赖前端连接。
 * 前端刷新后，后端任务不受影响。
 *
 * @param message 用户问题
 * @param options 选项（model, sessionId）
 * @returns { session_id, message_id, status }
 */
export async function createAnalysis(
  message: string,
  options?: { model?: string; sessionId?: string | null }
): Promise<CreateAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analysis/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      model: options?.model ?? null,  // null 表示自动选择
      session_id: options?.sessionId || null
    })
  })

  if (!response.ok) {
    throw new Error(`Failed to create analysis: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 会话历史中的单条消息
 */
export interface HistoryMessage {
  message_id: string
  user_query: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  data: MessageData
}

/**
 * 会话历史响应
 */
export interface SessionHistoryResponse {
  session_id: string
  messages: HistoryMessage[]
}

/**
 * 获取会话历史（用于页面刷新后恢复）
 *
 * @param sessionId 会话ID
 * @param signal 可选的 AbortSignal，用于取消请求
 * @returns 会话历史数据
 */
export async function getSessionHistory(
  sessionId: string,
  signal?: AbortSignal
): Promise<SessionHistoryResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analysis/history/${sessionId}`, {
      signal
    })

    if (response.status === 404) {
      // 会话不存在，返回 null
      return null
    }

    if (!response.ok) {
      throw new Error(`Failed to get session history: ${response.statusText}`)
    }

    return response.json()
  } catch (error) {
    // 如果是取消请求，直接抛出让调用方处理
    if (error instanceof Error && error.name === 'AbortError') {
      throw error
    }
    console.error('获取会话历史失败:', error)
    throw error
  }
}

/**
 * SSE 流式事件类型（旧版，仅思考流式）
 */
export interface StreamEvent {
  type: 'session' | 'thinking' | 'intent' | 'done' | 'error'
  session_id?: string
  message_id?: string
  content?: string  // thinking content chunk
  intent?: string
  is_forecast?: boolean
  reason?: string
  completed?: boolean
  message?: string  // error message
}

/**
 * 完全流式 SSE 事件类型
 */
export interface FullStreamEvent {
  type: 'session' | 'step_start' | 'step_progress' | 'step_complete' | 'thinking' | 'data' | 'report_chunk' | 'chat_chunk' | 'emotion_chunk' | 'intent' | 'heartbeat' | 'done' | 'error' | 'resume'
  session_id?: string
  message_id?: string
  step?: number
  step_name?: string
  content?: string
  data_type?: 'time_series_original' | 'time_series_full' | 'news' | 'emotion' | 'anomaly_zones'
  data?: unknown
  prediction_start_day?: string
  intent?: string
  is_forecast?: boolean
  reason?: string
  completed?: boolean
  message?: string
  current_data?: MessageData
}

/**
 * 流式分析回调接口
 */
export interface StreamCallbacks {
  onThinking?: (content: string) => void  // 思考内容累积
  onIntent?: (intent: string, isForecast: boolean, reason: string) => void
  onError?: (message: string) => void
}

/**
 * 流式分析任务 - 使用 SSE 获取思考内容
 *
 * 流程:
 * 1. 连接 SSE 端点
 * 2. 接收 session/message_id
 * 3. 实时接收思考内容
 * 4. 接收意图识别结果
 * 5. 返回 session_id 和 message_id 供后续轮询使用
 *
 * @param message 用户问题
 * @param callbacks 流式回调函数
 * @param model 预测模型
 * @param context 上下文
 * @param sessionId 会话ID (多轮对话时传入)
 * @returns { session_id, message_id } 用于后续轮询
 */
export async function streamAnalysisTask(
  message: string,
  callbacks: StreamCallbacks,
  model?: string | null,  // 可选，null 表示自动选择
  context: string = '',
  sessionId?: string | null
): Promise<{ session_id: string; message_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/analysis/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      model: model ?? null,  // null 表示自动选择
      context,
      session_id: sessionId || null
    })
  })

  if (!response.ok) {
    throw new Error(`Failed to start streaming analysis: ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('No response body')
  }

  let buffer = ''
  let sessionIdResult = ''
  let messageIdResult = ''
  let thinkingContent = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue

        if (line.startsWith('data: ')) {
          try {
            const event: StreamEvent = JSON.parse(line.slice(6))

            switch (event.type) {
              case 'session':
                sessionIdResult = event.session_id || ''
                messageIdResult = event.message_id || ''
                break

              case 'thinking':
                if (event.content) {
                  thinkingContent += event.content
                  callbacks.onThinking?.(thinkingContent)
                }
                break

              case 'intent':
                callbacks.onIntent?.(
                  event.intent || '',
                  event.is_forecast || false,
                  event.reason || ''
                )
                break

              case 'error':
                callbacks.onError?.(event.message || 'Unknown error')
                break

              case 'done':
                // Stream completed, backend continues in background
                break
            }
          } catch (e) {
            console.error('Parse SSE event error:', e, 'Line:', line)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  if (!sessionIdResult || !messageIdResult) {
    throw new Error('Stream ended without session/message IDs')
  }

  return { session_id: sessionIdResult, message_id: messageIdResult }
}

/**
 * 完全流式分析回调接口
 */
export interface FullStreamCallbacks {
  onSession?: (sessionId: string, messageId: string) => void
  onStepStart?: (step: number, stepName: string) => void
  onStepComplete?: (step: number, data: Record<string, unknown>) => void
  onThinking?: (content: string) => void
  onIntent?: (intent: string, isForecast: boolean, reason: string) => void
  onData?: (dataType: string, data: unknown, predictionStartDay?: string, fullEvent?: any) => void
  onReportChunk?: (content: string) => void
  onChatChunk?: (content: string) => void
  onEmotionChunk?: (content: string) => void
  onHeartbeat?: () => void
  onDone?: (completed: boolean) => void
  onError?: (message: string) => void
  onResume?: (currentData: MessageData) => void
}

/**
 * 恢复流式会话（断点续传）
 *
 * @param sessionId 会话 ID
 * @param messageId 消息 ID
 * @param callbacks 流式回调函数
 * @param lastEventId 最后接收的事件 ID（可选，用于从特定位置恢复）
 * @returns 如果任务已完成，返回当前数据；否则通过 SSE 继续接收
 */
export async function resumeStream(
  sessionId: string,
  messageId: string,
  callbacks: FullStreamCallbacks,
  lastEventId?: string,
  signal?: AbortSignal
): Promise<{ completed: boolean; data?: MessageData }> {
  let url = `${API_BASE_URL}/api/analysis/stream-resume/${sessionId}?message_id=${messageId}`
  if (lastEventId) {
    url += `&last_event_id=${encodeURIComponent(lastEventId)}`
  }
  const response = await fetch(url, { signal })

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Session or message not found')
    }
    throw new Error(`Failed to resume stream: ${response.statusText}`)
  }

  // 检查 Content-Type 确定是 JSON 还是 SSE
  const contentType = response.headers.get('Content-Type') || ''

  if (contentType.includes('application/json')) {
    // 任务已完成，返回 JSON 数据
    const result = await response.json()
    return {
      completed: result.status !== 'streaming',
      data: result.data
    }
  }

  // SSE 流式返回
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('No response body')
  }

  let buffer = ''

  try {
    while (true) {
      // 检查是否已被中止
      if (signal?.aborted) {
        return { completed: false }
      }

      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue

        if (line.startsWith('data: ')) {
          try {
            const event: FullStreamEvent = JSON.parse(line.slice(6))
            // console.log('[SSE] Raw event:', event.type, event.data_type, event)

            switch (event.type) {
              case 'resume':
                if (event.current_data) {
                  callbacks.onResume?.(event.current_data)
                }
                break

              case 'step_start':
                callbacks.onStepStart?.(event.step || 0, event.step_name || '')
                break

              case 'step_complete':
                callbacks.onStepComplete?.(event.step || 0, event.data as Record<string, unknown> || {})
                break

              case 'thinking':
                callbacks.onThinking?.(event.content || '')
                break

              case 'data':
                // console.log('[SSE] Data event - type:', event.data_type, 'data:', event.data)
                // Pass the complete event so ChatArea can extract semantic_zones, anomalies, etc.
                callbacks.onData?.(
                  event.data_type || '',
                  event.data,
                  event.prediction_start_day,
                  event as any // Pass full event for additional fields
                )
                break

              case 'report_chunk':
                callbacks.onReportChunk?.(event.content || '')
                break

              case 'chat_chunk':
                callbacks.onChatChunk?.(event.content || '')
                break

              case 'emotion_chunk':
                callbacks.onEmotionChunk?.(event.content || '')
                break

              case 'done':
                callbacks.onDone?.(event.completed || false)
                return { completed: true }

              case 'error':
                callbacks.onError?.(event.message || 'Unknown error')
                return { completed: true }
            }
          } catch (e) {
            console.error('Parse SSE event error:', e, 'Line:', line)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  return { completed: true }
}
