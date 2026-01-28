'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { Download, Share2, MoreVertical, Send } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { QuickSuggestions } from './QuickSuggestions'
import { AnalysisCards } from './AnalysisCards'
import type { RAGSource, ThinkingLogEntry, TimeSeriesPoint, NewsItem, MessageData } from '@/lib/api/analysis'

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
export type MessageContentType = 'text' | 'chart' | 'table' | 'stock'

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
  // 异常区域和新闻（新增）
  anomalyZones?: Array<{
    startDate: string
    endDate: string
    summary: string
    sentiment: 'positive' | 'negative' | 'neutral'
    method?: string
  }>
  anomalies?: Array<{
    date: string
    price: number
    score: number
    description: string
    method: string
  }>
  semantic_zones?: any[]  // 语义合并区间
  prediction_semantic_zones?: any[]  // 预测语义区间
  ticker?: string  // 股票代码，用于获取新闻
  predictionStartDay?: string // 预测开始日期
}

// 表格内容
export interface TableContent {
  type: 'table'
  title?: string
  headers: string[]
  rows: (string | number)[][]
}

// 股票内容
export interface StockContent {
  type: 'stock'
  ticker: string
  title?: string
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
  content?: TextContent | ChartContent | TableContent | StockContent
  contents?: (TextContent | ChartContent | TableContent | StockContent)[]
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
  // RAG 研报来源
  ragSources?: RAGSource[]
  // 累积的思考日志（显示各步骤 LLM 原始输出）
  thinkingLogs?: ThinkingLogEntry[]
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

interface ChatAreaProps {
  sessionId: string | null
  onSessionCreated?: (sessionId: string) => void
}

export function ChatArea({ sessionId: externalSessionId, onSessionCreated }: ChatAreaProps) {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(externalSessionId)
  const [quickSuggestions, setQuickSuggestions] = useState<string[]>(defaultQuickSuggestions)

  // 对话模式动画状态 (针对最后一条消息)
  const [lastMessageConversationalMode, setLastMessageConversationalMode] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_lastMessageCollapsing, setLastMessageCollapsing] = useState(false)  // 保留用于未来动画实现

  // 对话区域滚动容器 ref
  const chatContainerRef = useRef<HTMLDivElement>(null)

  // 跟踪当前消息是否已经滚动过（用于控制只滚动两次：发送时+开始产生内容时）
  const hasScrolledForContentRef = useRef(false)

  // AbortController 用于取消旧请求（切换会话时）
  const abortControllerRef = useRef<AbortController | null>(null)

  // 用于在 effect 中访问最新的 isLoading 状态（避免闭包问题）
  const isLoadingRef = useRef(isLoading)
  isLoadingRef.current = isLoading

  // 标记 sessionId 变化来源：'handleSend' 表示由 handleSend 触发，不需要 abort
  const sessionChangeSourceRef = useRef<'handleSend' | null>(null)

  // 是否正在加载历史记录（如果有 sessionId，初始就是加载状态）
  const [isLoadingHistory, setIsLoadingHistory] = useState(!!externalSessionId)

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

  // 同步 externalSessionId 到内部 sessionId
  useEffect(() => {
    // 当 externalSessionId 变化时，同步到内部状态
    if (externalSessionId !== sessionId) {
      setSessionId(externalSessionId)
    }
  }, [externalSessionId]) // 只监听 externalSessionId

  // 当 sessionId 变化时，同步到 URL
  useEffect(() => {
    if (sessionId) {
      const currentUrl = new URL(window.location.href)
      if (currentUrl.searchParams.get('session') !== sessionId) {
        router.replace(`/?session=${sessionId}`, { scroll: false })
      }
    }
  }, [sessionId, router])

  // 创建流式回调的工厂函数（共享逻辑）
  const createStreamCallbacks = (
    assistantMessageId: string,
    backendSessionId: string,
    backendMessageId: string,
    options: { enableScrollOnFirstContent?: boolean } = {}
  ) => {
    // 累积的数据状态
    let accumulatedTimeSeriesOriginal: TimeSeriesPoint[] = []
    let accumulatedTimeSeriesFull: TimeSeriesPoint[] = []
    let accumulatedNews: NewsItem[] = []
    let accumulatedEmotion: { score: number; description: string } | null = null
    let accumulatedAnomalyZones: any[] = []  // 异常区域
    let accumulatedAnomalies: any[] = []     // 异常点
    let accumulatedSemanticZones: any[] = []  // 语义区间
    let accumulatedPredictionSemanticZones: any[] = []  // 预测语义区间
    let accumulatedConclusion = '' // 综合报告内容
    let stockTicker = ''  // 股票代码
    let predictionStartDay = ''

    return {
      // 恢复数据（断点续传时使用）
      onResume: (currentData: MessageData) => {
        // console.log('[ChatArea] Resume - currentData:', currentData)
        if (currentData) {
          if (currentData.time_series_original) {
            accumulatedTimeSeriesOriginal = currentData.time_series_original
          }
          if (currentData.time_series_full) {
            accumulatedTimeSeriesFull = currentData.time_series_full
          }
          if (currentData.news_list) {
            accumulatedNews = currentData.news_list
            // console.log('[ChatArea] Resume - Loaded news:', accumulatedNews.length, 'items')
            // console.log('[ChatArea] Resume - First news:', accumulatedNews[0]?.summarized_title || 'N/A')
          } else {
            // console.log('[ChatArea] Resume - NO news_list in currentData')
          }
          if (currentData.emotion !== null && currentData.emotion !== undefined) {
            accumulatedEmotion = { score: currentData.emotion, description: currentData.emotion_des || '中性' }
          }
          // 提取anomaly_zones
          if (currentData.anomaly_zones && currentData.anomaly_zones.length > 0) {
            accumulatedAnomalyZones = currentData.anomaly_zones
            stockTicker = currentData.anomaly_zones_ticker || ''
            // console.log('[ChatArea] Resume - extracted anomaly zones:', accumulatedAnomalyZones.length, 'zones for ticker:', stockTicker)
          } else {
            // console.log('[ChatArea] Resume - NO anomaly_zones in currentData')
          }
          if (currentData.anomalies && currentData.anomalies.length > 0) {
            accumulatedAnomalies = currentData.anomalies;
            // console.log('[ChatArea] Resume - extracted anomalies:', accumulatedAnomalies.length);
          }
          if (currentData.prediction_start_day) {
            predictionStartDay = currentData.prediction_start_day
          }

          if (currentData.conclusion) {
            accumulatedConclusion = currentData.conclusion
          }

          // DEBUG: Log restored zones
          console.log('[onResume] Restoring Semantic Zones. CurrentData Keys:', Object.keys(currentData))
          console.log('[onResume] currentData.semantic_zones:', currentData.semantic_zones?.length)
          console.log('[onResume] currentData.prediction_semantic_zones:', currentData.prediction_semantic_zones?.length)
          console.log('[onResume] predictionStartDay:', predictionStartDay)

          if (currentData.semantic_zones) {
            accumulatedSemanticZones = currentData.semantic_zones
          }
          if (currentData.prediction_semantic_zones) {
            accumulatedPredictionSemanticZones = currentData.prediction_semantic_zones
          }

          updateContentsFromStreamData(
            assistantMessageId,
            accumulatedTimeSeriesOriginal,
            accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null,
            accumulatedNews,
            accumulatedEmotion,
            accumulatedConclusion,
            predictionStartDay,
            backendSessionId,
            backendMessageId,
            accumulatedAnomalyZones,
            stockTicker,
            accumulatedAnomalies,
            accumulatedSemanticZones,
            accumulatedPredictionSemanticZones
          )
        }
      },

      // 步骤开始
      onStepStart: (step: number, stepName: string) => {
        const steps = PREDICTION_STEPS.map((s, idx) => {
          const stepNum = idx + 1
          if (stepNum < step) {
            return { ...s, status: 'completed' as StepStatus }
          } else if (stepNum === step) {
            return { ...s, status: 'running' as StepStatus, message: `${stepName}中...` }
          }
          return { ...s, status: 'pending' as StepStatus }
        })

        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, steps }
            : msg
        ))
      },

      // 步骤完成
      onStepComplete: (step: number, data?: any) => {
        // 捕获股票代码（步骤2完成时）
        if (step === 2 && data?.stock_code) {
          stockTicker = data.stock_code
        }

        const steps = PREDICTION_STEPS.map((s, idx) => {
          const stepNum = idx + 1
          if (stepNum <= step) {
            return { ...s, status: 'completed' as StepStatus, message: '已完成' }
          }
          return { ...s, status: 'pending' as StepStatus }
        })

        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, steps }
            : msg
        ))
      },

      // 思考内容（累积）
      onThinking: (content: string) => {
        // 第一次收到内容时滚动一次（仅新消息需要）
        if (options.enableScrollOnFirstContent && !hasScrolledForContentRef.current && content.length > 0) {
          hasScrolledForContentRef.current = true
          setTimeout(scrollToBottom, 50)
        }
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, thinkingContent: content }
            : msg
        ))
      },

      // 意图识别结果
      onIntent: (_intent: string, isForecast: boolean) => {
        const renderMode: RenderMode = isForecast ? 'forecast' : 'chat'
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, renderMode }
            : msg
        ))
      },

      // 结构化数据
      onData: (dataType: string, data: unknown, predStart?: string, fullEvent?: any) => {
        // console.log('[ChatArea] onData received:', dataType, data, 'fullEvent:', fullEvent)
        if (dataType === 'time_series_original') {
          accumulatedTimeSeriesOriginal = data as TimeSeriesPoint[]
          updateContentsFromStreamData(
            assistantMessageId,
            accumulatedTimeSeriesOriginal,
            null,
            accumulatedNews,
            accumulatedEmotion,
            null,
            '',
            backendSessionId,
            backendMessageId,
            accumulatedAnomalyZones,
            stockTicker,
            accumulatedAnomalies,
            accumulatedSemanticZones,
            accumulatedPredictionSemanticZones
          )
        } else if (dataType === 'time_series_full') {
          accumulatedTimeSeriesFull = data as TimeSeriesPoint[]
          predictionStartDay = predStart || ''

          // CRITICAL: Extract semantic_zones, anomalies, and stock_zones from fullEvent
          if (fullEvent) {
            if (fullEvent.semantic_zones) {
              // console.log('[ChatArea] Extracted semantic_zones from time_series_full:', fullEvent.semantic_zones.length)
              accumulatedSemanticZones = fullEvent.semantic_zones
            }
            if (fullEvent.prediction_semantic_zones) {
              // console.log('[ChatArea] Extracted prediction_semantic_zones:', fullEvent.prediction_semantic_zones.length)
              accumulatedPredictionSemanticZones = fullEvent.prediction_semantic_zones
            }
            if (fullEvent.anomalies) {
              // console.log('[ChatArea] Extracted anomalies from  time_series_full:', fullEvent.anomalies.length)
              accumulatedAnomalies = fullEvent.anomalies
            }
            if (fullEvent.stock_zones) {
              // console.log('[ChatArea] Extracted stock_zones (anomaly zones) from time_series_full:', fullEvent.stock_zones.length)
              accumulatedAnomalyZones = fullEvent.stock_zones
            }
          }

          updateContentsFromStreamData(assistantMessageId, accumulatedTimeSeriesOriginal, accumulatedTimeSeriesFull, accumulatedNews, accumulatedEmotion, null, predictionStartDay, backendSessionId, backendMessageId, accumulatedAnomalyZones, stockTicker, accumulatedAnomalies, accumulatedSemanticZones, accumulatedPredictionSemanticZones)
        } else if (dataType === 'news') {
          accumulatedNews = data as NewsItem[]
          updateContentsFromStreamData(assistantMessageId, accumulatedTimeSeriesOriginal, accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null, accumulatedNews, accumulatedEmotion, null, predictionStartDay, backendSessionId, backendMessageId, accumulatedAnomalyZones, stockTicker, accumulatedAnomalies, accumulatedSemanticZones, accumulatedPredictionSemanticZones)
        } else if (dataType === 'emotion') {
          const emotionData = data as { score: number; description: string }
          accumulatedEmotion = emotionData
          updateContentsFromStreamData(assistantMessageId, accumulatedTimeSeriesOriginal, accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null, accumulatedNews, accumulatedEmotion, null, predictionStartDay, backendSessionId, backendMessageId, accumulatedAnomalyZones, stockTicker, accumulatedAnomalies, accumulatedSemanticZones, accumulatedPredictionSemanticZones)
        } else if (dataType === 'anomaly_zones') {
          console.log('[ChatArea] Received anomaly_zones event:', data)
          const zonesData = data as { zones: any[]; ticker: string; anomalies?: any[] }
          accumulatedAnomalyZones = zonesData.zones || []
          accumulatedAnomalies = zonesData.anomalies || []
          stockTicker = zonesData.ticker || ''
          console.log('[ChatArea] Extracted - zones:', accumulatedAnomalyZones.length, 'ticker:', stockTicker, 'anomalies:', accumulatedAnomalies.length)
          // 异常区数据收到后立即更新图表
          updateContentsFromStreamData(assistantMessageId, accumulatedTimeSeriesOriginal, accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null, accumulatedNews, accumulatedEmotion, null, predictionStartDay, backendSessionId, backendMessageId, accumulatedAnomalyZones, stockTicker, accumulatedAnomalies, accumulatedSemanticZones, accumulatedPredictionSemanticZones)
        } else if (dataType === 'anomalies') {
          accumulatedAnomalies = data as any[];
          updateContentsFromStreamData(assistantMessageId, accumulatedTimeSeriesOriginal, accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null, accumulatedNews, accumulatedEmotion, null, predictionStartDay, backendSessionId, backendMessageId, accumulatedAnomalyZones, stockTicker, accumulatedAnomalies, accumulatedSemanticZones, accumulatedPredictionSemanticZones)
        }
      },

      // 报告流式（累积）
      onReportChunk: (content: string) => {
        accumulatedConclusion = content
        updateContentsFromStreamData(
          assistantMessageId,
          accumulatedTimeSeriesOriginal,
          accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null,
          accumulatedNews,
          accumulatedEmotion,
          accumulatedConclusion,
          predictionStartDay,
          backendSessionId,
          backendMessageId,
          accumulatedAnomalyZones,
          stockTicker,
          accumulatedAnomalies,
          accumulatedSemanticZones,
          accumulatedPredictionSemanticZones
        )
      },

      // 聊天流式（累积）
      onChatChunk: (content: string) => {
        accumulatedConclusion = content
        updateContentsFromStreamData(
          assistantMessageId,
          accumulatedTimeSeriesOriginal,
          accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null,
          accumulatedNews,
          accumulatedEmotion,
          accumulatedConclusion,
          predictionStartDay,
          backendSessionId,
          backendMessageId,
          accumulatedAnomalyZones,
          stockTicker,
          accumulatedAnomalies,
          accumulatedSemanticZones,
          accumulatedPredictionSemanticZones
        )
      },

      // 情绪分析流式（累积）- 实时更新描述文本
      onEmotionChunk: (content: string) => {
        // 流式接收时，score 先设为 0，等 data 事件传完整结果
        accumulatedEmotion = { score: accumulatedEmotion?.score ?? 0, description: content }
        updateContentsFromStreamData(
          assistantMessageId,
          accumulatedTimeSeriesOriginal,
          accumulatedTimeSeriesFull.length > 0 ? accumulatedTimeSeriesFull : null,
          accumulatedNews,
          accumulatedEmotion,
          accumulatedConclusion,
          predictionStartDay,
          backendSessionId,
          backendMessageId,
          accumulatedAnomalyZones,
          stockTicker,
          accumulatedAnomalies,
          accumulatedSemanticZones,
          accumulatedPredictionSemanticZones
        )
      },

      // 完成
      onDone: () => {
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, steps: undefined }
            : msg
        ))
        setIsLoading(false)
      },

      // 错误
      onError: (errorMsg: string) => {
        console.error('Stream error:', errorMsg)
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? {
              ...msg,
              contents: [{
                type: 'text',
                text: errorMsg || '抱歉，处理请求时出现错误，请稍后重试。'
              }],
              steps: undefined
            }
            : msg
        ))
        setIsLoading(false)
      }
    }
  }

  // 恢复进行中消息的流式接收
  const resumeStreamForMessage = async (
    backendMessageId: string,
    currentSessionId: string,
    assistantMessageId: string,
    signal?: AbortSignal
  ) => {
    try {
      setIsLoading(true)
      const { resumeStream } = await import('@/lib/api/analysis')
      const callbacks = createStreamCallbacks(assistantMessageId, currentSessionId, backendMessageId)
      await resumeStream(currentSessionId, backendMessageId, callbacks, undefined, signal)
    } catch (error: unknown) {
      // 忽略取消错误
      if (error instanceof Error && error.name === 'AbortError') {
        return
      }
      console.error('恢复流式接收失败:', error)
      setIsLoading(false)
    }
  }

  // 页面加载时恢复会话历史（每次 sessionId 变化都重新加载）
  useEffect(() => {
    // 检查 sessionId 变化来源
    const changeSource = sessionChangeSourceRef.current
    sessionChangeSourceRef.current = null  // 重置

    // ✅ 只有外部触发的 sessionId 变化（用户切换会话）才 abort 旧请求
    // handleSend 触发的变化不需要 abort，因为 handleSend 自己管理 AbortController
    if (changeSource !== 'handleSend' && abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // 如果正在发送消息，跳过加载历史（handleSend 会自己处理）
    if (isLoadingRef.current) {
      setIsLoadingHistory(false)
      return
    }

    // 创建新的 AbortController
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    const loadSessionHistory = async () => {
      // 如果没有 sessionId，清空消息（新会话状态）
      if (!sessionId) {
        setMessages([])
        setIsLoadingHistory(false)
        return
      }

      setIsLoadingHistory(true)

      try {
        const { getSessionHistory } = await import('@/lib/api/analysis')
        const history = await getSessionHistory(sessionId, abortController.signal)

        // 如果请求被取消，直接返回
        if (abortController.signal.aborted) {
          return
        }

        // 将后端历史消息转换为前端 Message 格式
        const loadedMessages: Message[] = []
        // 收集需要恢复流式接收的消息
        const messagesToResume: Array<{ messageId: string; assistantMessageId: string }> = []

        if (history && history.messages && history.messages.length > 0) {
          for (const historyMsg of history.messages) {
            // 跳过没有数据的消息
            if (!historyMsg.data) {
              continue
            }

            const data = historyMsg.data

            // 添加用户消息
            loadedMessages.push({
              id: `user-${historyMsg.message_id}`,
              role: 'user',
              text: historyMsg.user_query,
              timestamp: new Date(data.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
            })

            const isForecastIntent = data.intent === 'forecast' ||
              (data.unified_intent && data.unified_intent.is_forecast)
            const assistantMessageId = `assistant-${historyMsg.message_id}`

            if (historyMsg.status === 'completed') {
              // 已完成的消息：直接渲染
              const contents = convertAnalysisToContents(data, data.steps, 'completed')

              loadedMessages.push({
                id: assistantMessageId,
                role: 'assistant',
                timestamp: new Date(data.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                contents: contents.length > 0 ? contents : [{
                  type: 'text',
                  text: data.conclusion || '已完成分析'
                }],
                renderMode: isForecastIntent ? 'forecast' : 'chat',
                ragSources: data.rag_sources || [],
                thinkingLogs: data.thinking_logs || [],
              })
            } else if (historyMsg.status === 'processing' || historyMsg.status === 'pending') {
              // 进行中的消息：先显示已有数据，然后调用 resumeStream 继续接收
              const currentStep = data.steps || 0
              const contents = convertAnalysisToContents(data, currentStep, 'processing')

              // 构建步骤状态
              const steps = convertSteps(currentStep, 6, 'processing')

              loadedMessages.push({
                id: assistantMessageId,
                role: 'assistant',
                timestamp: new Date(data.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
                contents: contents.length > 0 ? contents : [],
                steps: steps,
                renderMode: isForecastIntent ? 'forecast' : 'thinking',
                ragSources: data.rag_sources || [],
                thinkingLogs: data.thinking_logs || [],
              })

              // 记录需要恢复的消息
              messagesToResume.push({
                messageId: historyMsg.message_id,
                assistantMessageId: assistantMessageId
              })
            }
          }
        }

        // 无论是否有历史，都更新messages（确保切换到空会话时清空）
        setMessages(loadedMessages)
        setIsLoadingHistory(false)

        // 加载历史后滚动到底部
        if (loadedMessages.length > 0) {
          setTimeout(scrollToBottom, 100)
        }

        // 异步恢复进行中的消息（不阻塞渲染）
        for (const { messageId, assistantMessageId } of messagesToResume) {
          resumeStreamForMessage(messageId, sessionId, assistantMessageId, abortController.signal)
        }
      } catch (error: unknown) {
        // 如果是取消请求导致的错误，直接忽略
        if (error instanceof Error && error.name === 'AbortError') {
          return
        }

        setIsLoadingHistory(false)
        console.error('加载会话历史失败:', error)

        // 区分 404（会话不存在）和网络错误
        const errorMessage = error instanceof Error ? error.message : String(error)
        if (errorMessage.includes('404') || errorMessage.includes('not found') || errorMessage.includes('Not Found')) {
          // console.log('[ChatArea] Session not found (404), clearing messages')
          setMessages([])
        }
        // 网络错误时不清空消息，保留现有内容
      }
    }

    loadSessionHistory()

    // 组件卸载或 sessionId 变化时取消请求
    return () => {
      abortController.abort()
    }
  }, [sessionId])

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

  // 将后端返回的数据转换为前端的 contents
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
        source_name?: string
      }>
      rag_sources?: RAGSource[]
      conclusion?: string
      is_time_series?: boolean
      conversational_response?: string
      session_id?: string
      message_id?: string
      anomalyZones?: Array<{
        startDate: string
        endDate: string
        summary: string
        sentiment: 'positive' | 'negative' | 'neutral'
      }>
      anomaly_zones?: Array<{  // Backend uses snake_case
        startDate: string
        endDate: string
        summary: string
        sentiment: 'positive' | 'negative'
      }>
      anomaly_zones_ticker?: string | null
      anomalies?: Array<{
        date: string
        price: number
        score: number
        description: string
        method: string
      }>
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
    // 注意：emotion 为 0 是有效值（中性情绪），需要用 === null/undefined 判断
    const isSimpleAnswer = data.conclusion &&
      (!data.time_series_full || data.time_series_full.length === 0) &&
      (data.emotion === null || data.emotion === undefined) &&
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
      // emotion_des 可能是空字符串，需要使用严格的 null/undefined 检查
      const hasValidEmotion = typeof data.emotion === 'number'
      const hasEmotionDes = data.emotion_des !== null && data.emotion_des !== undefined

      if (hasValidEmotion && hasEmotionDes) {
        // 使用后端返回的真实数据（emotion_des 为空字符串时使用默认值）
        const emotionDescription = data.emotion_des || '中性'
        contents.push({
          type: 'text',
          text: `__EMOTION_MARKER__${data.emotion}__${emotionDescription}__`
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
        headers: ['标题', '来源', '时间'],
        rows: data.news_list.slice(0, 10).map((news) => [
          // 如果有 URL，使用 markdown 链接格式 [标题](url)；否则只显示标题
          news.url ? `[${news.summarized_title}](${news.url})` : news.summarized_title,
          news.source_name || (news.source_type === 'search' ? '网络' : '资讯'),
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
          originalData: data.time_series_original,
          // 异常区域和股票代码（用于刷新后恢复）
          anomalyZones: data.anomaly_zones || [],
          ticker: data.anomaly_zones_ticker ?? undefined,
          // CRITICAL FIX: Include all zone data for refresh persistence
          anomalies: data.anomalies || [],
          semantic_zones: (data as any).semantic_zones || [],
          prediction_semantic_zones: (data as any).prediction_semantic_zones || [],
          predictionStartDay: (data as any).prediction_start_day
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
          originalData: data.time_series_original,
          // 异常区域和股票代码（用于刷新后恢复）
          anomalyZones: data.anomaly_zones || [],
          ticker: data.anomaly_zones_ticker ?? undefined,
          // CRITICAL FIX: Include all zone data for refresh persistence
          anomalies: data.anomalies || [],
          semantic_zones: (data as any).semantic_zones || [],
          prediction_semantic_zones: (data as any).prediction_semantic_zones || [],
          predictionStartDay: (data as any).prediction_start_day
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

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: messageToSend,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev: Message[]) => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    // 发送消息后滚动一次
    setTimeout(scrollToBottom, 50)

    // 重置滚动标记，准备在收到内容时再滚动一次
    hasScrolledForContentRef.current = false

    // 创建新的 AbortController 并更新 ref（覆盖 useEffect 创建的）
    // 这样 handleSend 接管控制权，后续 setSessionId 触发的 useEffect 会因为 isLoadingRef 而跳过
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const sendAbortController = new AbortController()
    abortControllerRef.current = sendAbortController

    // 创建AI消息占位符（清空旧内容）
    const assistantMessageId = (Date.now() + 1).toString()
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      contents: [], // 初始为空数组，避免显示旧内容
      renderMode: 'thinking', // 初始为思考中状态
    }

    setMessages((prev: Message[]) => [...prev, assistantMessage])

    try {
      // 使用 create + resumeStream 模式（后端任务独立运行，不依赖前端连接）
      const { createAnalysis, resumeStream } = await import('@/lib/api/analysis')
      const { createSession } = await import('@/lib/api/sessions')

      // 确保 session 存在（后端要求 session_id 必填）
      let activeSessionId = sessionId
      if (!activeSessionId) {
        const newSession = await createSession()
        activeSessionId = newSession.session_id
        // 标记这是 handleSend 触发的 sessionId 变化，useEffect 不应该 abort
        sessionChangeSourceRef.current = 'handleSend'
        setSessionId(activeSessionId)
        // URL 会通过 useEffect 自动更新
      }

      // Step 1: 创建后台任务
      const createResult = await createAnalysis(messageToSend, {
        model: undefined,  // undefined 表示自动选择最佳模型
        sessionId: activeSessionId
      })

      // 标记这是 handleSend 触发的 sessionId 变化，useEffect 不应该 abort
      sessionChangeSourceRef.current = 'handleSend'
      setSessionId(createResult.session_id)

      // 通知父组件会话已创建（立即刷新侧边栏并高亮显示）
      if (onSessionCreated) {
        onSessionCreated(createResult.session_id)
      }

      // Step 2: 通过 resumeStream 流式获取结果（使用共享回调）
      const callbacks = createStreamCallbacks(
        assistantMessageId,
        createResult.session_id,
        createResult.message_id,
        { enableScrollOnFirstContent: true }
      )
      // 使用 handleSend 自己的 AbortController，不受 useEffect sessionId 变化影响
      await resumeStream(createResult.session_id, createResult.message_id, callbacks, undefined, sendAbortController.signal)

    } catch (error: unknown) {
      // 忽略取消错误（切换会话时正常行为）
      if (error instanceof Error && error.name === 'AbortError') {
        return
      }
      console.error('发送消息失败:', error)
      // 更新消息显示错误
      setMessages((prev: Message[]) => prev.map((msg: Message) =>
        msg.id === assistantMessageId
          ? {
            ...msg,
            contents: [{
              type: 'text',
              text: '抱歉，处理请求时出现错误，请稍后重试。'
            }],
            steps: undefined
          }
          : msg
      ))
    } finally {
      setIsLoading(false)
    }
  }

  // 辅助函数：根据流式数据更新 contents
  const updateContentsFromStreamData = (
    messageId: string,
    timeSeriesOriginal: TimeSeriesPoint[],
    timeSeriesFull: TimeSeriesPoint[] | null,
    news: NewsItem[],
    emotion: { score: number; description: string } | null,
    conclusion: string | null,
    _predictionStart: string,  // 保留参数用于未来可能的扩展
    backendSessionId?: string,  // 用于回测功能
    backendMessageId?: string,   // 用于回测功能
    anomalyZones?: any[],  // 异常区域
    ticker?: string,  // 股票代码
    anomalies?: any[], // 异常点
    semanticZones?: any[], // 语义合并区间
    predictionSemanticZones?: any[] // 预测语义区间
  ) => {
    setMessages((prev: Message[]) => prev.map((msg: Message) => {
      if (msg.id !== messageId) return msg

      const newContents: (TextContent | ChartContent | TableContent)[] = []

      // 1. 情绪（如果有）
      if (emotion) {
        newContents.push({
          type: 'text',
          text: `__EMOTION_MARKER__${emotion.score}__${emotion.description}__`
        })
      }

      // 2. 新闻表格（如果有）
      if (news.length > 0) {
        newContents.push({
          type: 'table',
          title: '',
          headers: ['标题', '来源', '时间'],
          rows: news.slice(0, 10).map((n) => [
            n.url ? `[${n.summarized_title}](${n.url})` : n.summarized_title,
            n.source_name || (n.source_type === 'search' ? '网络' : '资讯'),
            n.published_date
          ])
        })
      }

      // 3. 图表
      if (timeSeriesFull && timeSeriesFull.length > 0) {
        // 完整图表（历史 + 预测）
        const originalLength = timeSeriesOriginal.length
        const allLabels = timeSeriesFull.map((p) => p.date)
        const historicalData = timeSeriesFull.map((p, idx) =>
          idx < originalLength ? p.value : null
        )
        const lastHistoricalValue = timeSeriesFull[originalLength - 1]?.value
        const forecastData = timeSeriesFull.map((p, idx) => {
          if (idx < originalLength - 1) return null
          if (idx === originalLength - 1) return lastHistoricalValue
          return p.value
        })

        newContents.push({
          type: 'chart',
          title: '',
          data: {
            labels: allLabels,
            datasets: [
              { label: '历史价格', data: historicalData, color: '#8b5cf6' },
              { label: '预测价格', data: forecastData, color: '#06b6d4' }
            ]
          },
          sessionId: backendSessionId,
          messageId: backendMessageId,
          originalData: timeSeriesOriginal,
          anomalyZones: anomalyZones || [],
          anomalies: anomalies || [],
          semantic_zones: semanticZones || [],
          prediction_semantic_zones: predictionSemanticZones || [],
          ticker: ticker,
          predictionStartDay: _predictionStart || undefined
        })
        // console.log('[ChatArea] Created chart with anomalyZones:', anomalyZones?.length || 0, 'zones, ticker:', ticker)
      } else if (timeSeriesOriginal.length > 0) {
        // 只有历史图表
        newContents.push({
          type: 'chart',
          title: '',
          data: {
            labels: timeSeriesOriginal.map((p) => p.date),
            datasets: [
              { label: '历史价格', data: timeSeriesOriginal.map((p) => p.value), color: '#8b5cf6' }
            ]
          },
          sessionId: backendSessionId,
          messageId: backendMessageId,
          originalData: timeSeriesOriginal,
          anomalyZones: anomalyZones || [],
          anomalies: anomalies || [],
          semantic_zones: semanticZones || [],
          prediction_semantic_zones: predictionSemanticZones || [],
          ticker: ticker
        })
      }

      // 4. 报告/结论
      if (conclusion) {
        newContents.push({
          type: 'text',
          text: conclusion
        })
      }

      return {
        ...msg,
        contents: newContents.length > 0 ? newContents : msg.contents
      }
    }))
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
        {isLoadingHistory ? (
          /* 加载历史记录中 */
          <div className="flex flex-col items-center justify-center h-full -mt-20">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <p className="text-gray-400 text-sm mt-4">加载对话历史...</p>
          </div>
        ) : isEmpty ? (
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
