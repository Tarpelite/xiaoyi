'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { Download, Share2, MoreVertical, Paperclip, Send, Zap, ChevronDown, ChevronRight } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { QuickSuggestions } from './QuickSuggestions'
import { AnalysisCards } from './AnalysisCards'
import { cn } from '@/lib/utils'

// 步骤状态
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed'

// 步骤定义
export interface Step {
  id: string
  name: string
  status: StepStatus
  message?: string
}

// 消息内容类型
export type MessageContentType = 'text' | 'chart' | 'table'

// 文本内容
export interface TextContent {
  type: 'text'
  text: string
}

// 图表内容
export interface ChartContent {
  type: 'chart'
  title?: string
  data: {
    labels: string[]
    datasets: {
      label: string
      data: (number | null)[]
      color?: string
    }[]
  }
  chartType?: 'line' | 'bar' | 'area'
  // 回测功能字段
  sessionId?: string
  messageId?: string
  originalData?: Array<{ date: string; value: number; is_prediction: boolean }>
}

// 表格内容
export interface TableContent {
  type: 'table'
  title?: string
  headers: string[]
  rows: (string | number)[][]
}

// 意图识别结果
export interface IntentInfo {
  intent: 'analyze' | 'answer'
  reason: string
}

// 渲染模式：根据 intent 决定 UI 渲染方式
export type RenderMode = 'thinking' | 'forecast' | 'chat'

// 消息类型定义
export interface Message {
  id: string
  role: 'user' | 'assistant'
  timestamp: string
  // 内容（支持多种类型，可以是单个或多个）
  content?: TextContent | ChartContent | TableContent
  contents?: (TextContent | ChartContent | TableContent)[]
  // 旧版兼容：纯文本内容
  text?: string
  // 步骤进度（仅assistant消息）
  steps?: Step[]
  // 意图识别结果（仅assistant消息）
  intentInfo?: IntentInfo
  // 分析结果附件（可选，保留兼容）
  analysis?: {
    reportConsensus?: {
      totalReports: number
      ratings: { buy: number; hold: number; sell: number }
      avgTargetPrice: number
      currentPrice: number
    }
    modelPrediction?: {
      model: string
      prediction: number
      mase: number
      confidenceInterval: [number, number]
    }
    anomalyDetection?: {
      count: number
      anomalies: { date: string; change: number }[]
    }
  }
  // 对话模式标志
  isConversationalMode?: boolean
  isCollapsing?: boolean
  // 渲染模式：thinking(思考中) / forecast(预测分析) / chat(简单对话)
  renderMode?: RenderMode
  // 思考过程内容（LLM 实时推理）
  thinkingContent?: string
}

// 预测步骤定义（6个步骤）- 与后端 FORECAST_STEPS 保持一致
export const PREDICTION_STEPS: Omit<Step, 'status' | 'message'>[] = [
  { id: '1', name: '意图识别' },
  { id: '2', name: '股票验证' },
  { id: '3', name: '数据获取' },
  { id: '4', name: '分析处理' },
  { id: '5', name: '模型预测' },
  { id: '6', name: '报告生成' },
]

// 默认快速追问建议
const defaultQuickSuggestions = [
  '帮我分析一下茅台，预测下个季度走势',
  '查看最近的市场趋势',
  '对比几只白酒股的表现',
  '生成一份投资分析报告',
]

// 从 localStorage 获取或生成 session_id
function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return ''

  const stored = localStorage.getItem('chat_session_id')
  if (stored) {
    return stored
  }

  // 生成新的 session_id
  const newSessionId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  localStorage.setItem('chat_session_id', newSessionId)
  return newSessionId
}

interface ChatAreaProps {
  sessionId: string | null
}

export function ChatArea({ sessionId: externalSessionId }: ChatAreaProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => externalSessionId || getOrCreateSessionId())
  const [quickSuggestions, setQuickSuggestions] = useState<string[]>(defaultQuickSuggestions)

  // 对话模式动画状态 (针对最后一条消息)
  const [lastMessageConversationalMode, setLastMessageConversationalMode] = useState(false)
  const [lastMessageCollapsing, setLastMessageCollapsing] = useState(false)

  // 对话区域滚动容器 ref
  const chatContainerRef = useRef<HTMLDivElement>(null)

  // 跟踪当前消息是否已经滚动过（用于控制只滚动两次：发送时+开始产生内容时）
  const hasScrolledForContentRef = useRef(false)

  // 防止 React 严格模式下重复加载历史
  const historyLoadedRef = useRef(false)

  // 跟踪当前活跃的轮询消息（支持多会话并发）
  // Key: sessionId, Value: messageId
  const activePollingMapRef = useRef<Map<string, string>>(new Map())

  // 自动滚动到底部
  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth'
      })
    }
  }

  // 检测对话模式并触发坍缩动画
  useEffect(() => {
    if (messages.length === 0) return

    const lastMessage = messages[messages.length - 1]
    if (lastMessage.role !== 'assistant') return

    // 检查最后一条助手消息的内容
    const lastContent = lastMessage.contents?.[0]
    const messageText = lastContent?.type === 'text' ? lastContent.text : ''

    // 通过检查消息开头判断是否是对话模式（conversational_response）
    // 实际应该通过 data 字段，但消息中没有保存原始 data
    // 所以我们检测：如果只有文本且包含"抱歉"等关键词
    const looksLikeConversational =
      lastMessage.contents?.length === 1 &&
      lastContent?.type === 'text' &&
      (messageText.includes('抱歉') || messageText.includes('无法获取') || messageText.includes('数据不存在'))

    if (looksLikeConversational && !lastMessage.steps) {
      // 可能是对话模式，触发坍缩
      if (!lastMessageConversationalMode) {
        setLastMessageCollapsing(true)
        setTimeout(() => {
          setLastMessageConversationalMode(true)
          setLastMessageCollapsing(false)
        }, 800)
      }
    } else {
      // 重置状态
      setLastMessageConversationalMode(false)
      setLastMessageCollapsing(false)
    }
  }, [messages])

  // 构建对话历史（从 messages 中提取）
  const buildHistory = (): Array<{ role: string; content: string }> => {
    const history: Array<{ role: string; content: string }> = []

    for (const msg of messages) {
      if (msg.role === 'user' && msg.text) {
        history.push({ role: 'user', content: msg.text })
      } else if (msg.role === 'assistant' && msg.contents) {
        // 提取助手回复的文本内容
        const textContents = msg.contents.filter(c => c.type === 'text') as TextContent[]
        if (textContents.length > 0) {
          const combinedText = textContents.map(c => c.text).join('\n\n')
          history.push({ role: 'assistant', content: combinedText })
        }
      }
    }

    return history
  }

  // 当外部 sessionId 变化时，更新内部状态
  useEffect(() => {
    // 只在真正切换会话时才处理（externalSessionId变化）
    // 不处理内部sessionId的自然更新（如发送首条消息时）
    if (externalSessionId && externalSessionId !== sessionId) {
      console.log('[ChatArea] Switching to session:', externalSessionId)
      setSessionId(externalSessionId)
      // 不立即清空messages，让loadSessionHistory处理
      historyLoadedRef.current = false
      // 清除这个会话的轮询跟踪（但不影响其他会话）
      if (sessionId) {
        activePollingMapRef.current.delete(sessionId)
      }
    } else if (externalSessionId === null && sessionId) {
      // 新建会话（用户点击New Chat）
      console.log('[ChatArea] Creating new session')
      const newSessionId = getOrCreateSessionId()
      setSessionId(newSessionId)
      setMessages([]) // 新会话才清空
      historyLoadedRef.current = false
      // 清除旧会话的轮询跟踪
      if (sessionId) {
        activePollingMapRef.current.delete(sessionId)
      }
    }
  }, [externalSessionId]) // 只监听externalSessionId，不监听sessionId

  // 页面加载时恢复会话历史
  useEffect(() => {
    const loadSessionHistory = async () => {
      console.log("🔄 [loadSessionHistory] CALLED", { sessionId })
      // 防止 React 严格模式下重复加载
      if (historyLoadedRef.current) return
      historyLoadedRef.current = true

      if (!sessionId) return

      try {
        console.log('[loadSessionHistory] Fetching history for session:', sessionId)
        const { getSessionHistory } = await import('@/lib/api/analysis')
        const history = await getSessionHistory(sessionId)
        console.log('[loadSessionHistory] Got history:', history)

        // 将后端历史消息转换为前端 Message 格式
        const loadedMessages: Message[] = []
        let processingMessageId: string | null = null
        let processingSessionId: string | null = null

        if (history && history.messages && history.messages.length > 0) {
          for (const historyMsg of history.messages) {
            // 用户消息
            if (historyMsg.user_query) {
              loadedMessages.push({
                id: `user-${historyMsg.message_id}`,
                role: 'user',
                text: historyMsg.user_query,
                timestamp: new Date(historyMsg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
              })
            }

            // 助手消息
            if (historyMsg.status === 'completed' && historyMsg.data) {
              const data = historyMsg.data
              const isForecastIntent = data.intent === 'forecast' ||
                (data.unified_intent && data.unified_intent.is_forecast)

              // 转换内容
              const contents = convertAnalysisToContents(data, data.steps, 'completed')

              loadedMessages.push({
                id: `assistant-${historyMsg.message_id}`,
                role: 'assistant',
                timestamp: new Date(data.updated_at || data.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                contents: contents.length > 0 ? contents : [{
                  type: 'text',
                  text: data.conclusion || '已完成分析'
                }],
                renderMode: isForecastIntent ? 'forecast' : 'chat',
              })
            }
            // 🆕 检测processing或pending状态的消息（都需要auto-resume）
            else if (historyMsg.status === 'processing' || historyMsg.status === 'pending') {
              console.log('[Auto-Resume] Found incomplete message:', historyMsg.message_id, 'status:', historyMsg.status)
              console.log('[Auto-Resume] Message data:', historyMsg)
              processingMessageId = historyMsg.message_id
              processingSessionId = historyMsg.data.session_id

              // 创建占位符消息
              const assistantMessage: Message = {
                id: `assistant-${historyMsg.message_id}`,
                role: 'assistant',
                timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                renderMode: 'thinking',
                thinkingContent: historyMsg.thinking_content || ((historyMsg.data as any)?.thinking_content) || ''
              }
              console.log('[Auto-Resume] Created placeholder with thinking:', assistantMessage.thinkingContent?.length || 0, 'chars')
              loadedMessages.push(assistantMessage)
            }
          }
        }

        setMessages(loadedMessages)

        console.log("[Auto-Resume] Checking for reconnect:", { processingMessageId, processingSessionId })
        // 🆕 Auto-resume: 如果发现processing消息，自动重连SSE
        if (processingMessageId && processingSessionId) {
          console.log('[Auto-Resume] Reconnecting to SSE for message:', processingMessageId)
          setIsLoading(true)

          // 订阅SSE流
          const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''
          const sseUrl = `${API_BASE}/api/v2/stream/subscribe/${processingMessageId}?session_id=${processingSessionId}`
          const eventSource = new EventSource(sseUrl)

          const assistantMessageId = `assistant-${processingMessageId}`

          // Thinking chunks
          eventSource.addEventListener('thinking_chunk', (event: MessageEvent) => {
            const data = JSON.parse(event.data)
            const thinkingContent = data.accumulated || data.data?.accumulated || ''

            setMessages((prev: Message[]) => prev.map((msg: Message) =>
              msg.id === assistantMessageId
                ? { ...msg, thinkingContent }
                : msg
            ))
          })

          // Intent determined
          eventSource.addEventListener('intent_determined', (event: MessageEvent) => {
            const data = JSON.parse(event.data)
            const isForecast = data.is_forecast || data.data?.is_forecast || false
            const renderMode: RenderMode = isForecast ? 'forecast' : 'chat'

            setMessages((prev: Message[]) => prev.map((msg: Message) =>
              msg.id === assistantMessageId
                ? { ...msg, renderMode }
                : msg
            ))
          })

          // Analysis complete
          eventSource.addEventListener('analysis_complete', async () => {
            console.log('[Auto-Resume] Analysis complete')
            eventSource.close()
            setIsLoading(false)

            // 获取最终结果
            try {
              const { getAnalysisStatus } = await import('@/lib/api/analysis')
              const finalResult = await getAnalysisStatus(processingSessionId, processingMessageId)

              const isForecast = finalResult.data?.is_forecast || finalResult.data?.unified_intent?.is_forecast || false
              const conclusion = finalResult.data?.conclusion || (finalResult.data as any)?.chat_response || ''

              setMessages((prev: Message[]) => prev.map((msg: Message) =>
                msg.id === assistantMessageId
                  ? {
                    ...msg,
                    contents: conclusion ? [{
                      type: 'text' as const,
                      text: conclusion
                    }] : msg.contents || [],
                    renderMode: isForecast ? 'forecast' : 'chat'
                  }
                  : msg
              ))
            } catch (error) {
              console.error('[Auto-Resume] Failed to fetch final result:', error)
            }
          })

          eventSource.onerror = () => {
            console.error('[Auto-Resume] SSE error')
            eventSource.close()
            setIsLoading(false)
          }
        }

      } catch (error) {
        console.error('[ChatArea] Failed to load session history:', error)
        // 加载失败时也清空消息，避免显示错误的内容
        setMessages([])
      }
    }

    loadSessionHistory()
  }, [sessionId]) // 依赖 sessionId，当 sessionId 变化时重新加载

  // 更新快速追问建议（在对话完成后）
  useEffect(() => {
    const updateSuggestions = async () => {
      // 只有在有消息、不在加载中、且有sessionId时才更新
      if (messages.length > 0 && !isLoading && sessionId) {
        try {
          const { getSuggestions } = await import('@/lib/api/chat')
          const suggestions = await getSuggestions(sessionId)
          if (suggestions && suggestions.length > 0) {
            setQuickSuggestions(suggestions)
          }
        } catch (error) {
          console.error('更新快速追问建议失败:', error)
        }
      }
    }

    // 延迟更新，确保消息已完全处理（等待加载完成）
    if (!isLoading) {
      const timer = setTimeout(updateSuggestions, 800)
      return () => clearTimeout(timer)
    }
  }, [messages.length, isLoading, sessionId])

  // 将后端的步骤数转换为前端的 Step[] 数组
  const convertSteps = (currentStep: number, totalSteps: number = 6, status: string): Step[] => {
    return PREDICTION_STEPS.map((step, index) => {
      const stepNum = index + 1
      if (stepNum < currentStep) {
        return { ...step, status: 'completed' as StepStatus, message: '已完成' }
      } else if (stepNum === currentStep && status === 'processing') {
        return { ...step, status: 'running' as StepStatus, message: '处理中...' }
      } else if (status === 'completed' && stepNum <= totalSteps) {
        return { ...step, status: 'completed' as StepStatus, message: '已完成' }
      } else if (status === 'error') {
        return { ...step, status: 'failed' as StepStatus, message: '失败' }
      } else {
        return { ...step, status: 'pending' as StepStatus }
      }
    })
  }

  // 将 AnalysisStatusResponse 转换为前端的 contents
  const convertAnalysisToContents = (
    data: {
      time_series_original?: Array<{ date: string; value: number; is_prediction: boolean }>
      time_series_full?: Array<{ date: string; value: number; is_prediction: boolean }>
      prediction_done?: boolean
      emotion?: number | null
      emotion_des?: string | null
      news_list?: Array<{
        summarized_title: string
        summarized_content: string
        original_title: string
        url: string
        published_date: string
        source_type: string
      }>
      conclusion?: string
      is_time_series?: boolean
      conversational_response?: string
      session_id?: string
      message_id?: string
    },
    currentStep: number = 0,
    status: string = 'pending'
  ): (TextContent | ChartContent | TableContent)[] => {
    const contents: (TextContent | ChartContent | TableContent)[] = []

    // 🎯 对话模式：数据获取失败，显示 AI 友好解释
    if (data.is_time_series === false && data.conversational_response) {
      contents.push({
        type: 'text',
        text: data.conversational_response
      })
      return contents
    }

    // 判断是否是简单问答：只有 conclusion，没有其他结构化数据
    const isSimpleAnswer = data.conclusion &&
      (!data.time_series_full || data.time_series_full.length === 0) &&
      (!data.emotion || data.emotion === null) &&
      (!data.news_list || data.news_list.length === 0)

    // 如果是简单问答，只返回文本内容，不生成结构化数据
    if (isSimpleAnswer) {
      if (data.conclusion) {
        contents.push({
          type: 'text',
          text: data.conclusion
        })
      }
      return contents
    }

    // 结构化回答：根据当前步骤生成内容（只显示已完成步骤的内容）
    // 后端 6 步：1-意图识别, 2-股票验证, 3-数据获取, 4-分析处理, 5-模型预测, 6-报告生成
    const isCompleted = status === 'completed' || currentStep >= 6

    // 1. 市场情绪（步骤4"分析处理"完成后显示）
    if (currentStep >= 4 || isCompleted) {
      if (data.emotion !== null && data.emotion !== undefined && typeof data.emotion === 'number' && data.emotion_des) {
        // 使用后端返回的真实数据
        contents.push({
          type: 'text',
          text: `__EMOTION_MARKER__${data.emotion}__${data.emotion_des}__`
        })
      } else if (isCompleted) {
        // 已完成但无数据，使用模拟数据
        const mockEmotion = Math.random() * 0.6 + 0.2 // 0.2 到 0.8 之间
        const mockDescription = '市场情绪分析中，基于新闻和技术指标综合评估'
        contents.push({
          type: 'text',
          text: `__EMOTION_MARKER__${mockEmotion}__${mockDescription}__`
        })
      }
      // 如果步骤 < 5，不添加情绪内容（MessageBubble 会显示"情绪分析中..."）
    }

    // 2. 新闻列表表格（步骤3"数据获取"完成后显示）
    // 显示全部新闻（最多10条：5条AkShare + 5条Tavily）
    if ((currentStep >= 3 || isCompleted) && data.news_list && data.news_list.length > 0) {
      contents.push({
        type: 'table',
        title: '', // 标题由外层MessageBubble显示"相关新闻"，这里不重复显示
        headers: ['标题', '来源', '日期'],
        rows: data.news_list.slice(0, 10).map((news) => [
          // 如果有 URL，使用 markdown 链接格式 [标题](url)；否则只显示标题
          news.url ? `[${news.summarized_title}](${news.url})` : news.summarized_title,
          news.source_type === 'search' ? '网络搜索' : '领域资讯',
          news.published_date
        ])
      })
    }

    // 3. 价格走势图表（分步渲染）
    // 步骤3"数据获取"后：如果有原始数据，先渲染历史价格
    if ((currentStep >= 3 || isCompleted) && data.time_series_original && data.time_series_original.length > 0) {
      const hasForecast = data.prediction_done && data.time_series_full && data.time_series_full.length > 0

      // 步骤5"模型预测"后：同时显示历史和预测价格
      if (hasForecast && (currentStep >= 5 || isCompleted) && data.time_series_full) {
        // 步骤6+：同时显示历史和预测价格
        const originalLength = data.time_series_original.length
        const allLabels = data.time_series_full.map((p) => p.date)
        // 历史价格：包含到最后一个历史数据点，之后为null
        const historicalData = data.time_series_full.map((p, idx) =>
          idx < originalLength ? p.value : null
        )
        // 预测价格：从最后一个历史数据点开始（使用历史价格的最后一个值），之后为预测值
        const lastHistoricalValue = data.time_series_full[originalLength - 1]?.value
        const forecastData = data.time_series_full.map((p, idx) => {
          if (idx < originalLength - 1) {
            return null
          } else if (idx === originalLength - 1) {
            // 交接点：使用历史价格的最后一个值，使两条曲线连接
            return lastHistoricalValue
          } else {
            // 预测值
            return p.value
          }
        })

        contents.push({
          type: 'chart',
          title: '', // 标题由外层MessageBubble显示"价格走势分析"，这里不重复显示
          data: {
            labels: allLabels,
            datasets: [
              {
                label: '历史价格',
                data: historicalData,
                color: '#8b5cf6'
              },
              {
                label: '预测价格',
                data: forecastData,
                color: '#06b6d4'
              }
            ]
          },
          // 回测功能字段
          sessionId: data.session_id,
          messageId: data.message_id,
          originalData: data.time_series_original
        })
      } else {
        // 步骤2-5：只显示历史价格
        const historicalLabels = data.time_series_original.map((p) => p.date)
        const historicalData = data.time_series_original.map((p) => p.value)

        contents.push({
          type: 'chart',
          title: '', // 标题由外层MessageBubble显示"价格走势分析"，这里不重复显示
          data: {
            labels: historicalLabels,
            datasets: [
              {
                label: '历史价格',
                data: historicalData,
                color: '#8b5cf6'
              }
            ]
          },
          // 回测功能字段
          sessionId: data.session_id,
          messageId: data.message_id,
          originalData: data.time_series_original
        })
      }
    }

    // 4. 综合分析报告（步骤6"报告生成"完成后显示）
    if ((currentStep >= 6 || isCompleted) && data.conclusion) {
      contents.push({
        type: 'text',
        text: data.conclusion
      })
    }

    return contents
  }

  const handleSend = async (messageOverride?: string) => {
    const messageToSend = messageOverride || inputValue
    if (!messageToSend.trim() || isLoading) return

    // Create user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: messageToSend,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev: Message[]) => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    setTimeout(scrollToBottom, 50)
    hasScrolledForContentRef.current = false

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const currentSessionId = sessionId || `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

      if (!sessionId) {
        setSessionId(currentSessionId)
        if (typeof window !== 'undefined') {
          localStorage.setItem('chat_session_id', currentSessionId)
        }
      }

      // 🚀 Step 1: Trigger background worker
      console.log('[Pub/Sub] Triggering worker...')
      const startResponse = await fetch(
        `${API_BASE}/api/v2/analysis/start?message=${encodeURIComponent(messageToSend)}&session_id=${currentSessionId}&model=prophet&context=`
      )

      if (!startResponse.ok) {
        throw new Error('Failed to start analysis')
      }

      const { message_id: currentMessageId } = await startResponse.json()
      console.log('[Pub/Sub] Worker started, message_id:', currentMessageId)

      // Create assistant message placeholder
      const assistantMessageId = `assistant-${currentMessageId}`
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        contents: [],
        renderMode: 'thinking',
      }

      setMessages((prev: Message[]) => [...prev, assistantMessage])

      // 🎧 Step 2: Subscribe to SSE stream
      console.log('[Pub/Sub] Subscribing to stream...')
      const sseUrl = `${API_BASE}/api/v2/stream/subscribe/${currentMessageId}?session_id=${currentSessionId}`
      console.log('[Pub/Sub] SSE URL:', sseUrl)
      const eventSource = new EventSource(sseUrl)

      console.log('[Pub/Sub] EventSource created, readyState:', eventSource.readyState)

      // Log when connection opens
      eventSource.onopen = () => {
        console.log('[Pub/Sub] ✅ EventSource connection OPENED, readyState:', eventSource.readyState)
      }

      // Handle thinking chunks
      eventSource.addEventListener('thinking_chunk', (event: MessageEvent) => {
        console.log('[DEBUG] ===== THINKING_CHUNK EVENT =====')
        console.log('[DEBUG] Raw event.data:', event.data)

        const data = JSON.parse(event.data)
        console.log('[DEBUG] Parsed data:', data)

        const thinkingContent = data.accumulated || data.data?.accumulated || ''
        console.log('[DEBUG] Extracted thinkingContent:', thinkingContent)
        console.log('[DEBUG] thinkingContent length:', thinkingContent.length)
        console.log('[DEBUG] assistantMessageId:', assistantMessageId)

        if (!hasScrolledForContentRef.current && thinkingContent.length > 0) {
          hasScrolledForContentRef.current = true
          setTimeout(scrollToBottom, 50)
        }

        setMessages((prev: Message[]) => {
          console.log('[DEBUG] Previous messages count:', prev.length)
          const updated = prev.map((msg: Message) => {
            if (msg.id === assistantMessageId) {
              console.log('[DEBUG] Found matching message, adding thinkingContent')
              return { ...msg, thinkingContent }
            }
            return msg
          })
          console.log('[DEBUG] Updated messages count:', updated.length)
          return updated
        })
      })

      // Handle thinking complete
      eventSource.addEventListener('thinking_complete', (event: MessageEvent) => {
        console.log('[Pub/Sub] Thinking complete')
      })

      // Handle intent determined
      eventSource.addEventListener('intent_determined', (event: MessageEvent) => {
        const data = JSON.parse(event.data)
        const isForecast = data.is_forecast || data.data?.is_forecast || false
        const renderMode: RenderMode = isForecast ? 'forecast' : 'chat'

        console.log('[Pub/Sub] Intent determined:', renderMode)
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, renderMode }
            : msg
        ))
      })

      // Handle analysis complete
      eventSource.addEventListener('analysis_complete', async () => {
        console.log('[Pub/Sub] Analysis complete')
        eventSource.close()
        setIsLoading(false)
        // ✅ 直接获取最终结果，无需刷新页面
        try {
          const { getAnalysisStatus } = await import('@/lib/api/analysis')
          const finalResult = await getAnalysisStatus(currentSessionId, currentMessageId)

          console.log('[Pub/Sub] Fetched final result:', finalResult)

          const isForecast = finalResult.data?.is_forecast || finalResult.data?.unified_intent?.is_forecast || false
          const conclusion = finalResult.data?.conclusion || (finalResult.data as any)?.chat_response || ''

          setMessages((prev: Message[]) => prev.map((msg: Message) =>
            msg.id === assistantMessageId
              ? {
                ...msg,
                contents: conclusion ? [{
                  type: 'text' as const,
                  text: conclusion
                }] : msg.contents || [],
                renderMode: isForecast ? 'forecast' : 'chat'
              }
              : msg
          ))
        } catch (error) {
          console.error('[Pub/Sub] Failed to fetch final result:', error)
        }
      })

      // Handle errors
      eventSource.addEventListener('error', (event: MessageEvent) => {
        console.error('[Pub/Sub] Error event:', event)
      })

      eventSource.onerror = (error) => {
        console.error('[Pub/Sub] SSE connection error:', error)
        eventSource.close()
        setIsLoading(false)
      }

    } catch (error) {
      console.error('[ChatArea] Error:', error)
      setIsLoading(false)
      // Show error message
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: `抱歉，发生错误：${error instanceof Error ? error.message : '未知错误'}`,
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev: Message[]) => [...prev, errorMessage])
    }
  }


  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSend()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <main className="flex-1 flex flex-col min-w-0">
      {/* 顶部栏 */}
      <header className="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-dark-800/30">
        <div className="flex items-center gap-4">
          <Image
            src="/logo.svg"
            alt="Logo"
            width={28}
            height={28}
            className="flex-shrink-0"
          />
          <h2 className="text-base font-semibold">
            小易猜猜
          </h2>
          {!isEmpty && isLoading && (
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-[10px] font-medium">
                分析中
              </span>
            </div>
          )}
        </div>
        {!isEmpty && (
          <div className="flex items-center gap-2">
            <button className="p-2 hover:bg-dark-600 rounded-lg transition-colors" title="导出报告">
              <Download className="w-4 h-4 text-gray-400" />
            </button>
            <button className="p-2 hover:bg-dark-600 rounded-lg transition-colors" title="分享">
              <Share2 className="w-4 h-4 text-gray-400" />
            </button>
            <button className="p-2 hover:bg-dark-600 rounded-lg transition-colors" title="更多">
              <MoreVertical className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        )}
      </header>

      {/* 对话区域 */}
      <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-6 space-y-6">
        {isEmpty ? (
          /* 空状态 - 欢迎界面 */
          <div className="flex flex-col items-center justify-center h-full -mt-20">
            <div className="text-center max-w-md">
              <h3 className="text-2xl font-semibold text-gray-200 mb-3">
                有什么可以帮忙的？
              </h3>
              <p className="text-gray-400 text-sm mb-8">
                我可以帮你分析股票走势、预测市场趋势、生成投资报告等
              </p>
              <div className="flex flex-col gap-3">
                {quickSuggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      // 直接发送快速追问
                      handleSend(suggestion)
                    }}
                    className="px-4 py-3 bg-dark-600/50 hover:bg-dark-500/50 border border-white/5 hover:border-violet-500/30 rounded-xl text-left text-sm text-gray-300 hover:text-gray-100 transition-all"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* 消息列表 */
          messages.map((message: Message, index: number) => (
            <div key={message.id}>
              <MessageBubble
                message={message}
                onRegenerateMessage={message.role === 'assistant' ? () => {
                  // 找到对应的用户消息（前一条）
                  const userMessage = index > 0 ? messages[index - 1] : null
                  if (userMessage && userMessage.role === 'user' && userMessage.text) {
                    // 删除当前这对QA消息
                    setMessages(prev => prev.filter((_, i) => i !== index && i !== index - 1))
                    // 重新发送用户消息
                    setTimeout(() => {
                      handleSend(userMessage.text)
                    }, 100)
                  }
                } : undefined}
              />
              {/* 如果有分析结果，显示分析卡片 */}
              {message.analysis && (
                <div className="mt-4 ml-13">
                  <AnalysisCards analysis={message.analysis} />
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* 快捷建议 - 只在有消息时显示 */}
      {!isEmpty && (
        <QuickSuggestions
          suggestions={quickSuggestions}
          onSelect={(suggestion) => {
            // 直接发送快速追问
            handleSend(suggestion)
          }}
        />
      )}

      {/* 输入区域 */}
      <div className="px-3 py-2 border-t border-white/5 bg-dark-800/50">
        <div className="max-w-4xl mx-auto">
          {/* 输入框行 */}
          <div className="flex items-center gap-2">
            {/* 输入框 */}
            <div className="flex-1 relative">
              <div className="glass rounded-xl border border-white/10 focus-within:border-violet-500/50 transition-colors">
                <textarea
                  className="w-full bg-transparent px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 resize-none outline-none"
                  rows={1}
                  placeholder="问我任何关于股票分析的问题..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
              </div>
            </div>

            {/* 发送按钮 */}
            <button
              className="p-2.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 rounded-lg transition-all flex-shrink-0 disabled:opacity-50"
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isLoading}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

          {/* 底部提示 */}
          <div className="flex items-center justify-between mt-1.5 px-1">
            <div className="flex items-center gap-2 text-[10px] text-gray-600">
              <kbd className="px-1 py-0.5 bg-dark-600/50 rounded text-gray-500 text-[9px]">⌘↵</kbd>
              <span>发送</span>
            </div>
            <div className="text-[10px] text-gray-600">
              智能分析
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
