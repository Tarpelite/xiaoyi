'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Brain, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ThinkingSectionProps {
  content: string
  isLoading?: boolean
}

export function ThinkingSection({ content, isLoading = false }: ThinkingSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // 如果没有内容且不在加载中，不显示
  if (!content && !isLoading) return null

  return (
    <div className="glass rounded-xl border border-white/5 overflow-hidden">
      {/* 标题栏 - 可点击展开/收起 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isLoading ? (
            <Sparkles className="w-4 h-4 text-violet-400 animate-pulse" />
          ) : (
            <Brain className="w-4 h-4 text-violet-400" />
          )}
          <span className="text-sm font-medium text-gray-300">
            {isLoading ? '思考中...' : '思考过程'}
          </span>
          {isLoading && (
            <div className="flex gap-1 ml-2">
              <div className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {content && (
            <span className="text-xs text-gray-500">
              {content.length} 字
            </span>
          )}
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </div>
      </button>

      {/* 内容区域 - 可展开 */}
      <div
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          isExpanded ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="px-4 py-3 border-t border-white/5">
          <div className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap overflow-y-auto max-h-80">
            {content || (
              <span className="text-gray-500 italic">正在分析...</span>
            )}
            {/* 闪烁光标效果 - 仅在加载时显示 */}
            {isLoading && (
              <span className="inline-block w-2 h-4 ml-0.5 bg-violet-400/70 animate-pulse" />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
