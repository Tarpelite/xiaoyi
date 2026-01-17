'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { Download, Share2, MoreVertical, Paperclip, Send, Zap, ChevronDown, ChevronRight } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { QuickSuggestions } from './QuickSuggestions'
import { AnalysisCards } from './AnalysisCards'
import { cn } from '@/lib/utils'
import type { RAGSource, ThinkingLogEntry } from '@/lib/api/analysis'

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
      // 防止 React 严格模式下重复加载
      if (historyLoadedRef.current) return
      historyLoadedRef.current = true

      if (!sessionId) return

      try {
        const { getSessionHistory } = await import('@/lib/api/analysis')
        const history = await getSessionHistory(sessionId)

        // 将后端历史消息转换为前端 Message 格式
        // 只加载已完成的消息，跳过 processing/pending 状态的消息
        const loadedMessages: Message[] = []

        if (history && history.messages && history.messages.length > 0) {
          for (const historyMsg of history.messages) {
            // 只处理已完成的消息
            if (historyMsg.status !== 'completed' || !historyMsg.data) {
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

            // 添加助手消息
            const isForecastIntent = data.intent === 'forecast' ||
              (data.unified_intent && data.unified_intent.is_forecast)

            // 转换内容
            const contents = convertAnalysisToContents(data, data.steps, 'completed')

            loadedMessages.push({
              id: `assistant-${historyMsg.message_id}`,
              role: 'assistant',
              timestamp: new Date(data.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
              contents: contents.length > 0 ? contents : [{
                type: 'text',
                text: data.conclusion || '已完成分析'
              }],
              renderMode: isForecastIntent ? 'forecast' : 'chat',
              ragSources: data.rag_sources || [], // RAG 研报来源
              thinkingLogs: data.thinking_logs || [], // 思考日志
            })
          }
        }

        // 无论是否有历史，都更新messages（确保切换到空会话时清空）
        setMessages(loadedMessages)
      } catch (error) {
        console.error('加载会话历史失败:', error)
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
        source_name?: string
      }>
      rag_sources?: RAGSource[]
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
    // DEBUG: 输出情绪数据用于调试
    const hasValidEmotion_debug = typeof data.emotion === 'number'
    const hasEmotionDes_debug = data.emotion_des !== null && data.emotion_des !== undefined
    console.log('[Emotion Debug]', {
      currentStep,
      isCompleted,
      emotion: data.emotion,
      emotion_des: data.emotion_des,
      willAddEmotion: (currentStep >= 4 || isCompleted) && hasValidEmotion_debug && hasEmotionDes_debug,
      conditions: { hasValidEmotion: hasValidEmotion_debug, hasEmotionDes: hasEmotionDes_debug }
    })
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
      // 使用 analysis API - 流式获取思考内容
      const { streamAnalysisTask, pollAnalysisStatus, getAnalysisStatus } = await import('@/lib/api/analysis')
      const { createSession } = await import('@/lib/api/sessions')

      // 确保 session 存在（后端要求 session_id 必填）
      let activeSessionId = sessionId
      if (!activeSessionId) {
        const newSession = await createSession()
        activeSessionId = newSession.session_id
        setSessionId(activeSessionId)
        if (typeof window !== 'undefined') {
          localStorage.setItem('chat_session_id', activeSessionId)
        }
      }

      // 阶段1: 使用 SSE 流式获取思考内容
      const { session_id: currentSessionId, message_id: currentMessageId } = await streamAnalysisTask(
        messageToSend,
        {
          // 实时更新思考内容
          onThinking: (content: string) => {
            // 第一次收到内容时滚动一次
            if (!hasScrolledForContentRef.current && content.length > 0) {
              hasScrolledForContentRef.current = true
              setTimeout(scrollToBottom, 50)
            }
            setMessages((prev: Message[]) => prev.map((msg: Message) =>
              msg.id === assistantMessageId
                ? { ...msg, thinkingContent: content }
                : msg
            ))
          },
          // 收到意图后更新渲染模式
          onIntent: (intent: string, isForecast: boolean) => {
            const renderMode: RenderMode = isForecast ? 'forecast' : 'chat'
            setMessages((prev: Message[]) => prev.map((msg: Message) =>
              msg.id === assistantMessageId
                ? { ...msg, renderMode }
                : msg
            ))
          },
          // 错误处理
          onError: (errorMsg: string) => {
            console.error('Stream error:', errorMsg)
          }
        },
        'prophet',
        '',
        sessionId
      )

      // 更新 sessionId（首次创建或复用）
      setSessionId(currentSessionId)
      if (typeof window !== 'undefined') {
        localStorage.setItem('chat_session_id', currentSessionId)
      }

      // 设置当前活跃的轮询任务（支持多会话）
      activePollingMapRef.current.set(currentSessionId, currentMessageId)
      console.log('[ChatArea] Started polling for session:', currentSessionId, 'message:', currentMessageId)

      // 阶段2: 流结束后，查询一次状态判断是否需要轮询
      const initialStatus = await getAnalysisStatus(currentSessionId, currentMessageId)

      // 如果任务已完成（如简单问答），直接显示结果
      if (initialStatus.status === 'completed') {
        const { data } = initialStatus

        // 简单问答：只显示文本内容，renderMode 为 chat（保留 thinkingContent 和 thinkingLogs）
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? {
              ...msg,
              contents: [{
                type: 'text',
                text: data.conclusion || '已收到回答'
              }],
              steps: undefined,
              renderMode: 'chat' as RenderMode,
              thinkingLogs: data.thinking_logs || msg.thinkingLogs || []
            }
            : msg
        ))
      } else {
        // 轮询状态（使用 message_id 确保轮询正确的消息）
        await pollAnalysisStatus(
          currentSessionId,
          currentMessageId,
          (statusResponse) => {
            // 检查这个轮询是否还是active的（避免切换会话后继续更新）
            const activeMessageId = activePollingMapRef.current.get(currentSessionId)
            if (activeMessageId !== currentMessageId) {
              console.log('[Poll] Skipping update for session:', currentSessionId, 'message:', currentMessageId, 'active:', activeMessageId)
              return
            }
            const { data, steps: currentStep, status } = statusResponse

            // DEBUG: 输出轮询响应数据
            console.log('[Poll Debug] statusResponse:', {
              currentStep,
              status,
              intent: data.intent,
              emotion: data.emotion,
              emotion_des: data.emotion_des,
              hasTimeSeries: data.time_series_full?.length || 0,
              hasNews: data.news_list?.length || 0
            })

            // 🎯 根据后端返回的 intent 决定渲染模式
            const isForecastIntent = data.intent === 'forecast' ||
              (data.unified_intent && data.unified_intent.is_forecast)

            // 确定渲染模式
            let currentRenderMode: RenderMode = 'thinking'
            if (data.intent && data.intent !== 'pending') {
              currentRenderMode = isForecastIntent ? 'forecast' : 'chat'
            }

            // 判断是否是简单问答（非 forecast 意图，只有 conclusion）
            const isSimpleAnswer = !isForecastIntent && status === 'completed' && data.conclusion

            if (isSimpleAnswer) {
              // 简单问答：只显示文本内容，renderMode 为 chat（保留 thinkingContent 和 thinkingLogs）
              setMessages((prev: Message[]) => prev.map((msg: Message) =>
                msg.id === assistantMessageId
                  ? {
                    ...msg,
                    contents: [{
                      type: 'text',
                      text: data.conclusion
                    }],
                    steps: undefined,
                    renderMode: 'chat' as RenderMode,
                    thinkingLogs: data.thinking_logs || msg.thinkingLogs || []
                  }
                  : msg
              ))
            } else {
              // 预测分析：显示完整分析结果
              // 转换步骤
              const steps = convertSteps(currentStep, data.total_steps || 6, status)

              // 转换内容（传入当前步骤和状态，只显示已完成步骤的内容）
              const contents = convertAnalysisToContents(data, currentStep, status)

              // DEBUG: 输出转换后的 contents
              console.log('[Poll Debug] converted contents:', contents.map(c => ({ type: c.type, hasEmotion: c.type === 'text' && c.text?.startsWith('__EMOTION_MARKER__') })))

              // 更新消息（保留 thinkingContent，添加 ragSources 和 thinkingLogs）
              setMessages((prev: Message[]) => prev.map((msg: Message) =>
                msg.id === assistantMessageId
                  ? {
                    ...msg,
                    steps: status === 'completed' ? undefined : steps, // 完成后隐藏步骤
                    contents: contents.length > 0 ? contents : [], // 清空旧内容，避免显示上次的数据
                    renderMode: currentRenderMode, // 根据 intent 设置渲染模式
                    ragSources: data.rag_sources || [], // RAG 研报来源
                    thinkingLogs: data.thinking_logs || msg.thinkingLogs || [] // 累积的思考日志（保留已有的）
                  }
                  : msg
              ))
            }
          },
          500 // 轮询间隔 500ms (推荐)
        )
      }

    } catch (error) {
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
