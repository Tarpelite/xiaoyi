/**
 * Analysis API Client - 异步任务版本
 * 
 * 使用轮询方式获取分析结果
 */

export interface CreateAnalysisRequest {
  message: string
  model: 'prophet' | 'xgboost' | 'randomforest' | 'dlinear'
  context?: string
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
}

export interface ReportItem {
  title: string
  summary: string
  date: string
  source: string
}

export interface EmotionData {
  score: number  // -1 到 1
  description: string
}

export interface AnalysisSessionData {
  session_id: string
  context: string
  steps: number
  status: 'pending' | 'processing' | 'completed' | 'error'
  is_time_series: boolean

  time_series_original: TimeSeriesPoint[]
  time_series_full: TimeSeriesPoint[]
  prediction_done: boolean
  prediction_start_day: string | null

  news_list: NewsItem[]
  report_list: ReportItem[]
  emotion: number | null
  emotion_des: string | null

  conclusion: string

  // 对话模式（数据获取失败时）
  conversational_response: string
  error_type: string | null

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
 * 创建分析任务
 */
export async function createAnalysisTask(
  message: string,
  model: string = 'prophet',
  context: string = '',
  sessionId?: string | null
): Promise<{ session_id: string; status: string; intent?: string }> {
  // 如果有 sessionId，将其添加到 context 中
  const contextWithSession = sessionId ? `session_id:${sessionId}` : context

  const response = await fetch(`${API_BASE_URL}/api/analysis/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, model, context: contextWithSession })
  })

  if (!response.ok) {
    throw new Error(`Failed to create analysis task: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 查询任务状态
 */
export async function getAnalysisStatus(
  sessionId: string
): Promise<AnalysisStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/analysis/status/${sessionId}`)

  if (!response.ok) {
    throw new Error(`Failed to get analysis status: ${response.statusText}`)
  }

  return response.json()
}

/**
 * 删除会话
 */
export async function deleteAnalysisSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/analysis/${sessionId}`, {
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
  pollInterval: number = 2000
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
