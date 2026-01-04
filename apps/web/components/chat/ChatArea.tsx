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

// 模拟消息数据（兼容旧格式）
const mockMessages: Message[] = [
  {
    id: '1',
    role: 'user',
    text: '帮我分析一下茅台，预测下个季度走势，结合最新的研报观点',
    timestamp: '14:32',
  },
  {
    id: '2',
    role: 'assistant',
    text: '好的！我来为你分析 **600519.SH 贵州茅台**',
    timestamp: '14:32',
    analysis: {
      reportConsensus: {
        totalReports: 12,
        ratings: { buy: 8, hold: 4, sell: 0 },
        avgTargetPrice: 2180,
        currentPrice: 1850,
      },
      modelPrediction: {
        model: 'AutoARIMA',
        prediction: 8.5,
        mase: 0.82,
        confidenceInterval: [1920, 2050],
      },
      anomalyDetection: {
        count: 2,
        anomalies: [
          { date: '2024-11-15', change: -4.2 },
          { date: '2024-10-28', change: 5.8 },
        ],
      },
    },
  },
]

const quickSuggestions = [
  '📊 查看详细预测图表',
  '📝 生成投资分析报告',
  '🔔 设置价格预警',
  '📈 对比其他白酒股',
  '⚠️ 分析异常波动原因',
]

export function ChatArea() {
  const [messages, setMessages] = useState<Message[]>(mockMessages)
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)

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
      
      for await (const chunk of sendMessageStreamReal(inputValue, (steps: Step[]) => {
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

  return (
    <main className="flex-1 flex flex-col min-w-0">
      {/* 顶部栏 */}
      <header className="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-dark-800/30">
        <div className="flex items-center gap-4">
          <h2 className="text-base font-semibold">茅台 Q1 预测分析</h2>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-[10px] font-medium">
              进行中
            </span>
            <span className="px-2 py-0.5 bg-violet-500/20 text-violet-400 rounded text-[10px] font-medium">
              GPT-4o
            </span>
          </div>
        </div>
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
      </header>

      {/* 对话区域 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((message: Message) => (
          <div key={message.id}>
            <MessageBubble message={message} />
            {/* 如果有分析结果，显示分析卡片 */}
            {message.analysis && (
              <div className="mt-4 ml-13">
                <AnalysisCards analysis={message.analysis} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 快捷建议 */}
      <QuickSuggestions 
        suggestions={quickSuggestions} 
        onSelect={(suggestion) => setInputValue(suggestion)}
      />

      {/* 输入区域 */}
      <div className="p-4 border-t border-white/5 bg-dark-800/50">
        <div className="max-w-4xl mx-auto">
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
