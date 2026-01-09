/**
 * Analysis API Client - v2 异步任务版本
 *
 * 支持 forecast/rag/news/chat 四种意图
 * 使用轮询方式获取分析结果
 */

export interface CreateAnalysisRequest {
  message: string
  session_id?: string  // 多轮对话时复用
  model?: 'prophet' | 'xgboost' | 'randomforest' | 'dlinear'
  context?: string
  force_intent?: 'forecast' | 'rag' | 'news' | 'chat'  // 强制指定意图
}

export interface TimeSeriesPoint {
  date: string
  value: number
  is_prediction: boolean
}

export interface NewsItem {
  title: string
  summary: string
  date: string
  source: string
  url?: string  // v2 新增：新闻链接
}

export interface ReportItem {
  title: string
  summary: string
  date: string
  source: string
}

export interface RAGSource {
  file_name: string
  page_number: number
  score: number
  content?: string
}

export interface StepDetail {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'error'
  message: string
}

export interface IntentResult {
  intent: string
  reason: string
  tools: {
    forecast: boolean
    report_rag: boolean
    news_rag: boolean
  }
  model: string
  params: {
    history_days: number
    forecast_horizon: number
  }
}

export interface AnalysisSessionData {
  session_id: string
  context: string
  steps: number  // 兼容旧字段
  status: 'pending' | 'processing' | 'completed' | 'error'
  is_time_series: boolean

  // v2 新增：意图相关
  intent: string  // pending/forecast/rag/news/chat
  intent_result: IntentResult | null

  // v2 新增：动态步骤
  total_steps: number
  step_details: StepDetail[]

  // 时序数据
  time_series_original: TimeSeriesPoint[]
  time_series_full: TimeSeriesPoint[]
  prediction_done: boolean
  prediction_start_day: string | null

  // 新闻和研报
  news_list: NewsItem[]
  report_list: ReportItem[]
  rag_sources: RAGSource[]  // v2 新增
  emotion: number | null
  emotion_des: string | null

  // 综合报告
  conclusion: string

  // v2 新增：对话历史
  conversation_history: { role: string; content: string }[]

  // 元数据
  created_at: string
  updated_at: string
  error_message: string | null
  stock_code: string | null
  model_name: string
}

export interface AnalysisStatusResponse {
  session_id: string
  status: 'pending' | 'processing' | 'completed' | 'error'
  steps: number
  data: AnalysisSessionData
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * 创建分析任务 (v2 API)
 */
export async function createAnalysisTask(
  message: string,
  model: string = 'prophet',
  context: string = '',
  sessionId?: string | null,
  forceIntent?: string
): Promise<{ session_id: string; status: string; intent?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v2/analysis/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      model,
      context,
      session_id: sessionId || undefined,
      force_intent: forceIntent
    })
  })

  if (!response.ok) {
    throw new Error(`Failed to create analysis task: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 查询任务状态 (v2 API)
 */
export async function getAnalysisStatus(
  sessionId: string
): Promise<AnalysisStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v2/analysis/status/${sessionId}`)

  if (!response.ok) {
    throw new Error(`Failed to get analysis status: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 删除会话 (v2 API)
 */
export async function deleteAnalysisSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v2/analysis/${sessionId}`, {
    method: 'DELETE'
  })

  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.statusText}`)
  }
}

/**
 * 轮询任务状态直到完成
 *
 * @param sessionId 会话ID
 * @param onUpdate 状态更新回调
 * @param pollInterval 轮询间隔（毫秒）
 */
export async function pollAnalysisStatus(
  sessionId: string,
  onUpdate: (status: AnalysisStatusResponse) => void,
  pollInterval: number = 1500
): Promise<AnalysisStatusResponse> {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const status = await getAnalysisStatus(sessionId)
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
 * 获取意图对应的步骤名称
 */
export function getStepsForIntent(intent: string): { id: string; name: string; icon: string }[] {
  const FORECAST_STEPS = [
    { id: '1', name: '数据获取与预处理', icon: '📊' },
    { id: '2', name: '新闻获取与情绪分析', icon: '📰' },
    { id: '3', name: '时序特征分析', icon: '📈' },
    { id: '4', name: '参数智能推荐', icon: '⚙️' },
    { id: '5', name: '模型训练与预测', icon: '🔮' },
    { id: '6', name: '结果可视化', icon: '📉' },
    { id: '7', name: '报告生成', icon: '📝' },
  ]

  const RAG_STEPS = [
    { id: '1', name: '研报检索', icon: '🔍' },
    { id: '2', name: '生成回答', icon: '💬' },
  ]

  const NEWS_STEPS = [
    { id: '1', name: '新闻搜索', icon: '📰' },
    { id: '2', name: '新闻总结', icon: '📝' },
  ]

  const CHAT_STEPS = [
    { id: '1', name: '生成回答', icon: '💬' },
  ]

  switch (intent) {
    case 'forecast':
      return FORECAST_STEPS
    case 'rag':
      return RAG_STEPS
    case 'news':
      return NEWS_STEPS
    case 'chat':
      return CHAT_STEPS
    default:
      return CHAT_STEPS
  }
}

/**
 * 获取快速追问建议 (v2 API)
 */
export async function getSuggestions(sessionId?: string | null): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v2/analysis/suggestions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId || null,
      }),
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }

    const data = await response.json()
    return data.suggestions || []
  } catch (error) {
    console.error('获取快速追问建议失败:', error)
    // 返回默认建议
    return [
      '帮我分析一下茅台，预测下个季度走势',
      '查看最近的市场趋势',
      '对比几只白酒股的表现',
      '生成一份投资分析报告',
    ]
  }
}
