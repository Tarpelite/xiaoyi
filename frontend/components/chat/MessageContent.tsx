'use client'

import ReactMarkdown from 'react-markdown'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
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
    const { title, data, chartType = 'line' } = content
    
    // 转换数据格式为 Recharts 格式
    const chartData = data.labels.map((label, index) => {
      const item: Record<string, string | number> = { name: label }
      data.datasets.forEach((dataset) => {
        item[dataset.label] = dataset.data[index]
      })
      return item
    })

    const colors = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

    return (
      <div className="mt-2">
        {title && (
          <h4 className="text-sm font-medium text-gray-300 mb-3">{title}</h4>
        )}
        <div className="w-full h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3a3a4a" />
              <XAxis 
                dataKey="name" 
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
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
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
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

