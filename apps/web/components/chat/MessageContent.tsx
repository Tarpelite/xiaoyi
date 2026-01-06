'use client'

import { useState, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush } from 'recharts'
import { ZoomIn, RotateCcw } from 'lucide-react'
import type { TextContent, ChartContent, TableContent } from './ChatArea'

interface MessageContentProps {
  content: TextContent | ChartContent | TableContent
}

export function MessageContent({ content }: MessageContentProps) {
  if (content.type === 'text') {
    return (
      <div className="prose prose-invert max-w-none">
        <ReactMarkdown
          components={{
            strong: ({ children }) => <strong className="font-semibold text-violet-300">{children}</strong>,
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
            li: ({ children }) => <li className="text-gray-300">{children}</li>,
            code: ({ children }) => (
              <code className="px-1.5 py-0.5 bg-dark-600 rounded text-sm text-violet-300">{children}</code>
            ),
          }}
        >
          {content.text}
        </ReactMarkdown>
      </div>
    )
  }

  if (content.type === 'chart') {
    return <InteractiveChart content={content} />
  }

  if (content.type === 'table') {
    const { title, headers, rows } = content

    return (
      <div className="mt-2 overflow-x-auto">
        {title && (
          <h4 className="text-sm font-medium text-gray-300 mb-3">{title}</h4>
        )}
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-white/10">
              {headers.map((header, index) => (
                <th
                  key={index}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-white/5 hover:bg-dark-600/30 transition-colors"
              >
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    className="px-4 py-2 text-sm text-gray-300"
                  >
                    {typeof cell === 'number' ? cell.toLocaleString() : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return null
}

// 交互式图表组件（支持区间选择和放大）
function InteractiveChart({ content }: { content: ChartContent }) {
  const { title, data, chartType = 'line' } = content
  
  // 转换数据格式为 Recharts 格式
  const fullChartData = useMemo(() => {
    return data.labels.map((label, index) => {
      const item: Record<string, string | number> = { name: label }
      data.datasets.forEach((dataset) => {
        item[dataset.label] = dataset.data[index]
      })
      return item
    })
  }, [data])

  // 区间选择状态
  const [brushIndex, setBrushIndex] = useState<{ startIndex?: number; endIndex?: number }>({})
  const [isZoomed, setIsZoomed] = useState(false)

  // 根据选中的区间过滤数据
  const displayData = useMemo(() => {
    if (!isZoomed || brushIndex.startIndex === undefined || brushIndex.endIndex === undefined) {
      return fullChartData
    }
    const start = Math.max(0, brushIndex.startIndex)
    const end = Math.min(fullChartData.length - 1, brushIndex.endIndex)
    return fullChartData.slice(start, end + 1)
  }, [fullChartData, brushIndex, isZoomed])

  // 处理 Brush 变化
  const handleBrushChange = (newBrushIndex: any) => {
    // Recharts Brush onChange 可能返回不同的格式
    if (newBrushIndex && typeof newBrushIndex === 'object') {
      setBrushIndex({
        startIndex: newBrushIndex.startIndex,
        endIndex: newBrushIndex.endIndex,
      })
    }
  }

  // 放大到选中区间
  const handleZoomIn = () => {
    if (brushIndex.startIndex !== undefined && brushIndex.endIndex !== undefined) {
      setIsZoomed(true)
    }
  }

  // 重置视图
  const handleReset = () => {
    setIsZoomed(false)
    setBrushIndex({})
  }

  const colors = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']
  const hasSelection = brushIndex.startIndex !== undefined && brushIndex.endIndex !== undefined
  const canZoom = hasSelection && !isZoomed

  return (
    <div className="mt-2">
      {/* 标题和操作按钮 */}
      <div className="flex items-center justify-between mb-3">
        {title && (
          <h4 className="text-sm font-medium text-gray-300">{title}</h4>
        )}
        <div className="flex items-center gap-2">
          {canZoom && (
            <button
              onClick={handleZoomIn}
              className="p-1.5 hover:bg-dark-600 rounded-lg transition-colors text-gray-400 hover:text-violet-400"
              title="放大选中区间"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          )}
          {isZoomed && (
            <button
              onClick={handleReset}
              className="p-1.5 hover:bg-dark-600 rounded-lg transition-colors text-gray-400 hover:text-violet-400"
              title="重置视图"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* 主图表 */}
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={displayData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#3a3a4a" />
            <XAxis 
              dataKey="name" 
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
              angle={displayData.length > 20 ? -45 : 0}
              textAnchor={displayData.length > 20 ? 'end' : 'middle'}
              height={displayData.length > 20 ? 60 : 30}
            />
            <YAxis 
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1a24',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Legend />
            {data.datasets.map((dataset, index) => (
              <Line
                key={dataset.label}
                type="monotone"
                dataKey={dataset.label}
                stroke={dataset.color || colors[index % colors.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
            ))}
            {/* Brush 组件用于区间选择 */}
            {!isZoomed && (
              <Brush
                dataKey="name"
                height={30}
                stroke="#8b5cf6"
                fill="rgba(139, 92, 246, 0.1)"
                onChange={handleBrushChange}
                startIndex={brushIndex.startIndex}
                endIndex={brushIndex.endIndex}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 选中区间提示 */}
      {hasSelection && !isZoomed && (
        <div className="mt-2 text-xs text-gray-500 flex items-center gap-2">
          <span>
            已选择区间: {fullChartData[brushIndex.startIndex!]?.name} 至 {fullChartData[brushIndex.endIndex!]?.name}
          </span>
          <button
            onClick={handleZoomIn}
            className="text-violet-400 hover:text-violet-300 underline"
          >
            点击放大
          </button>
        </div>
      )}
    </div>
  )
}

