'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { Download, Share2, MoreVertical, Paperclip, Send, Zap, Settings2, ChevronDown, ChevronRight } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { QuickSuggestions } from './QuickSuggestions'
import { AnalysisCards } from './AnalysisCards'
import { cn } from '@/lib/utils'
import type { ToolSettings } from '@/lib/api/chat'
import { DEFAULT_TOOL_SETTINGS } from '@/lib/api/chat'

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
      data: number[]
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

export function ChatArea() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState<'prophet' | 'xgboost' | 'randomforest' | 'dlinear'>('prophet')
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId())
  const [quickSuggestions, setQuickSuggestions] = useState<string[]>(defaultQuickSuggestions)
  const [tools, setTools] = useState<ToolSettings>(DEFAULT_TOOL_SETTINGS)
  const [isSettingsExpanded, setIsSettingsExpanded] = useState(false)

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

    // 创建AI消息占位符（不预先添加 steps，由后端发送 step 事件时再显示）
    const assistantMessageId = (Date.now() + 1).toString()
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      // steps 由后端判断后发送，不在前端预先决定
    }

    setMessages((prev: Message[]) => [...prev, assistantMessage])

    try {
      // 导入API函数（使用真实API）
      const { sendMessageStreamReal } = await import('@/lib/api/chat')

      // 构建对话历史
      const history = buildHistory()

      // 处理流式响应
      const contents: (TextContent | ChartContent | TableContent)[] = []
      let currentSessionId = sessionId
      let streamingText = ''  // 用于累积流式文本

      for await (const chunk of sendMessageStreamReal(
        messageToSend,
        selectedModel,
        currentSessionId,
        history,
        (steps: Step[]) => {
          // 更新步骤状态（后端判断后才会发送 step 事件）
          setMessages((prev: Message[]) => prev.map((msg: Message) =>
            msg.id === assistantMessageId
              ? { ...msg, steps }
              : msg
          ))
        },
        tools  // 传递 tools 设置
      )) {
        if (chunk.type === 'session') {
          // 接收后端返回的 session_id（新会话）
          currentSessionId = chunk.data
          setSessionId(currentSessionId)
          if (typeof window !== 'undefined') {
            localStorage.setItem('chat_session_id', currentSessionId)
          }
        } else if (chunk.type === 'intent') {
          // 意图识别结果
          setMessages((prev: Message[]) => prev.map((msg: Message) =>
            msg.id === assistantMessageId
              ? { ...msg, intentInfo: chunk.data as IntentInfo }
              : msg
          ))
        } else if (chunk.type === 'text_delta') {
          // 流式文本片段
          streamingText += chunk.data

          // 实时更新消息内容
          setMessages((prev: Message[]) => prev.map((msg: Message) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  contents: [{ type: 'text', text: streamingText } as TextContent],
                  steps: undefined
                }
              : msg
          ))
        } else if (chunk.type === 'text_done') {
          // 流式文本完成，添加到 contents
          contents.push({ type: 'text', text: chunk.data } as TextContent)
        } else if (chunk.type === 'content') {
          contents.push(chunk.data)

          // 更新消息内容，累积所有内容
          setMessages((prev: Message[]) => prev.map((msg: Message) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  contents: [...contents],
                  // 如果所有步骤完成，清除steps
                  steps: msg.steps?.every((s: Step) => s.status === 'completed') ? undefined : msg.steps
                }
              : msg
          ))
        }
      }

      // 所有内容接收完成，清除步骤显示
      if (contents.length > 0) {
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? {
              ...msg,
              contents: contents,
              steps: undefined
            }
            : msg
        ))
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
            {/* 设置折叠按钮 */}
            <button
              onClick={() => setIsSettingsExpanded(!isSettingsExpanded)}
              className={cn(
                "p-2 rounded-lg transition-all flex-shrink-0",
                isSettingsExpanded
                  ? "bg-violet-500/20 text-violet-400"
                  : "hover:bg-dark-600 text-gray-500"
              )}
              title="设置"
            >
              <Settings2 className="w-4 h-4" />
            </button>

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

          {/* 可折叠设置面板 */}
          {isSettingsExpanded && (
            <div className="mt-2 p-3 bg-dark-700/30 rounded-lg border border-white/5 space-y-3">
              {/* 功能开关 */}
              <div className="flex items-center gap-4">
                <span className="text-[11px] text-gray-500 w-16">启用功能</span>
                <div className="flex items-center gap-3">
                  {/* 序列预测 */}
                  <button
                    onClick={() => setTools({...tools, forecast: !tools.forecast})}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-[11px] font-medium transition-all border",
                      tools.forecast
                        ? "bg-violet-500/20 text-violet-300 border-violet-500/30"
                        : "bg-dark-600/50 text-gray-500 border-white/5 hover:border-white/10"
                    )}
                  >
                    序列预测
                  </button>
                  {/* 研报检索 */}
                  <button
                    disabled
                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-dark-600/30 text-gray-600 border border-white/5 cursor-not-allowed"
                    title="即将推出"
                  >
                    研报检索
                  </button>
                  {/* 新闻分析 */}
                  <button
                    disabled
                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-dark-600/30 text-gray-600 border border-white/5 cursor-not-allowed"
                    title="即将推出"
                  >
                    新闻分析
                  </button>
                </div>
              </div>

              {/* 模型选择 - 仅在序列预测开启时显示 */}
              {tools.forecast && (
                <div className="flex items-center gap-4">
                  <span className="text-[11px] text-gray-500 w-16">预测模型</span>
                  <div className="flex items-center gap-1.5">
                    {(['prophet', 'xgboost', 'randomforest', 'dlinear'] as const).map((model) => (
                      <button
                        key={model}
                        onClick={() => setSelectedModel(model)}
                        className={cn(
                          "px-2.5 py-1 rounded-md text-[11px] font-medium transition-all border",
                          selectedModel === model
                            ? "bg-violet-500/20 text-violet-300 border-violet-500/30"
                            : "bg-dark-600/50 text-gray-400 border-white/5 hover:border-white/10 hover:text-gray-300"
                        )}
                      >
                        {model === 'prophet' && 'Prophet'}
                        {model === 'xgboost' && 'XGBoost'}
                        {model === 'randomforest' && 'RandomForest'}
                        {model === 'dlinear' && 'DLinear'}
                      </button>
                    ))}
                  </div>
                  <span className="text-[10px] text-gray-600 ml-auto">
                    {selectedModel === 'prophet' && '适合长期预测'}
                    {selectedModel === 'xgboost' && '捕捉非线性关系'}
                    {selectedModel === 'randomforest' && '稳定性好'}
                    {selectedModel === 'dlinear' && '轻量高效'}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* 底部提示 */}
          <div className="flex items-center justify-between mt-1.5 px-1">
            <div className="flex items-center gap-2 text-[10px] text-gray-600">
              <kbd className="px-1 py-0.5 bg-dark-600/50 rounded text-gray-500 text-[9px]">⌘↵</kbd>
              <span>发送</span>
            </div>
            <div className="text-[10px] text-gray-600">
              {tools.forecast ? `${selectedModel.toUpperCase()} · 序列预测` : '直接对话'}
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
