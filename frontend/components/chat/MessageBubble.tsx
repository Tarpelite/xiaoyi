'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Copy, ThumbsUp, ThumbsDown, RotateCcw, ChevronDown, ChevronRight, Brain } from 'lucide-react'
import type { Message, IntentInfo, RenderMode } from './ChatArea'
import { MessageContent } from './MessageContent'
import { StepProgress } from './StepProgress'
import { ThinkingSection } from './ThinkingSection'
import { RAGSourceCard } from './RAGSourceCard'

interface MessageBubbleProps {
  message: Message
  onRegenerateMessage?: () => void
}

// 情绪横向标尺组件
function EmotionGauge({ emotion, description }: { emotion: number; description: string }) {
  // 将情绪值从 [-1, 1] 映射到百分比 [0%, 100%]
  const position = ((emotion + 1) / 2) * 100

  const getPointerColor = (score: number) => {
    if (score > 0.3) return 'bg-green-400'
    if (score < -0.3) return 'bg-red-400'
    return 'bg-gray-400'
  }

  const getTextColor = (score: number) => {
    if (score > 0.3) return 'text-green-400'
    if (score < -0.3) return 'text-red-400'
    return 'text-gray-400'
  }

  return (
    <div className="space-y-3">
      {/* 横向标尺 */}
      <div className="relative pt-8 pb-6">
        {/* 数值显示 - 跟随指针 */}
        <div
          className="absolute top-0 transform -translate-x-1/2 transition-all duration-1000 ease-out"
          style={{ left: `${position}%` }}
        >
          <span className={`text-lg font-bold ${getTextColor(emotion)}`}>
            {emotion.toFixed(2)}
          </span>
        </div>

        {/* 渐变轨道 */}
        <div className="relative h-2 rounded-full overflow-hidden bg-dark-500">
          <div className="absolute inset-0 flex">
            {/* 红色区域（看跌） */}
            <div className="flex-1 bg-gradient-to-r from-red-500 to-red-300 opacity-60" />
            {/* 灰色区域（中性） */}
            <div className="flex-1 bg-gradient-to-r from-gray-500 to-gray-400 opacity-60" />
            {/* 绿色区域（看涨） */}
            <div className="flex-1 bg-gradient-to-r from-green-300 to-green-500 opacity-60" />
          </div>
        </div>

        {/* 指针 - 居中于轨道 (pt-8=32px, h-2=8px, 中心=36px, 指针h-3=12px, top=36-6=30px) */}
        <div
          className={`absolute w-3 h-3 rounded-full shadow-lg transform -translate-x-1/2 -translate-y-1/2 transition-all duration-1000 ease-out ${getPointerColor(emotion)}`}
          style={{ left: `${position}%`, top: '36px' }}
        />

        {/* 刻度标签 */}
        <div className="flex justify-between mt-3 px-0">
          <span className="text-xs font-medium text-red-400">-1</span>
          <span className="text-xs text-gray-500">-0.5</span>
          <span className="text-xs text-gray-400">0</span>
          <span className="text-xs text-gray-500">+0.5</span>
          <span className="text-xs font-medium text-green-400">+1</span>
        </div>
      </div>

      {/* LLM 生成的描述 */}
      {description && (
        <div className="bg-dark-700/40 rounded-lg px-3 py-2 border border-white/5">
          <p className="text-sm text-gray-300 leading-relaxed">{description}</p>
        </div>
      )}
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

export function MessageBubble({ message, onRegenerateMessage }: MessageBubbleProps) {
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

            {/* 思考过程 - 在有思考内容或思考日志时显示（可展开） */}
            {(message.thinkingContent || (message.thinkingLogs && message.thinkingLogs.length > 0)) && (
              <ThinkingSection
                content={message.thinkingContent || ''}
                isLoading={message.renderMode === 'thinking'}
                logs={message.thinkingLogs}
              />
            )}

            {/* 步骤进度 - 只在 forecast 模式下显示 */}
            {message.renderMode === 'forecast' && message.steps && message.steps.length > 0 && (
              <div className="glass rounded-2xl px-6 py-4">
                <StepProgress steps={message.steps} />
              </div>
            )}

            {/* 结构化内容布局 - 根据 renderMode 决定渲染方式 */}
            {(() => {
              const contents = message.contents || (message.content ? [message.content] : [])
              const hasContents = contents.length > 0
              const renderMode = message.renderMode || 'thinking'

              // 如果没有contents但有text，转换为text content
              if (!hasContents && displayText) {
                contents.push({ type: 'text', text: displayText })
              }

              // 🎯 renderMode === 'thinking': 显示可展开的思考过程
              // 注意：如果已经在上面通过 message.thinkingContent 显示了 ThinkingSection，这里就不再显示
              if (renderMode === 'thinking' && !hasContents && !displayText && !message.steps && !message.thinkingContent) {
                return (
                  <ThinkingSection
                    content=""
                    isLoading={true}
                  />
                )
              }

              const hasSteps = Boolean(message.steps && message.steps.length > 0)

              // 仅在有实际内容时渲染结构化预测面板，避免 thinking 阶段出现闪烁占位卡片。
              if (hasContents || displayText) {
                // 分类内容：图表、表格、文本
                const charts = contents.filter(c => c.type === 'chart')
                const tables = contents.filter(c => c.type === 'table')
                const texts = contents.filter(c => c.type === 'text')

                // 识别市场情绪内容（特殊标记）
                const emotionText = texts.find(t =>
                  t.type === 'text' && t.text.startsWith('__EMOTION_MARKER__')
                )

                // 🎯 判断是否是简单问答
                // 有结构化数据（图表、表格、情绪）时强制使用结构化布局，不管 renderMode 是什么
                const hasStructuredData = charts.length > 0 || tables.length > 0 || emotionText
                const isSimpleAnswer = !hasStructuredData && (
                  renderMode === 'chat' || (
                    !hasSteps &&
                    texts.length > 0 &&
                    texts.every(t => !t.text.startsWith('__EMOTION_MARKER__'))
                  )
                )

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

                // 🎯 renderMode === 'forecast': 显示进度条 + 结构化报告模板

                // 🎯 对话模式：数据获取失败，只显示对话气泡
                if (message.isConversationalMode && texts.length > 0) {
                  return (
                    <div className="max-w-3xl animate-fade-in">
                      <div className="glass rounded-2xl p-6">
                        <div className="flex items-start gap-4">
                          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center flex-shrink-0 shadow-lg">
                            <span className="text-2xl">🤖</span>
                          </div>
                          <div className="flex-1">
                            <h3 className="text-lg font-bold text-gray-100 mb-3 flex items-center gap-2">
                              小易助手
                              <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-1 rounded-full font-medium border border-blue-500/30">
                                智能助理
                              </span>
                            </h3>
                            <div className="text-gray-300 leading-relaxed">
                              {texts.map((content, index) => (
                                <MessageContent key={index} content={content} />
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Tips */}
                      <div className="mt-4 bg-blue-500/10 rounded-xl p-4 border border-blue-500/20">
                        <h4 className="font-semibold text-blue-300 mb-2 flex items-center gap-2">
                          💡 使用建议
                        </h4>
                        <ul className="text-sm text-blue-200/80 space-y-1">
                          <li>• 确认股票代码格式正确（A股为6位数字）</li>
                          <li>• 可以尝试使用公司名称，如"贵州茅台"</li>
                          <li>• 热门股票示例：600519（茅台）、000001（平安银行）</li>
                        </ul>
                      </div>
                    </div>
                  )
                }

                // 结构化回答：有图表、表格或情绪数据
                // 识别综合分析报告（通常是最后一个文本内容，且不是情绪标记）
                const reportText = texts.filter(t =>
                  t.type === 'text' && !t.text.startsWith('__EMOTION_MARKER__')
                ).pop() // 取最后一个文本作为报告

                // 识别价格走势图表（包含"历史价格"或"预测价格"）
                const priceChart = charts.find(c =>
                  c.type === 'chart' && (
                    c.title?.includes('预测') ||
                    c.title?.includes('走势') ||
                    c.data.datasets.some(d => d.label?.includes('价格'))
                  )
                )

                // 识别新闻表格
                const newsTable = tables.find(t =>
                  t.type === 'table' && (
                    t.title?.includes('新闻') ||
                    t.headers.some(h => h.includes('新闻') || h.includes('标题'))
                  )
                ) || tables[0]

                const ragRetrievalFinished = Boolean(
                  reportText ||
                  (message.steps && message.steps.every(s => s.status === 'completed' || s.status === 'failed'))
                )

                // 解析情绪数据
                let emotionData: { score: number; description: string } | null = null
                if (emotionText && emotionText.type === 'text') {
                  // 使用 [\s\S]* 匹配包括换行符在内的任意字符
                  const match = emotionText.text.match(/__EMOTION_MARKER__([^_]+)__([\s\S]*)__/)
                  if (match) {
                    const score = parseFloat(match[1])
                    const description = match[2] || ''
                    if (!isNaN(score)) {
                      emotionData = { score, description }
                    }
                  }
                }

                return (
                  <div className={cn(
                    "space-y-4",
                    message.isCollapsing && "animate-collapse"
                  )}>
                    {/* 上半部分：左右分栏 - 市场情绪(1) | 相关新闻+研报(2) */}
                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-4">
                      {/* 左侧：市场情绪 */}
                      <div className="glass rounded-2xl p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                          <span>😊</span> 市场情绪
                        </h3>
                        {emotionData ? (
                          <div className="space-y-3">
                            <EmotionGauge emotion={emotionData.score} description="" />
                            {emotionData.description && (
                              <div className="bg-dark-700/40 rounded-lg px-3 py-2 border border-white/5">
                                <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">{emotionData.description}</p>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-sm text-gray-400 flex items-center gap-2">
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                            <span>情绪分析中...</span>
                          </div>
                        )}
                      </div>

                      {/* 右侧：相关新闻 + 研报来源（1:1 高度比例） */}
                      <div className="grid grid-rows-2 gap-4 min-h-[400px]">
                        {/* 相关新闻（占 1 份高度） */}
                        <div className="glass rounded-2xl p-4 overflow-hidden flex flex-col">
                          <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2 flex-shrink-0">
                            <span>📰</span> 相关新闻
                          </h3>
                          <div className="flex-1 overflow-y-auto">
                            {newsTable ? (
                              <MessageContent content={newsTable} />
                            ) : (
                              <div className="text-sm text-gray-400 flex items-center gap-2">
                                <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                                <span>正在获取新闻...</span>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 研报来源（占 2 份高度） */}
                        {message.ragSources && message.ragSources.length > 0 ? (
                          <div className="glass rounded-2xl p-4 overflow-hidden flex flex-col">
                            <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2 flex-shrink-0">
                              <span>📚</span> 研报来源
                              <span className="text-xs text-gray-500 font-normal">
                                ({message.ragSources.length} 篇相关研报)
                              </span>
                            </h3>
                            <div className="flex-1 overflow-y-auto">
                              <RAGSourceCard sources={message.ragSources} />
                            </div>
                          </div>
                        ) : ragRetrievalFinished ? (
                          <div className="glass rounded-2xl p-4 overflow-hidden flex flex-col">
                            <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2 flex-shrink-0">
                              <span>📚</span> 研报来源
                            </h3>
                            <div className="flex-1 flex items-center justify-center text-sm text-gray-500">
                              暂未检索到相关研报
                            </div>
                          </div>
                        ) : (
                          <div className="glass rounded-2xl p-4 overflow-hidden flex flex-col">
                            <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2 flex-shrink-0">
                              <span>📚</span> 研报来源
                            </h3>
                            <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
                              <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse mr-2" />
                              <span>正在检索研报...</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 价格预测趋势图（全宽） */}
                    <div className="glass rounded-2xl p-4">
                      <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                        <span>📈</span> 价格走势分析
                      </h3>
                      {priceChart ? (
                        <MessageContent content={priceChart} />
                      ) : (
                        <div className="text-sm text-gray-400 flex items-center gap-2 h-64 items-center justify-center">
                          <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                          <span>正在生成预测图表...</span>
                        </div>
                      )}
                    </div>

                    {/* 综合分析报告（全宽，最后） */}
                    <div className="glass rounded-2xl p-4">
                      <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                        <span>📝</span> 综合分析报告
                      </h3>
                      {reportText ? (
                        <MessageContent content={reportText} />
                      ) : (
                        <div className="text-sm text-gray-400 flex items-center gap-2">
                          <div className="w-2 h-2 bg-violet-400 rounded-full animate-pulse" />
                          <span>正在生成分析报告...</span>
                        </div>
                      )}
                    </div>

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

          {/* AI 消息的操作按钮 - 只在消息完成后显示 */}
          {!isUser && (() => {
            // 判断消息是否完成
            const isMessageComplete = message.renderMode !== 'thinking' && (
              // chat模式：有内容即完成
              message.renderMode === 'chat' ||
              // forecast模式：所有步骤完成
              !message.steps || message.steps.every(s => s.status === 'completed' || s.status === 'failed')
            )

            if (!isMessageComplete) return null

            // 提取可复制的内容
            const getCopyContent = () => {
              const contents = message.contents || (message.content ? [message.content] : [])

              // 对于forecast模式，复制综合分析报告（最后一个非情绪的文本）
              if (message.renderMode === 'forecast') {
                const reportText = contents
                  .filter(c => c.type === 'text' && !c.text.startsWith('__EMOTION_MARKER__'))
                  .pop()
                if (reportText && reportText.type === 'text') {
                  return reportText.text
                }
              }

              // 对于chat模式，复制所有文本内容
              return contents
                .filter(c => c.type === 'text')
                .map(c => c.type === 'text' ? c.text : '')
                .join('\n\n')
            }

            const handleCopy = async () => {
              const textToCopy = getCopyContent()
              if (textToCopy) {
                try {
                  await navigator.clipboard.writeText(textToCopy)
                  // TODO: 可以添加toast提示
                  // console.log('已复制到剪贴板')
                } catch (err) {
                  console.error('复制失败:', err)
                }
              }
            }

            return (
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <ActionButton
                  icon={<Copy className="w-3 h-3" />}
                  title="复制"
                  onClick={handleCopy}
                />
                <ActionButton icon={<ThumbsUp className="w-3 h-3" />} title="有帮助" />
                <ActionButton icon={<ThumbsDown className="w-3 h-3" />} title="没帮助" />
                <ActionButton
                  icon={<RotateCcw className="w-3 h-3" />}
                  title="重新生成"
                  onClick={onRegenerateMessage}
                />
              </div>
            )
          })()}
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
function ActionButton({ icon, title, onClick }: {
  icon: React.ReactNode
  title: string
  onClick?: () => void
}) {
  return (
    <button
      className="p-1 hover:bg-dark-600 rounded transition-colors text-gray-500 hover:text-gray-300"
      title={title}
      onClick={onClick}
    >
      {icon}
    </button>
  )
}
