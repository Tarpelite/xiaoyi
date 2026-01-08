'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Copy, ThumbsUp, ThumbsDown, RotateCcw, ChevronDown, ChevronRight, Brain, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { Message, IntentInfo } from './ChatArea'
import { MessageContent } from './MessageContent'
import { StepProgress } from './StepProgress'

interface MessageBubbleProps {
  message: Message
}

// 情绪仪表盘组件
function EmotionGauge({ emotion, description }: { emotion: number; description: string }) {
  const rotation = emotion * 90
  const getEmotionColor = (score: number) => {
    if (score > 0.3) return 'text-green-400'
    if (score < -0.3) return 'text-red-400'
    return 'text-gray-400'
  }

  const getEmotionIcon = (score: number) => {
    if (score > 0.3) return <TrendingUp className="w-6 h-6" />
    if (score < -0.3) return <TrendingDown className="w-6 h-6" />
    return <Minus className="w-6 h-6" />
  }

  return (
    <div className="space-y-4">
      {/* 仪表盘 */}
      <div className="relative w-full h-32 mx-auto">
        <svg className="w-full h-full" viewBox="0 0 200 100">
          <defs>
            <linearGradient id="gaugeRed" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#dc2626" />
              <stop offset="100%" stopColor="#f87171" />
            </linearGradient>
            <linearGradient id="gaugeGreen" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
          </defs>

          <path d="M 20 80 A 80 80 0 0 1 180 80" fill="none" stroke="#3a3a4a" strokeWidth="20" strokeLinecap="round" />
          <path d="M 20 80 A 80 80 0 0 1 100 10" fill="none" stroke="url(#gaugeRed)" strokeWidth="20" strokeLinecap="round" opacity="0.4" />
          <path d="M 100 10 A 80 80 0 0 1 180 80" fill="none" stroke="url(#gaugeGreen)" strokeWidth="20" strokeLinecap="round" opacity="0.4" />

          <line x1="100" y1="80" x2="100" y2="25" stroke="#9ca3af" strokeWidth="3" strokeLinecap="round"
            transform={`rotate(${rotation} 100 80)`} className="transition-transform duration-1000" />
          <circle cx="100" cy="80" r="8" fill="#9ca3af" />
        </svg>

        <div className="absolute top-0 left-0 text-[10px] font-bold text-red-400">极度看跌</div>
        <div className="absolute top-0 right-0 text-[10px] font-bold text-green-400">极度看涨</div>
      </div>

      {/* 情绪值 */}
      <div className="text-center space-y-2">
        <div className={`flex items-center justify-center gap-2 ${getEmotionColor(emotion)}`}>
          {getEmotionIcon(emotion)}
          <span className="text-3xl font-bold">
            {emotion > 0 ? '+' : ''}{emotion.toFixed(2)}
          </span>
        </div>
        {description && (
          <div className="bg-dark-700/50 rounded-lg p-3">
            <p className="text-xs text-gray-300 leading-relaxed">{description}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// 可折叠的意图识别组件
function IntentBadge({ intentInfo }: { intentInfo: IntentInfo }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const intentLabel = intentInfo.intent === 'analyze' ? '执行分析' : '直接回答'
  const intentColor = intentInfo.intent === 'analyze'
    ? 'text-blue-400 bg-blue-500/10 border-blue-500/20'
    : 'text-green-400 bg-green-500/10 border-green-500/20'

  return (
    <div className="mb-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[11px] transition-all",
          intentColor,
          "hover:opacity-80"
        )}
      >
        <Brain className="w-3 h-3" />
        <span>意图: {intentLabel}</span>
        {isExpanded ? (
          <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronRight className="w-3 h-3" />
        )}
      </button>
      {isExpanded && intentInfo.reason && (
        <div className="mt-1.5 px-3 py-2 bg-dark-700/50 rounded-lg text-[11px] text-gray-400 border border-white/5">
          {intentInfo.reason}
        </div>
      )}
    </div>
  )
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  // 兼容旧版text字段
  const displayText = message.text || (message.content?.type === 'text' ? message.content.text : '')

  return (
    <div className={cn(
      "flex gap-3 animate-slide-up",
      isUser ? "justify-end" : "justify-start"
    )}>
      {/* AI 头像 */}
      {!isUser && (
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
          <span className="text-base">🔮</span>
        </div>
      )}

      <div className={cn(
        "group",
        isUser ? "max-w-[85%] order-first" : "flex-1 max-w-full"
      )}>
        {/* 消息内容 */}
        {isUser ? (
          // 用户消息：纯文本
          <div className="px-4 py-3 rounded-2xl text-[15px] leading-relaxed bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-br-md">
            {displayText}
          </div>
        ) : (
          // AI消息：支持多种内容类型
          <div className="space-y-4 min-w-[200px]">
            {/* 意图识别结果（可折叠） */}
            {message.intentInfo && (
              <IntentBadge intentInfo={message.intentInfo} />
            )}

            {/* 步骤进度 - 横向链式显示 */}
            {message.steps && message.steps.length > 0 && (
              <div className="glass rounded-2xl px-6 py-4">
                <StepProgress steps={message.steps} />
              </div>
            )}

            {/* 结构化内容布局 */}
            {(() => {
              const contents = message.contents || (message.content ? [message.content] : [])
              const hasContents = contents.length > 0
              
              // 如果没有contents但有text，转换为text content
              if (!hasContents && displayText) {
                contents.push({ type: 'text', text: displayText })
              }

              if (!hasContents && !displayText && !message.steps) {
                return (
                  <div className="glass rounded-2xl px-4 py-3 text-gray-400">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                      <span className="text-sm">思考中...</span>
                    </div>
                  </div>
                )
              }

              if (hasContents || displayText) {
                // 分类内容：图表、表格、文本
                const charts = contents.filter(c => c.type === 'chart')
                const tables = contents.filter(c => c.type === 'table')
                const texts = contents.filter(c => c.type === 'text')
                
                // 识别市场情绪内容（特殊标记）
                const emotionText = texts.find(t => 
                  t.type === 'text' && t.text.startsWith('__EMOTION_MARKER__')
                )

                // 判断是否是简单问答：只有文本内容，没有图表、表格、情绪标记
                const isSimpleAnswer = charts.length === 0 && 
                  tables.length === 0 && 
                  !emotionText &&
                  texts.length > 0 &&
                  texts.every(t => !t.text.startsWith('__EMOTION_MARKER__'))

                // 如果是简单问答，直接显示文本内容，不使用结构化布局
                if (isSimpleAnswer) {
                  return (
                    <div className="glass rounded-2xl px-4 py-3 text-gray-200">
                      {texts.map((content, index) => (
                        <MessageContent key={index} content={content} />
                      ))}
                    </div>
                  )
                }

                // 结构化回答：有图表、表格或情绪数据
                // 识别综合分析报告（通常是最后一个文本内容，且不是情绪标记）
                const reportText = texts.filter(t => 
                  t.type === 'text' && !t.text.startsWith('__EMOTION_MARKER__')
                ).pop() // 取最后一个文本作为报告

                // 识别价格预测趋势图（标题包含"预测"）
                const priceChart = charts.find(c => 
                  c.type === 'chart' && (
                    c.title?.includes('预测') ||
                    c.data.datasets.some(d => d.label?.includes('预测'))
                  )
                )

                // 识别新闻表格
                const newsTable = tables.find(t => 
                  t.type === 'table' && (
                    t.title?.includes('新闻') || 
                    t.headers.some(h => h.includes('新闻') || h.includes('标题'))
                  )
                ) || tables[0]

                // 解析情绪数据
                let emotionData: { score: number; description: string } | null = null
                if (emotionText && emotionText.type === 'text') {
                  const match = emotionText.text.match(/__EMOTION_MARKER__([^_]+)__(.*)__/)
                  if (match) {
                    const score = parseFloat(match[1])
                    const description = match[2] || ''
                    if (!isNaN(score)) {
                      emotionData = { score, description }
                    }
                  }
                }

                return (
                  <div className="space-y-4">
                    {/* 四个结构化部分 */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {/* 市场情绪区域（左侧上方） */}
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>😊</span> 市场情绪
                        </h3>
                        {emotionData ? (
                          <EmotionGauge emotion={emotionData.score} description={emotionData.description} />
                        ) : (
                          <div className="text-sm text-gray-400">情绪分析中...</div>
                        )}
                      </div>

                      {/* 相关新闻区域（右侧上方） */}
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>📰</span> 相关新闻
                        </h3>
                        {newsTable ? (
                          <MessageContent content={newsTable} />
                        ) : (
                          <div className="text-sm text-gray-400">暂无新闻数据</div>
                        )}
                      </div>
                    </div>

                    {/* 价格预测趋势图（全宽） */}
                    {priceChart ? (
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>📈</span> 价格走势分析
                        </h3>
                        <MessageContent content={priceChart} />
                      </div>
                    ) : (
                      // 如果图表未生成，显示加载状态
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>📈</span> 价格走势分析
                        </h3>
                        <div className="text-sm text-gray-400 flex items-center gap-2 h-64 items-center justify-center">
                          <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                          <span>正在生成预测图表...</span>
                        </div>
                      </div>
                    )}

                    {/* 综合分析报告（全宽，最后） */}
                    {reportText ? (
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>📝</span> 综合分析报告
                        </h3>
                        <MessageContent content={reportText} />
                      </div>
                    ) : (
                      // 如果报告未生成，显示加载状态
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>📝</span> 综合分析报告
                        </h3>
                        <div className="text-sm text-gray-400 flex items-center gap-2">
                          <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                          <span>正在生成分析报告...</span>
                        </div>
                      </div>
                    )}

                    {/* 其他未分类的内容（向后兼容） */}
                    {contents.filter(c => {
                      if (c === priceChart || c === reportText) return false
                      if (emotionText === c) return false
                      if (newsTable === c) return false
                      return true
                    }).map((content, index) => (
                      <div key={index} className="glass rounded-2xl px-4 py-3 text-gray-200">
                        <MessageContent content={content} />
                      </div>
                    ))}
                  </div>
                )
              }

              return null
            })()}

            {/* 分析结果卡片（保留兼容） */}
            {message.analysis && (
              <div className="mt-2">
                {/* AnalysisCards 组件会在 ChatArea 中单独渲染 */}
              </div>
            )}
          </div>
        )}

        {/* 消息底部操作 */}
        <div className={cn(
          "flex items-center gap-2 mt-1.5 px-1",
          isUser ? "justify-end" : "justify-start"
        )}>
          <span className="text-[10px] text-gray-600">{message.timestamp}</span>
          
          {/* AI 消息的操作按钮 */}
          {!isUser && (
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <ActionButton icon={<Copy className="w-3 h-3" />} title="复制" />
              <ActionButton icon={<ThumbsUp className="w-3 h-3" />} title="有帮助" />
              <ActionButton icon={<ThumbsDown className="w-3 h-3" />} title="没帮助" />
              <ActionButton icon={<RotateCcw className="w-3 h-3" />} title="重新生成" />
            </div>
          )}
        </div>
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center flex-shrink-0 text-sm font-bold">
          李
        </div>
      )}
    </div>
  )
}

// 操作按钮组件
function ActionButton({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <button 
      className="p-1 hover:bg-dark-600 rounded transition-colors text-gray-500 hover:text-gray-300"
      title={title}
    >
      {icon}
    </button>
  )
}
