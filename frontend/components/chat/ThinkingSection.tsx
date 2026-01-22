'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Brain, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ThinkingLogEntry } from '@/lib/api/analysis'

interface ThinkingSectionProps {
  content: string
  isLoading?: boolean
  logs?: ThinkingLogEntry[]  // 累积的思考日志
}

export function ThinkingSection({ content, isLoading = false, logs = [] }: ThinkingSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // 只保留意图识别日志
  const intentLogs = logs.filter(log => log.step_id === 'intent')

  // 如果没有内容且不在加载中且没有意图识别日志，不显示
  if (!content && !isLoading && intentLogs.length === 0) return null

  // 计算总内容长度（只计算意图识别相关内容）
  const totalLength = content.length + intentLogs.reduce((acc, log) => acc + log.content.length, 0)

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
          {totalLength > 0 && (
            <span className="text-xs text-gray-500">
              {totalLength} 字
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
          isExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="px-4 py-3 border-t border-white/5 overflow-y-auto max-h-[480px]">
          {/* 流式思考内容（意图识别） */}
          {content && (
            <div className="mb-4">
              <div className="text-xs font-medium text-violet-400 mb-1.5 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full" />
                意图识别
              </div>
              <div className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap bg-dark-700/30 rounded-lg p-3">
                {content}
                {/* 闪烁光标效果 - 仅在加载时显示 */}
                {isLoading && intentLogs.length === 0 && (
                  <span className="inline-block w-2 h-4 ml-0.5 bg-violet-400/70 animate-pulse" />
                )}
              </div>
            </div>
          )}

          {/* 仅当没有流式内容时，显示历史保存的意图识别日志 */}
          {!content && intentLogs.map((log, index) => (
            <div key={`${log.step_id}-${index}`} className="mb-4 last:mb-0">
              <div className="text-xs font-medium text-violet-400 mb-1.5 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full" />
                {log.step_name}
              </div>
              <div className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap bg-dark-700/30 rounded-lg p-3">
                {log.content}
              </div>
            </div>
          ))}

          {/* 加载状态（没有任何内容时） */}
          {!content && intentLogs.length === 0 && isLoading && (
            <div className="text-sm text-gray-500 italic flex items-center gap-2">
              <span>正在分析...</span>
              <span className="inline-block w-2 h-4 bg-violet-400/70 animate-pulse" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
