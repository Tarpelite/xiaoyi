'use client'

import { cn } from '@/lib/utils'
import { Copy, ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react'
import type { Message } from './ChatArea'
import { MessageContent } from './MessageContent'
import { StepProgress } from './StepProgress'

interface MessageBubbleProps {
  message: Message
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
        "max-w-[85%] group",
        isUser ? "order-first" : ""
      )}>
        {/* 消息内容 */}
        {isUser ? (
          // 用户消息：纯文本
          <div className="px-4 py-3 rounded-2xl text-[15px] leading-relaxed bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-br-md">
            {displayText}
          </div>
        ) : (
          // AI消息：支持多种内容类型
          <div className="space-y-3">
            {/* 步骤进度 */}
            {message.steps && message.steps.length > 0 && (
              <div className="glass rounded-2xl px-4 py-3">
                <StepProgress steps={message.steps} />
              </div>
            )}
            
            {/* 多个内容块 */}
            {message.contents && message.contents.length > 0 && (
              <>
                {message.contents.map((content, index) => (
                  <div key={index} className="glass rounded-2xl px-4 py-3 text-gray-200">
                    <MessageContent content={content} />
                  </div>
                ))}
              </>
            )}
            
            {/* 单个内容（兼容） */}
            {message.content && !message.contents && (
              <div className="glass rounded-2xl px-4 py-3 text-gray-200">
                <MessageContent content={message.content} />
              </div>
            )}
            
            {/* 兼容旧版：纯文本内容 */}
            {displayText && !message.content && !message.contents && (
              <div className="glass rounded-2xl px-4 py-3 text-[15px] leading-relaxed text-gray-200 rounded-bl-md">
                <MessageContent content={{ type: 'text', text: displayText }} />
              </div>
            )}
            
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
