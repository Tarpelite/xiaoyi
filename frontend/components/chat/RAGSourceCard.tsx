'use client'

import { useState } from 'react'
import { FileText, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import type { RAGSource } from '@/lib/api/analysis'

interface RAGSourceCardProps {
  sources: RAGSource[]
}

/**
 * RAG 研报来源卡片组件
 *
 * 展示 RAG 检索到的研报来源，包括：
 * - 文件名
 * - 页码定位
 * - 内容摘要
 * - 相关度分数
 */
export function RAGSourceCard({ sources }: RAGSourceCardProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  if (!sources || sources.length === 0) {
    return null
  }

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index)
  }

  // 根据分数获取颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-400 bg-green-500/10 border-green-500/20'
    if (score >= 0.6) return 'text-blue-400 bg-blue-500/10 border-blue-500/20'
    if (score >= 0.4) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20'
    return 'text-gray-400 bg-gray-500/10 border-gray-500/20'
  }

  // 根据分数获取相关度文字
  const getScoreLabel = (score: number) => {
    if (score >= 0.8) return '高度相关'
    if (score >= 0.6) return '较为相关'
    if (score >= 0.4) return '一般相关'
    return '参考价值'
  }

  return (
    <div className="space-y-2">
      {sources.map((source, index) => (
        <div
          key={`${source.filename}-${source.page}-${index}`}
          className="bg-dark-700/40 rounded-lg border border-white/5 overflow-hidden transition-all duration-200 hover:border-violet-500/30"
        >
          {/* 头部：文件名、页码、相关度 */}
          <button
            onClick={() => toggleExpand(index)}
            className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-dark-600/30 transition-colors"
          >
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <FileText className="w-4 h-4 text-violet-400 flex-shrink-0" />
              <span className="text-sm text-gray-200 truncate font-medium">
                {source.filename}
              </span>
              <span className="text-xs text-gray-500 flex-shrink-0">
                第 {source.page} 页
              </span>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
              {/* 相关度标签 */}
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded border ${getScoreColor(source.score)}`}
              >
                {getScoreLabel(source.score)} {(source.score * 100).toFixed(0)}%
              </span>
              {expandedIndex === index ? (
                <ChevronUp className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              )}
            </div>
          </button>

          {/* 展开内容：摘要 */}
          {expandedIndex === index && source.content_snippet && (
            <div className="px-3 pb-3 border-t border-white/5">
              <div className="mt-2 text-xs text-gray-400 leading-relaxed bg-dark-800/50 rounded p-2">
                <p className="line-clamp-4">{source.content_snippet}</p>
              </div>
              {/* 快捷操作 */}
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    // TODO: 实现研报预览功能
                    const ragUrl = `rag://${source.filename}#page=${source.page}`
                    alert(`研报来源: ${source.filename}\n页码: ${source.page}\n\n链接: ${ragUrl}`)
                  }}
                  className="flex items-center gap-1 text-[10px] text-violet-400 hover:text-violet-300 transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  查看原文
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

/**
 * 紧凑版 RAG 来源展示（用于有限空间）
 */
export function RAGSourceCompact({ sources }: RAGSourceCardProps) {
  if (!sources || sources.length === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {sources.slice(0, 3).map((source, index) => (
        <span
          key={`${source.filename}-${source.page}-${index}`}
          className="inline-flex items-center gap-1 text-[10px] text-violet-400 bg-violet-500/10 px-2 py-1 rounded-full border border-violet-500/20 hover:bg-violet-500/20 cursor-pointer transition-colors"
          title={`${source.filename} - 第${source.page}页 (相关度: ${(source.score * 100).toFixed(0)}%)`}
          onClick={() => {
            alert(`研报来源: ${source.filename}\n页码: ${source.page}\n相关度: ${(source.score * 100).toFixed(0)}%\n\n摘要:\n${source.content_snippet}`)
          }}
        >
          <FileText className="w-3 h-3" />
          <span className="truncate max-w-[120px]">{source.filename}</span>
          <span className="text-violet-300/60">p.{source.page}</span>
        </span>
      ))}
      {sources.length > 3 && (
        <span className="text-[10px] text-gray-500 px-2 py-1">
          +{sources.length - 3} 更多
        </span>
      )}
    </div>
  )
}
