/**
 * Analysis API Client - 异步任务版本
 *
 * 架构:
 * - Session: 整个多轮对话 (复用同一 session_id)
 * - Message: 每轮 QA (每次查询创建新 message_id)
 *
 * 使用轮询方式获取分析结果
 */

export interface CreateAnalysisRequest {
  message: string
  model: 'prophet' | 'xgboost' | 'randomforest' | 'dlinear'
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

  conclusion: string

  // 思考日志 (累积显示所有 LLM 调用的原始输出)
  thinking_logs: ThinkingLogEntry[]

  created_at: string
  updated_at: string
  error_message: string | null
}

// 兼容旧版类型别名
export type AnalysisSessionData = MessageData

export interface AnalysisStatusResponse {
  session_id: string
  message_id: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  steps: number
  total_steps: number
  data: MessageData
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * 查询任务状态
 *
 * @param sessionId 会话ID
 * @param messageId 消息ID (可选，不传则返回当前正在处理的消息)
 */
export async function getAnalysisStatus(
  sessionId: string,
  messageId?: string | null
): Promise<AnalysisStatusResponse> {
  const url = messageId
    ? `${API_BASE_URL}/api/analysis/status/${sessionId}?message_id=${messageId}`
    : `${API_BASE_URL}/api/analysis/status/${sessionId}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to get analysis status: ${response.statusText}`)
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
 * @returns 会话历史数据
 */
export async function getSessionHistory(sessionId: string): Promise<SessionHistoryResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analysis/history/${sessionId}`)

    if (response.status === 404) {
      // 会话不存在，返回 null
      return null
    }

    if (!response.ok) {
      throw new Error(`Failed to get session history: ${response.statusText}`)
    }

    return response.json()
  } catch (error) {
    console.error('获取会话历史失败:', error)
    return null
  }
}

/**
 * 轮询任务状态直到完成
 *
 * @param sessionId 会话ID
 * @param messageId 消息ID (推荐传入，确保轮询正确的消息)
 * @param onUpdate 状态更新回调
 * @param pollInterval 轮询间隔（毫秒）
 */
export async function pollAnalysisStatus(
  sessionId: string,
  messageId: string | null,
  onUpdate: (status: AnalysisStatusResponse) => void,
  pollInterval: number = 500
): Promise<AnalysisStatusResponse> {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const status = await getAnalysisStatus(sessionId, messageId)
        onUpdate(status)

        if (status.status === 'completed' || status.status === 'error') {
          resolve(status)
        } else {
          setTimeout(poll, pollInterval)
        }
      } catch (error) {
        reject(error)
      }
    }

    poll()
  })
}

/**
 * SSE 流式事件类型
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
  model: string = 'prophet',
  context: string = '',
  sessionId?: string | null
): Promise<{ session_id: string; message_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/analysis/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      model,
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
