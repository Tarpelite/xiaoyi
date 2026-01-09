'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { Download, Share2, MoreVertical, Send } from 'lucide-react'
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
}

// 预测步骤定义（7个步骤）- 与后端 STEPS 保持一致
export const PREDICTION_STEPS: Omit<Step, 'status' | 'message'>[] = [
  { id: '1', name: '数据获取与预处理' },
  { id: '2', name: '新闻获取与情绪分析' },
  { id: '3', name: '时序特征分析' },
  { id: '4', name: '参数智能推荐' },
  { id: '5', name: '模型训练与预测' },
  { id: '6', name: '结果可视化' },
  { id: '7', name: '报告生成' },
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

// Tool 开关设置
interface ToolSettings {
  forecast: boolean
  reportRag: boolean
  newsRag: boolean
}

export function ChatArea() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId())
  const [quickSuggestions, setQuickSuggestions] = useState<string[]>(defaultQuickSuggestions)
  const [selectedModel, setSelectedModel] = useState<'prophet' | 'xgboost' | 'randomforest' | 'dlinear'>('prophet')
  const [tools, setTools] = useState<ToolSettings>({ forecast: true, reportRag: false, newsRag: false })

  // 对话区域滚动容器 ref
  const chatContainerRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth'
      })
    }
  }

  // 消息更新时自动滚动
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 更新快速追问建议（在对话完成后）
  useEffect(() => {
    const updateSuggestions = async () => {
      // 只有在有消息、不在加载中、且有sessionId时才更新
      if (messages.length > 0 && !isLoading && sessionId) {
        try {
          const { getSuggestions } = await import('@/lib/api/analysis')
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
  const convertSteps = (currentStep: number, totalSteps: number = 7, status: string): Step[] => {
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
      news_list?: Array<{ title: string; summary: string; date: string; source: string }>
      conclusion?: string
    },
    currentStep: number = 0,
    status: string = 'pending'
  ): (TextContent | ChartContent | TableContent)[] => {
    const contents: (TextContent | ChartContent | TableContent)[] = []

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
    const isCompleted = status === 'completed' || currentStep >= 7

    // 1. 市场情绪（步骤5完成后显示）
    // 只有当步骤 >= 5 或已完成时，才显示情绪数据
    if (currentStep >= 5 || isCompleted) {
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

    // 2. 新闻列表表格（步骤4完成后显示）
    // 只有当步骤 >= 4 或已完成时，才显示新闻
    if ((currentStep >= 4 || isCompleted) && data.news_list && data.news_list.length > 0) {
      contents.push({
        type: 'table',
        title: '相关新闻',
        headers: ['标题', '来源', '日期'],
        rows: data.news_list.slice(0, 5).map((news) => [
          news.title,
          news.source,
          news.date
        ])
      })
    }

    // 3. 价格预测趋势图（步骤6完成后显示）
    // 只有当步骤 >= 6 或已完成时，才显示预测图表
    if ((currentStep >= 6 || isCompleted) && data.time_series_full && data.time_series_full.length > 0 && data.prediction_done) {
      const originalLength = data.time_series_original?.length || 0
      const allLabels = data.time_series_full.map((p) => p.date)
      const historicalData = data.time_series_full.map((p, idx) => 
        idx < originalLength ? p.value : null
      )
      const forecastData = data.time_series_full.map((p, idx) => 
        idx >= originalLength ? p.value : null
      )

      contents.push({
        type: 'chart',
        title: '价格预测趋势图',
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
        }
      })
    }

    // 4. 综合分析报告（步骤7完成后显示）
    // 只有当步骤 >= 7 或已完成时，才显示报告
    if ((currentStep >= 7 || isCompleted) && data.conclusion) {
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

    // 如果 forecast tool 关闭，直接回答（保留旧逻辑）
    if (!tools.forecast) {
      // 这里可以保留旧的流式回答逻辑，或者也改为使用 analysis API
      // 暂时先提示用户开启序列预测功能
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        text: messageToSend,
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev: Message[]) => [...prev, userMessage])
      setInputValue('')
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        contents: [{
          type: 'text',
          text: '请开启"序列预测"功能以使用分析功能。'
        }]
      }
      setMessages((prev: Message[]) => [...prev, assistantMessage])
      return
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: messageToSend,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev: Message[]) => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    // 创建AI消息占位符（清空旧内容）
    const assistantMessageId = (Date.now() + 1).toString()
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      contents: [], // 初始为空数组，避免显示旧内容
    }

    setMessages((prev: Message[]) => [...prev, assistantMessage])

    try {
      // 使用 analysis API
      const { createAnalysisTask, pollAnalysisStatus } = await import('@/lib/api/analysis')

      // 创建分析任务（传递当前 sessionId 以获取对话历史）
      const result = await createAnalysisTask(messageToSend, selectedModel, '', sessionId)
      const currentSessionId = result.session_id
      setSessionId(currentSessionId)
      if (typeof window !== 'undefined') {
        localStorage.setItem('chat_session_id', currentSessionId)
      }

      // 如果任务立即完成（intent == "answer"），立即查询一次状态
      if (result.status === 'completed' || result.intent === 'answer') {
        const { getAnalysisStatus } = await import('@/lib/api/analysis')
        const statusResponse = await getAnalysisStatus(currentSessionId)
        const { data, status } = statusResponse

        // 简单问答：只显示文本内容
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                contents: [{
                  type: 'text',
                  text: data.conclusion || '已收到回答'
                }],
                steps: undefined
              }
            : msg
        ))
      } else {
        // 轮询状态（intent == "analyze"）
        await pollAnalysisStatus(
          currentSessionId,
          (statusResponse) => {
            const { data, steps: currentStep, status } = statusResponse

            // 判断是否是简单问答（只有 conclusion，没有其他结构化数据）
            const isSimpleAnswer = status === 'completed' && 
              data.conclusion && 
              (!data.time_series_full || data.time_series_full.length === 0) &&
              (!data.emotion || data.emotion === null) &&
              (!data.news_list || data.news_list.length === 0)

            if (isSimpleAnswer) {
              // 简单问答：只显示文本内容
              setMessages((prev: Message[]) => prev.map((msg: Message) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      contents: [{
                        type: 'text',
                        text: data.conclusion
                      }],
                      steps: undefined
                    }
                  : msg
              ))
            } else {
              // 结构化回答：显示完整分析结果
              // 转换步骤
              const steps = convertSteps(currentStep, 7, status)

              // 转换内容（传入当前步骤和状态，只显示已完成步骤的内容）
              const contents = convertAnalysisToContents(data, currentStep, status)

              // 更新消息
              setMessages((prev: Message[]) => prev.map((msg: Message) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      steps: status === 'completed' ? undefined : steps, // 完成后隐藏步骤
                      contents: contents.length > 0 ? contents : [] // 清空旧内容，避免显示上次的数据
                    }
                  : msg
              ))
            }
          },
          2000 // 轮询间隔2秒
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
            {isEmpty ? '股票分析助手' : '股票分析'}
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
          messages.map((message: Message) => (
            <div key={message.id}>
              <MessageBubble message={message} />
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
              智能识别意图 · 自动选择模型
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
