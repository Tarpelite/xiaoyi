'use client'

import { useState } from 'react'
import { Download, Share2, MoreVertical, Paperclip, Send, Zap } from 'lucide-react'
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

// 预测步骤定义（7个步骤）
export const PREDICTION_STEPS: Omit<Step, 'status' | 'message'>[] = [
  { id: '1', name: '数据获取与预处理' },
  { id: '2', name: '时序特征分析' },
  { id: '3', name: '异常检测' },
  { id: '4', name: '模型训练与评估' },
  { id: '5', name: '预测生成' },
  { id: '6', name: '结果可视化' },
  { id: '7', name: '分析完成' },
]

// 引导性问题建议
const quickSuggestions = [
  '帮我分析一下茅台，预测下个季度走势',
  '查看最近的市场趋势',
  '对比几只白酒股的表现',
  '生成一份投资分析报告',
]

export function ChatArea() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState<'prophet' | 'xgboost' | 'randomforest' | 'dlinear'>('prophet')

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: inputValue,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev: Message[]) => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    // 创建AI消息占位符
    const assistantMessageId = (Date.now() + 1).toString()
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      steps: PREDICTION_STEPS.map(step => ({
        ...step,
        status: 'pending' as const,
      })),
    }

    setMessages((prev: Message[]) => [...prev, assistantMessage])

    try {
      // 导入API函数（使用真实API）
      const { sendMessageStreamReal } = await import('@/lib/api/chat')

      // 处理流式响应
      const contents: (TextContent | ChartContent | TableContent)[] = []

      for await (const chunk of sendMessageStreamReal(inputValue, selectedModel, (steps: Step[]) => {
        // 更新步骤状态
        setMessages((prev: Message[]) => prev.map((msg: Message) =>
          msg.id === assistantMessageId
            ? { ...msg, steps }
            : msg
        ))
      })) {
        if (chunk.type === 'content') {
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
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
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
                      setInputValue(suggestion)
                      // 自动聚焦到输入框
                      setTimeout(() => {
                        const textarea = document.querySelector('textarea')
                        textarea?.focus()
                      }, 100)
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
          onSelect={(suggestion) => setInputValue(suggestion)}
        />
      )}

      {/* 输入区域 */}
      <div className="p-4 border-t border-white/5 bg-dark-800/50">
        <div className="max-w-4xl mx-auto">
          {/* 模型选择器 */}
          <div className="flex items-center gap-3 mb-3 px-1">
            <span className="text-xs text-gray-500">预测模型:</span>
            <div className="flex items-center gap-2 bg-dark-700/50 rounded-lg p-1 border border-white/5">
              <button
                onClick={() => setSelectedModel('prophet')}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                  selectedModel === 'prophet'
                    ? "bg-violet-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200"
                )}
              >
                Prophet
              </button>
              <button
                onClick={() => setSelectedModel('xgboost')}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                  selectedModel === 'xgboost'
                    ? "bg-violet-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200"
                )}
              >
                XGBoost
              </button>
              <button
                onClick={() => setSelectedModel('randomforest')}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                  selectedModel === 'randomforest'
                    ? "bg-violet-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200"
                )}
              >
                RandomForest
              </button>
              <button
                onClick={() => setSelectedModel('dlinear')}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-all",
                  selectedModel === 'dlinear'
                    ? "bg-violet-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200"
                )}
              >
                DLinear
              </button>
            </div>
            <span className="text-[10px] text-gray-600 ml-auto">
              {selectedModel === 'prophet' && '适合长期预测，自动处理季节性'}
              {selectedModel === 'xgboost' && '适合中短期预测，捕捉非线性关系'}
              {selectedModel === 'randomforest' && '集成学习，稳定性好，适合复杂模式'}
              {selectedModel === 'dlinear' && '分解线性模型，轻量高效，趋势提取强'}
            </span>
          </div>

          <div className="flex items-end gap-3">
            {/* 附件按钮 */}
            <button className="p-2.5 hover:bg-dark-600 rounded-xl transition-colors flex-shrink-0" title="上传文件">
              <Paperclip className="w-5 h-5 text-gray-500" />
            </button>

            {/* 输入框 */}
            <div className="flex-1 relative">
              <div className="glass rounded-2xl border border-white/10 focus-within:border-violet-500/50 transition-colors">
                <textarea
                  className="w-full bg-transparent px-5 py-3.5 text-[15px] text-gray-200 placeholder-gray-500 resize-none outline-none"
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
              className="p-3 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 rounded-xl transition-all hover-lift flex-shrink-0 disabled:opacity-50"
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>

          <div className="flex items-center justify-between mt-2 px-1">
            <div className="flex items-center gap-4 text-[10px] text-gray-600">
              <span className="flex items-center gap-1">
                <Zap className="w-3 h-3 text-yellow-500" />
                TimeCopilot 驱动
              </span>
              <span>|</span>
              <span>支持上传 CSV、Excel、研报 PDF</span>
            </div>
            <div className="flex items-center gap-1 text-[10px] text-gray-600">
              <kbd className="px-1.5 py-0.5 bg-dark-600 rounded text-gray-500">⌘</kbd>
              <kbd className="px-1.5 py-0.5 bg-dark-600 rounded text-gray-500">↵</kbd>
              <span className="ml-1">发送</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
