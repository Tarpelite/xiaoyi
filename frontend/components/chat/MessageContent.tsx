'use client'

import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { RotateCcw, Move } from 'lucide-react'
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

// 交互式图表组件，支持鼠标拖拽平移和滚轮缩放
function InteractiveChart({ content }: { content: ChartContent }) {
  const { title, data, chartType = 'line' } = content
  
  // 转换数据格式为 Recharts 格式
  const chartData = useMemo(() => {
    return data.labels.map((label, index) => {
      const item: Record<string, string | number> = { name: label }
      data.datasets.forEach((dataset) => {
        item[dataset.label] = dataset.data[index]
      })
      return item
    })
  }, [data])

  const colors = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

  // 状态管理：视图范围（显示的数据索引范围）
  const [viewStartIndex, setViewStartIndex] = useState(0)
  const [viewEndIndex, setViewEndIndex] = useState(() => chartData.length - 1)
  
  // 拖拽状态
  const [isDragging, setIsDragging] = useState(false)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragStartIndex, setDragStartIndex] = useState(0)
  
  // 图表容器引用
  const chartContainerRef = useRef<HTMLDivElement>(null)

  // 计算当前显示的数据
  const displayData = useMemo(() => {
    return chartData.slice(viewStartIndex, viewEndIndex + 1)
  }, [chartData, viewStartIndex, viewEndIndex])

  // 检查是否处于缩放状态
  const isZoomed = (viewEndIndex - viewStartIndex + 1) < chartData.length

  // 鼠标按下开始拖拽
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) { // 左键
      setIsDragging(true)
      setDragStartX(e.clientX)
      setDragStartIndex(viewStartIndex)
      e.preventDefault()
    }
  }, [viewStartIndex])

  // 鼠标移动拖拽
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !chartContainerRef.current) return

    const container = chartContainerRef.current
    const containerWidth = container.clientWidth
    const deltaX = dragStartX - e.clientX // 反转方向：向左拖拽显示更早的数据
    const dataRange = viewEndIndex - viewStartIndex + 1
    const pixelsPerDataPoint = containerWidth / dataRange
    
    // 计算应该移动的数据点数量
    const dataPointsToMove = Math.round(deltaX / pixelsPerDataPoint)
    const newStartIndex = dragStartIndex + dataPointsToMove
    
    // 限制在有效范围内
    const minStart = 0
    const maxStart = Math.max(0, chartData.length - dataRange)
    
    const clampedStart = Math.max(minStart, Math.min(maxStart, newStartIndex))
    const clampedEnd = clampedStart + dataRange - 1
    
    if (clampedStart !== viewStartIndex || clampedEnd !== viewEndIndex) {
      setViewStartIndex(clampedStart)
      setViewEndIndex(clampedEnd)
    }
  }, [isDragging, dragStartX, dragStartIndex, viewStartIndex, viewEndIndex, chartData.length])

  // 鼠标释放结束拖拽
  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  // 滚轮缩放处理函数
  const handleWheel = useCallback((e: WheelEvent) => {
    if (!chartContainerRef.current) return
    
    const container = chartContainerRef.current
    const rect = container.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    
    // 检查鼠标是否在图表容器内
    if (mouseX < 0 || mouseX > rect.width || mouseY < 0 || mouseY > rect.height) {
      return
    }
    
    // 阻止默认滚动行为
    e.preventDefault()
    e.stopPropagation()
    
    const containerWidth = rect.width
    
    // 计算鼠标位置对应的数据点索引（相对于当前视图）
    const currentRange = viewEndIndex - viewStartIndex + 1
    const mousePositionRatio = mouseX / containerWidth
    const focusIndex = Math.round(viewStartIndex + mousePositionRatio * currentRange)
    
    // 缩放因子（向上滚动放大，向下滚动缩小）
    const zoomFactor = e.deltaY > 0 ? 1.15 : 0.85
    const newRange = Math.round(currentRange * zoomFactor)
    
    // 限制缩放范围
    const minRange = 5 // 最少显示5个数据点
    const maxRange = chartData.length // 最多显示全部数据
    
    const clampedRange = Math.max(minRange, Math.min(maxRange, newRange))
    
    // 以鼠标位置为中心进行缩放
    const newStartIndex = Math.max(0, Math.min(
      chartData.length - clampedRange,
      Math.round(focusIndex - mousePositionRatio * clampedRange)
    ))
    const newEndIndex = newStartIndex + clampedRange - 1
    
    setViewStartIndex(newStartIndex)
    setViewEndIndex(newEndIndex)
  }, [viewStartIndex, viewEndIndex, chartData.length])

  // 当数据变化时重置视图
  useEffect(() => {
    setViewStartIndex(0)
    setViewEndIndex(chartData.length - 1)
  }, [chartData.length])

  // 添加滚轮事件监听（使用原生事件以正确阻止默认行为）
  useEffect(() => {
    const container = chartContainerRef.current
    if (!container) return

    // 使用 { passive: false } 确保可以调用 preventDefault
    container.addEventListener('wheel', handleWheel, { passive: false })
    
    return () => {
      container.removeEventListener('wheel', handleWheel)
    }
  }, [handleWheel])

  // 添加全局鼠标事件监听
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  // 重置视图
  const handleReset = useCallback(() => {
    setViewStartIndex(0)
    setViewEndIndex(chartData.length - 1)
  }, [chartData.length])

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between mb-3">
        {title && (
          <h4 className="text-sm font-medium text-gray-300">{title}</h4>
        )}
        <div className="flex items-center gap-2">
          {isZoomed && (
            <>
              <button
                onClick={handleReset}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-gray-400 hover:text-gray-200 bg-dark-600/50 hover:bg-dark-600 rounded-lg transition-colors"
                title="重置视图"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>重置</span>
              </button>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <Move className="w-3.5 h-3.5" />
                <span>拖拽平移 | 滚轮缩放</span>
              </div>
            </>
          )}
          {!isZoomed && (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Move className="w-3.5 h-3.5" />
              <span>点击图表后：拖拽平移 | 滚轮缩放</span>
            </div>
          )}
        </div>
      </div>
      <div 
        ref={chartContainerRef}
        className="w-full h-64 relative"
        onMouseDown={handleMouseDown}
        style={{ 
          cursor: isDragging ? 'grabbing' : 'grab',
          userSelect: 'none'
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart 
            data={displayData}
            margin={{ top: 5, right: 10, left: 0, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#3a3a4a" />
            <XAxis 
              dataKey="name" 
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
              angle={isZoomed ? -45 : 0}
              textAnchor={isZoomed ? "end" : "middle"}
              height={isZoomed ? 60 : 30}
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
            <Legend 
              wrapperStyle={{ fontSize: '12px' }}
            />
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
          </LineChart>
        </ResponsiveContainer>
      </div>
      {isZoomed && (
        <div className="mt-2 text-xs text-gray-500 text-center">
          当前视图：{chartData[viewStartIndex]?.name} 至 {chartData[viewEndIndex]?.name} 
          ({viewEndIndex - viewStartIndex + 1} / {chartData.length} 个数据点)
        </div>
      )}
    </div>
  )
}

