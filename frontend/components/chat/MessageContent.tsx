'use client'

import { useState, useMemo, useRef, useCallback, useEffect, Fragment } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LineChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine, ReferenceArea, ReferenceDot, Label } from 'recharts'
import { RotateCcw, Move, Sparkles } from 'lucide-react'
import type { TextContent, ChartContent, TableContent, StockContent } from './ChatArea'
import { useBacktestSimulation } from '@/hooks/useBacktestSimulation'
import { BacktestControls } from './BacktestControls'
import type { TimeSeriesPoint } from '@/lib/api/analysis'
import rehypeRaw from 'rehype-raw'
import { StockWidget } from '@/components/stock/StockWidget'
import { ChartNewsSidebar } from './ChartNewsSidebar'


interface MessageContentProps {
  content: TextContent | ChartContent | TableContent | StockContent
}

// 预处理 markdown 文本，确保带正负号的数字加粗能正确解析
function preprocessMarkdown(text: string): string {
  let processed = text

  // 全角归一化
  processed = processed.replace(/＋/g, '+').replace(/－/g, '-')

  // 🚀 直接把 **+3.70%** 变成 <strong>+3.70%</strong>
  processed = processed.replace(
    /\*\*\s*([+-]\d+(?:\.\d+)?[%元]?)\s*\*\*/g,
    '<strong>$1</strong>'
  )

  return processed
}





const PortalTooltip = ({ children, style }: { children: React.ReactNode, style?: React.CSSProperties }) => {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
    return () => setMounted(false)
  }, [])
  if (!mounted) return null
  return createPortal(
    <div style={{ position: 'fixed', zIndex: 9999, ...style }}>{children}</div>,
    document.body
  )
}

// AlgoSelect Component
const AlgoSelect: React.FC<{ label: string; value: string; options: { label: string; value: string }[]; onChange: (v: string) => void }> = ({ label, value, options, onChange }) => (
  <div className="flex items-center gap-2 bg-gray-800/80 px-3 py-1.5 rounded-lg border border-gray-700 shadow-sm transition-colors hover:border-violet-500/50">
    <span className="text-xs text-gray-400 font-medium whitespace-nowrap">{label}</span>
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent text-xs text-gray-200 outline-none appearance-none pr-6 cursor-pointer font-medium hover:text-violet-400 transition-colors w-full"
      >
        {options.map(opt => <option key={opt.value} value={opt.value} className="bg-gray-800 text-gray-300">{opt.label}</option>)}
      </select>
      <div className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500">
        <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  </div>
);

export function MessageContent({ content }: MessageContentProps) {
  if (content.type === 'text') {
    // 预处理文本，确保加粗格式正确
    const processedText = preprocessMarkdown(content.text)

    return (
      <div className="prose prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            strong: ({ children }) => (
              <strong className="font-semibold text-violet-300">
                {children}
              </strong>
            ),
            // 标题
            h1: ({ children }) => <h1 className="text-2xl font-bold text-gray-200 mb-3 mt-4 first:mt-0">{children}</h1>,
            h2: ({ children }) => <h2 className="text-xl font-bold text-gray-200 mb-2 mt-4 first:mt-0">{children}</h2>,
            h3: ({ children }) => <h3 className="text-lg font-semibold text-gray-200 mb-2 mt-3 first:mt-0">{children}</h3>,
            h4: ({ children }) => <h4 className="text-base font-semibold text-gray-200 mb-2 mt-3 first:mt-0">{children}</h4>,
            h5: ({ children }) => <h5 className="text-sm font-semibold text-gray-200 mb-1 mt-2 first:mt-0">{children}</h5>,
            h6: ({ children }) => <h6 className="text-sm font-medium text-gray-300 mb-1 mt-2 first:mt-0">{children}</h6>,
            // 段落
            p: ({ children }) => <p className="mb-2 last:mb-0 text-gray-300 leading-relaxed">{children}</p>,
            em: ({ children }) => <em className="italic text-gray-200">{children}</em>,
            // 列表
            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1 text-gray-300">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1 text-gray-300">{children}</ol>,
            li: ({ children }) => <li className="text-gray-300">{children}</li>,
            // 代码
            code: ({ className, children, ...props }: any) => {
              const isInline = !className
              return isInline ? (
                <code className="px-1.5 py-0.5 bg-dark-600 rounded text-sm text-violet-300 font-mono" {...props}>
                  {children}
                </code>
              ) : (
                <code className="block p-3 bg-dark-700 rounded-lg text-sm text-gray-300 font-mono overflow-x-auto mb-2" {...props}>
                  {children}
                </code>
              )
            },
            pre: ({ children }) => (
              <pre className="bg-dark-700 rounded-lg p-3 overflow-x-auto mb-2">{children}</pre>
            ),
            // 表格
            table: ({ children }) => (
              <div className="overflow-x-auto my-3">
                <table className="w-full border-collapse border border-white/10">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-dark-700/50">{children}</thead>
            ),
            tbody: ({ children }) => (
              <tbody>{children}</tbody>
            ),
            tr: ({ children }) => (
              <tr className="border-b border-white/5 hover:bg-dark-600/30 transition-colors">{children}</tr>
            ),
            th: ({ children }) => (
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider border border-white/10">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-4 py-2 text-sm text-gray-300 border border-white/5">
                {children}
              </td>
            ),
            // 链接
            a: ({ href, children }) => {
              // 处理 rag:// 协议（研报链接）
              if (href?.startsWith('rag://')) {
                // 解析 rag://文件名.pdf#page=页码 格式
                const match = href.match(/^rag:\/\/(.+?)(?:#page=(\d+))?$/)
                const filename = match?.[1] || href.replace('rag://', '')
                const page = match?.[2] || '1'
                return (
                  <span
                    className="text-violet-400 hover:text-violet-300 cursor-pointer underline"
                    title={`研报: ${filename} 第${page}页`}
                    onClick={() => {
                      // TODO: 可以打开研报预览弹窗
                      alert(`研报来源: ${filename}\n页码: ${page}`)
                    }}
                  >
                    {children}
                  </span>
                )
              }
              // 普通链接
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-violet-400 hover:text-violet-300 underline"
                >
                  {children}
                </a>
              )
            },
            // 引用
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-violet-500/50 pl-4 py-2 my-2 bg-dark-700/30 italic text-gray-300">
                {children}
              </blockquote>
            ),
            // 水平线
            hr: () => <hr className="my-4 border-white/10" />,
            // 换行
            br: () => <br />,
          }}
        >
          {processedText}
        </ReactMarkdown>
      </div>
    )
  }

  if (content.type === 'chart') {
    return <InteractiveChart content={content} />
  }

  if (content.type === 'table') {
    const { title, headers, rows } = content

    // 解析 markdown 链接格式 [text](url)
    // 使用更健壮的解析方式，处理标题中含有 [ 或 ] 的情况
    const parseMarkdownLink = (text: string): { text: string; url?: string } => {
      // 查找最后一个 ]( 来分割标题和URL
      const lastBracket = text.lastIndexOf('](')
      if (text.startsWith('[') && lastBracket > 0 && text.endsWith(')')) {
        const title = text.slice(1, lastBracket)
        const url = text.slice(lastBracket + 2, -1)
        if (url && url.startsWith('http')) {
          return { text: title, url }
        }
      }
      return { text }
    }

    // 渲染单元格内容（支持链接）
    const renderCell = (cell: string | number, cellIndex: number) => {
      if (typeof cell === 'number') {
        return cell.toLocaleString()
      }

      // 检查是否是 markdown 链接格式
      const parsed = parseMarkdownLink(cell)

      if (parsed.url) {
        // 有链接，渲染为可点击的链接
        const displayText = parsed.text.length > 25
          ? parsed.text.substring(0, 25) + '...'
          : parsed.text
        return (
          <a
            href={parsed.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-violet-400 hover:text-violet-300 hover:underline transition-colors"
            title={parsed.text} // 鼠标悬停显示完整标题
          >
            {displayText}
          </a>
        )
      }

      // 第一列是标题，如果超过25个字则截断
      if (cellIndex === 0 && cell.length > 25) {
        return (
          <span title={cell}>
            {cell.substring(0, 25)}...
          </span>
        )
      }

      return cell
    }

    return (
      <div className="mt-2 overflow-x-auto max-h-80 overflow-y-auto">
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
                    {renderCell(cell, cellIndex)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (content.type === 'stock') {
    return <StockWidget ticker={content.ticker} title={content.title} />;
  }

  return null
}

// 交互式图表组件，支持鼠标拖拽平移、滚轮缩放、异常区高亮、新闻侧边栏
function InteractiveChart({ content }: { content: ChartContent }) {
  const { title, data, chartType = 'line', sessionId, messageId, originalData, anomalyZones = [], semantic_zones = [], prediction_semantic_zones = [], ticker, anomalies = [], predictionStartDay } = content as any

  // 新闻侧边栏状态
  const [newsSidebarOpen, setNewsSidebarOpen] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [newsData, setNewsData] = useState<any[]>([])
  const [newsLoading, setNewsLoading] = useState(false)

  // 异常区悬浮状态
  const [activeZone, setActiveZone] = useState<any>(null)

  // Algorithm Selection State - Default to 'plr'
  const [trendAlgo, setTrendAlgo] = useState<string>('plr');
  const [anomalyAlgo, setAnomalyAlgo] = useState<string>('all');
  const [useSemanticRegimes, setUseSemanticRegimes] = useState(true); // Toggle for new view

  // 从URL恢复新闻侧栏状态（仅在ticker可用时）
  useEffect(() => {
    if (!ticker) return;

    const urlParams = new URLSearchParams(window.location.search);
    const savedDate = urlParams.get('selectedDate');
    const savedSidebarOpen = urlParams.get('sidebarOpen') === 'true';

    if (savedDate) {
      setSelectedDate(savedDate);
      setNewsSidebarOpen(savedSidebarOpen);
      // console.log('[MessageContent] Restored from URL - date:', savedDate, 'sidebar:', savedSidebarOpen);
    }
  }, [ticker]); // 只在ticker变化时执行

  // 获取新闻数据 - 只要有ticker就自动加载（确保刷新后能恢复）
  useEffect(() => {
    const fetchNews = async () => {
      if (!selectedDate || !ticker) return;
      setNewsLoading(true);
      try {
        const response = await fetch(`/api/news?ticker=${ticker}&date=${selectedDate}&range=2`);
        if (!response.ok) throw new Error('Failed to fetch news');
        const data = await response.json();

        const newsItems = data.news || [];
        console.log(`[NewsFetch] Loaded ${newsItems.length} items for date ${selectedDate}`);

        // Safety cap to prevent browser freeze if backend returns too much data
        if (newsItems.length > 500) {
          console.warn('[NewsFetch] Too many news items, capping at 500');
          setNewsData(newsItems.slice(0, 500));
        } else {
          setNewsData(newsItems);
        }
      } catch (error) {
        console.error('Failed to load news:', error);
        setNewsData([]);
      } finally {
        setNewsLoading(false);
      }
    };
    fetchNews();
  }, [selectedDate, ticker]);  // 移除newsSidebarOpen依赖，确保刷新后自动加载

  // Debug: Log semantic zones data
  useEffect(() => {
    // console.log('[SEMANTIC DATA] semantic_zones:', semantic_zones);
    // console.log('[SEMANTIC DATA] prediction_semantic_zones:', prediction_semantic_zones);
    // console.log('[SEMANTIC DATA] anomalyZones:', anomalyZones);
    // console.log('[SEMANTIC DATA] anomalies:', anomalies);

    if (semantic_zones && semantic_zones.length > 0) {
      // console.log('[SEMANTIC DATA] First semantic zone:', semantic_zones[0]);
      // console.log('[SEMANTIC DATA] First zone events:', semantic_zones[0].events);
    }
  }, [semantic_zones, prediction_semantic_zones, anomalyZones, anomalies]);

  // 图表点击处理
  const handleChartClick = useCallback((e: any) => {
    console.log('[ChartClick] Event received:', e);
    if (e && e.activeLabel && ticker) {
      const date = e.activeLabel as string;
      console.log('[ChartClick] Setting selected date:', date);
      setSelectedDate(date);
      setNewsSidebarOpen(true);

      // 持久化到URL
      const params = new URLSearchParams(window.location.search);
      params.set('selectedDate', date);
      params.set('sidebarOpen', 'true');
      window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
    } else {
      console.warn('[ChartClick] Missing required data:', { activeLabel: e?.activeLabel, ticker });
    }
  }, [ticker]);

  // 新闻侧栏关闭处理
  const handleCloseSidebar = useCallback(() => {
    setNewsSidebarOpen(false);

    // 更新URL参数
    const params = new URLSearchParams(window.location.search);
    params.set('sidebarOpen', 'false');
    window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
  }, []);

  // 回测功能hook
  const backtest = useBacktestSimulation({
    sessionId: sessionId || '',
    messageId: messageId || '',
    originalData: originalData || []
  })

  const hasBacktestSupport = Boolean(sessionId && messageId && originalData && originalData.length >= 60)

  // 周末过滤函数
  const isWeekday = (dateStr: string): boolean => {
    try {
      const date = new Date(dateStr)
      const day = date.getDay() // 0=Sunday, 6=Saturday
      return day !== 0 && day !== 6 // 过滤掉周日和周六
    } catch {
      return true // 解析失败则保留
    }
  }
  // 转换数据格式为 Recharts 格式
  const chartData = useMemo(() => {
    // 如果在回测模式，使用回测数据
    if (backtest.chartData) {
      const { history, groundTruth, prediction } = backtest.chartData

      // 合并所有数据点
      const allDates = new Set<string>()
      history.forEach(p => allDates.add(p.date))
      groundTruth.forEach(p => allDates.add(p.date))
      prediction.forEach(p => allDates.add(p.date))

      const sortedDates = Array.from(allDates).sort()

      return sortedDates
        .filter(date => isWeekday(date))
        .map(date => {
          const histPoint = history.find(p => p.date === date)
          const truthPoint = groundTruth.find(p => p.date === date)
          const predPoint = prediction.find(p => p.date === date)

          return {
            name: date,
            历史价格: histPoint?.value ?? null,
            实际值: truthPoint?.value ?? null,
            回测预测: predPoint?.value ?? null
          }
        })
    }

    // 正常模式
    return data.labels.map((label: any, index: any) => {
      const item: Record<string, string | number | null> = { name: label }
      data.datasets.forEach((dataset: any) => {
        item[dataset.label] = dataset.data[index]
      })
      return item
    }).filter((item: any) => isWeekday(item.name as string))
  }, [data, backtest.chartData])

  // 计算Y轴范围（自适应）- 基于所有数据，保持一致性
  const yAxisDomain = useMemo(() => {
    // 收集所有非null的数值
    const allValues: number[] = []
    chartData.forEach((item: any) => {
      data.datasets.forEach((dataset: any) => {
        const value = item[dataset.label]
        if (value !== null && value !== undefined && typeof value === 'number' && !isNaN(value)) {
          allValues.push(value)
        }
      })
    })

    if (allValues.length === 0) {
      return [0, 100] // 默认范围
    }

    const minValue = Math.min(...allValues)
    const maxValue = Math.max(...allValues)

    // 如果所有值相同，添加一些范围
    if (minValue === maxValue) {
      const padding = Math.abs(minValue) * 0.1 || 10
      return [minValue - padding, maxValue + padding]
    }

    // 计算范围，留出10%的边距
    const range = maxValue - minValue
    const padding = range * 0.1

    // 确保最小值不为负数（如果所有值都为正）
    const adjustedMin = minValue >= 0
      ? Math.max(0, minValue - padding)
      : minValue - padding

    const adjustedMax = maxValue + padding

    // 确保返回的是数字数组，保留合理精度
    return [Math.round(adjustedMin * 100) / 100, Math.round(adjustedMax * 100) / 100]
  }, [chartData, data.datasets])

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
  const [mouseY, setMouseY] = useState<number | null>(null) // 鼠标相对于绘图区域的Y坐标（像素）
  const [mouseX, setMouseX] = useState<number | null>(null) // 鼠标相对于绘图区域的X坐标（像素）
  const [plotAreaBounds, setPlotAreaBounds] = useState<{ top: number; height: number; left: number; width: number } | null>(null) // 绘图区域边界

  // 滑块拖拽状态
  const [isDraggingSlider, setIsDraggingSlider] = useState(false)
  const [tempSplitDate, setTempSplitDate] = useState<string | null>(null) // 拖拽时的临时分割日期
  const [activeCoordinateX, setActiveCoordinateX] = useState<number | null>(null); // Visual X for perfect alignment

  // 计算当前显示的数据
  const displayData = useMemo(() => {
    return chartData.slice(viewStartIndex, viewEndIndex + 1)
  }, [chartData, viewStartIndex, viewEndIndex])

  // DIAGNOSTIC: Check if zone dates exist in chartData AND their positions
  useEffect(() => {
    if (anomalyZones && anomalyZones.length > 0 && chartData.length > 0) {
      const chartDates = new Set(chartData.map((d: any) => d.name))
      // console.log('[DIAGNOSTIC] chartData range:', chartData[0]?.name, 'to', chartData[chartData.length - 1]?.name, `(${chartData.length} points)`)
      // console.log('[DIAGNOSTIC] viewStartIndex:', viewStartIndex, 'viewEndIndex:', viewEndIndex, 'visible:', viewEndIndex - viewStartIndex + 1, 'points')

      anomalyZones.forEach((zone: any, idx: any) => {
        const startIndex = chartData.findIndex((d: any) => d.name === zone.startDate)
        const endIndex = chartData.findIndex((d: any) => d.name === zone.endDate)
        const isInViewport = startIndex >= viewStartIndex && endIndex <= viewEndIndex
        const hasStart = chartDates.has(zone.startDate)
        const hasEnd = chartDates.has(zone.endDate)

        // console.log(`[DIAGNOSTIC] Zone ${idx} (${zone.startDate}-${zone.endDate}): start=${hasStart}(idx=${startIndex}), end=${hasEnd}(idx=${endIndex}), inViewport=${isInViewport}`)
      })
    }
  }, [anomalyZones, chartData, viewStartIndex, viewEndIndex])

  // Debug: Log anomaly data when received
  useEffect(() => {
    if (anomalies && anomalies.length > 0) {
      // console.log(`[Anomaly Rendering] Received ${anomalies.length} anomalies:`, anomalies);
      // console.log('[Anomaly Rendering] Chart Y-axis domain:', yAxisDomain);
      // console.log('[Anomaly Rendering] Chart date range:', chartData[0]?.name, 'to', chartData[chartData.length - 1]?.name);

      // Check which anomalies are in valid date range
      const chartDates = new Set(chartData.map((d: any) => d.name));
      anomalies.forEach((anom: any, idx: number) => {
        const inDateRange = chartDates.has(anom.date);
        const inYRange = anom.price >= yAxisDomain[0] && anom.price <= yAxisDomain[1];
        // console.log(`[Anomaly ${idx}] ${anom.method} at ${anom.date}: price=${anom.price}, inDateRange=${inDateRange}, inYRange=${inYRange}`);
      });
    }
  }, [anomalies, chartData, yAxisDomain]);

  // --- Semantic Regimes Logic ---
  const semanticRegimes = useMemo(() => {
    // 1. If Backend already provided Semantic Zones, use them directly!
    // This supports "Event Flow" feature and robust backend merging
    // 1. If Backend already provided Semantic Zones, use them directly!
    // This supports "Event Flow" feature and robust backend merging
    if (semantic_zones.length > 0 || (prediction_semantic_zones && prediction_semantic_zones.length > 0)) {
      // 1. Raw zones
      let historicalZones = semantic_zones.map((z: any) => ({ ...z, isPrediction: false }));
      let predictionZones = (prediction_semantic_zones || []).map((z: any) => ({ ...z, isPrediction: true }));

      // 2. Strict Interval Partitioning (if predictionStartDay is available)
      if (predictionStartDay) {
        // Historical: End at predictionStartDay (inclusive/exclusive boundary logic)
        historicalZones = historicalZones.map((z: any) => {
          // If zone starts after prediction start, discard it (it belongs to prediction)
          if (z.startDate >= predictionStartDay) return null;
          // If zone ends after prediction start, clip it
          if (z.endDate > predictionStartDay) return { ...z, endDate: predictionStartDay };
          return z;
        }).filter(Boolean);

        // Prediction: Start at predictionStartDay
        predictionZones = predictionZones.map((z: any) => {
          // If zone ends before prediction start, discard it (belongs to history)
          // But usually prediction zones are strictly after.
          if (z.endDate <= predictionStartDay) return null;
          // If zone starts before prediction start, clip it
          if (z.startDate < predictionStartDay) return { ...z, startDate: predictionStartDay };
          return z;
        }).filter(Boolean);
      }

      // 3. CRITICAL: Aggregate raw zones (anomalyZones) into semantic zones as events
      // This enables the "Event Flow" tooltip to show the timeline of raw zones
      const aggregateRawZones = (semanticZone: any) => {
        if (!anomalyZones || anomalyZones.length === 0) return semanticZone;

        // Find all raw zones that overlap with this semantic zone
        const overlappingRawZones = anomalyZones.filter((rawZone: any) => {
          const rawStart = new Date(rawZone.startDate).getTime();
          const rawEnd = new Date(rawZone.endDate).getTime();
          const semStart = new Date(semanticZone.startDate).getTime();
          const semEnd = new Date(semanticZone.endDate).getTime();

          // Check if there's any overlap
          return rawStart <= semEnd && rawEnd >= semStart;
        });

        // Convert raw zones to event format for tooltip display
        const events = overlappingRawZones.map((rawZone: any) => ({
          startDate: rawZone.startDate,
          endDate: rawZone.endDate,
          summary: rawZone.summary || rawZone.event_summary || 'Raw Zone Event',
          event_summary: rawZone.event_summary || rawZone.summary,
          avg_return: rawZone.avg_return,
          startPrice: rawZone.startPrice,
          endPrice: rawZone.endPrice,
          type: rawZone.type || rawZone.displayType || 'raw',
          sentiment: rawZone.sentiment
        }));

        return {
          ...semanticZone,
          events: events.length > 0 ? events : (semanticZone.events || [])
        };
      };

      // Apply aggregation to both historical and prediction zones
      historicalZones = historicalZones.map(aggregateRawZones);
      predictionZones = predictionZones.map(aggregateRawZones);

      // Merge history and prediction zones
      return [
        ...historicalZones,
        ...predictionZones
      ];
    }

    // 2. Fallback: Frontend Calculation (for legacy cache or other algos)
    if (!anomalyZones || anomalyZones.length === 0) return [];
    if (chartData.length === 0) return [];

    // 1. Sort zones by date
    const sortedZones = [...anomalyZones]
      .filter(z => trendAlgo === 'all' || (z.method || 'plr') === trendAlgo)
      .sort((a, b) => new Date(a.startDate).getTime() - new Date(b.startDate).getTime());

    if (sortedZones.length === 0) return [];

    // Helper to get price from chartData
    const getPrice = (date: string): number | null => {
      const point = chartData.find((d: any) => d.name === date);
      if (!point) return null;
      // Assume first dataset is the main price
      const label = data.datasets[0]?.label;
      return ((point as any)[label] as number) || null;
    };

    // 2. Merge Logic
    const merged: any[] = [];
    if (sortedZones.length === 0) return [];

    // let current removed to avoid redeclaration

    // Normalize type for comparison (up/down/sideways)
    const normalizeType = (type: string) => {
      const t = type?.toLowerCase() || '';
      if (t.includes('bull') || t.includes('up')) return 'up';
      if (t.includes('bear') || t.includes('down')) return 'down';
      return 'sideways';
    };

    // [New] Smooth out noise (Sandwich Logic): A(Up) -> B(Down) -> C(Up) => Merge B into Up
    // Fix: PLR returns 'direction', HMM returns 'type'. Map both to 'type'.
    const smoothedZones = (sortedZones as any[]).map(z => ({
      ...z,
      type: z.type || (z as any).direction || 'sideways'
    }));

    // 1-pass smoothing with Duration Check to avoid swallowing real corrections
    for (let pass = 0; pass < 1; pass++) {
      for (let i = 1; i < smoothedZones.length - 1; i++) {
        const prev: any = smoothedZones[i - 1];
        const curr: any = smoothedZones[i];
        const next: any = smoothedZones[i + 1];

        const prevType = normalizeType(prev.type);
        const currType = normalizeType(curr.type);
        const nextType = normalizeType(next.type);

        // If sandwiched between same types, flip current type IF it is short (noise)
        if (prevType === nextType && currType !== prevType) {
          const d1 = new Date(curr.startDate).getTime();
          const d2 = new Date(curr.endDate).getTime();
          const days = (d2 - d1) / (1000 * 3600 * 24);

          // Only treat as noise if < 7 days (1 week)
          if (days < 7) {
            curr.type = prev.type;
          }
        }
      }
    }

    if (smoothedZones.length === 0) return [];

    let current: any = { ...smoothedZones[0] };
    current.normalizedType = normalizeType(current.type);

    for (let i = 1; i < smoothedZones.length; i++) {
      const next: any = smoothedZones[i];
      const nextType = normalizeType(next.type);

      // Merge if same type and contiguous (or overlap/close)
      // Simple check: same type
      if (current.normalizedType === nextType) {
        // Extend current
        current.endDate = next.endDate;
        // Accumulate other props if needed
      } else {
        merged.push(current);
        current = { ...next, normalizedType: nextType };
      }
    }
    merged.push(current);

    // 3. Volatility / Efficiency Ratio Check & Final Enrichment
    return merged.map(regime => {
      const startPrice = getPrice(regime.startDate);
      const endPrice = getPrice(regime.endDate);

      let type = regime.normalizedType;
      let efficiencyRatio = 1.0;

      // Calculate Efficiency Ratio over the regime range
      if (startPrice !== null && endPrice !== null) {
        const startIndex = chartData.findIndex((d: any) => d.name === regime.startDate);
        const endIndex = chartData.findIndex((d: any) => d.name === regime.endDate);

        if (startIndex !== -1 && endIndex !== -1 && endIndex > startIndex) {
          const slice = chartData.slice(startIndex, endIndex + 1);
          const firstLabel = data.datasets[0]?.label;
          const prices = slice.map((d: any) => (d as any)[firstLabel] as number).filter((p: any) => p !== null);

          if (prices.length > 1) {
            const netChange = Math.abs(prices[prices.length - 1] - prices[0]);
            let sumAbsChange = 0;
            for (let k = 1; k < prices.length; k++) {
              sumAbsChange += Math.abs(prices[k] - prices[k - 1]);
            }
            efficiencyRatio = sumAbsChange === 0 ? 0 : netChange / sumAbsChange;

            // Identify anomalies/events within this regime
            const regimeEvents = (anomalies || []).filter((a: any) => {
              return a.date >= regime.startDate && a.date <= regime.endDate;
            });

            // Calculate total change
            const totalChange = (startPrice && endPrice)
              ? ((endPrice - startPrice) / startPrice * 100).toFixed(2) + '%'
              : 'N/A';

            return {
              ...regime,
              displayType: type,
              efficiencyRatio,
              totalChange,
              events: regimeEvents,
              startPrice,
              endPrice
            };
          }
        }
      }
      // If ER < 0.3, force sideways
      // If ER < 0.3, force sideways
      // DISABLED: PLR is volatile, this makes everything grey. Let original type stand.
      // if (efficiencyRatio < 0.3) {
      //   type = 'sideways';
      // }
      // Identify anomalies/events within this regime
      const regimeEvents = (anomalies || []).filter((a: any) => {
        return a.date >= regime.startDate && a.date <= regime.endDate;
      });

      // Calculate total change
      const totalChange = (startPrice && endPrice)
        ? ((endPrice - startPrice) / startPrice * 100).toFixed(2) + '%'
        : 'N/A';

      return {
        ...regime,
        displayType: type,
        efficiencyRatio,
        totalChange,
        events: regimeEvents,
        startPrice,
        endPrice
      };
    });
  }, [anomalyZones, chartData, trendAlgo, anomalies, data.datasets, semantic_zones, prediction_semantic_zones, predictionStartDay]);

  // --- End Semantic Regimes ---


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

  // Throttled mouse move safe ref
  const lastUpdateRef = useRef(0);

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

  // 绑定拖拽相关的全局鼠标事件
  useEffect(() => {
    if (isDragging) {
      // 拖拽时绑定到 window，确保鼠标移出容器外也能继续拖拽
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)

      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

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

  // 获取绘图区域边界（排除图例和边距）
  useEffect(() => {
    const container = chartContainerRef.current
    if (!container) return

    const updatePlotAreaBounds = () => {
      // 查找 SVG 元素（Recharts 会在容器内创建 SVG）
      const svg = container.querySelector('svg')
      if (!svg) return

      const containerRect = container.getBoundingClientRect()
      const svgRect = svg.getBoundingClientRect()

      // 查找 X 轴和 Y 轴的实际位置来确定绘图区域
      const xAxis = svg.querySelector('.recharts-cartesian-axis.xAxis')
      const yAxis = svg.querySelector('.recharts-cartesian-axis.yAxis')

      // 如果找不到坐标轴，使用 margin 计算
      if (!xAxis || !yAxis) {
        const marginTop = 5
        const marginBottom = 20
        const legend = svg.querySelector('.recharts-legend-wrapper')
        const legendHeight = legend ? legend.getBoundingClientRect().height : 0

        const plotTop = marginTop
        const plotHeight = containerRect.height - marginTop - marginBottom - legendHeight
        setPlotAreaBounds({ top: plotTop, height: plotHeight, left: 60, width: containerRect.width - 60 })
        return
      }

      // 获取坐标轴的实际位置
      const xAxisRect = xAxis.getBoundingClientRect()
      const yAxisRect = yAxis.getBoundingClientRect()

      // 绘图区域从 Y 轴顶部开始，到 X 轴顶部结束
      // 计算相对于容器顶部的偏移
      const plotTop = yAxisRect.top - containerRect.top
      const plotBottom = xAxisRect.top - containerRect.top
      const plotHeight = plotBottom - plotTop
      const plotLeft = yAxisRect.width  // Approximate, or use yAxisRect.right - containerRect.left
      const plotWidth = xAxisRect.width

      if (plotHeight > 0) {
        setPlotAreaBounds({ top: plotTop, height: plotHeight, left: plotLeft, width: plotWidth })
      }
    }

    // 初始化时获取边界
    const timer = setTimeout(updatePlotAreaBounds, 100)

    // 监听窗口大小变化
    window.addEventListener('resize', updatePlotAreaBounds)

    // 使用 MutationObserver 监听 DOM 变化（图表渲染完成）
    const observer = new MutationObserver(updatePlotAreaBounds)
    observer.observe(container, { childList: true, subtree: true })

    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', updatePlotAreaBounds)
      observer.disconnect()
    }
  }, [chartData, viewStartIndex, viewEndIndex, isZoomed])

  // 原生鼠标跟踪获取真实Y坐标（仅在绘图区域内）
  useEffect(() => {
    const container = chartContainerRef.current
    if (!container || !plotAreaBounds) return

    const handleMouseMove = (e: MouseEvent) => {
      // Throttle: 60ms (~16fps) to prevent chart lag during drag
      const now = Date.now();
      if (now - lastUpdateRef.current < 60) return;
      lastUpdateRef.current = now;

      const containerRect = container.getBoundingClientRect()
      const mouseYRelativeToContainer = e.clientY - containerRect.top

      // 检查鼠标是否在绘图区域内
      const plotAreaTop = plotAreaBounds.top
      const plotAreaBottom = plotAreaTop + plotAreaBounds.height

      // Slider Dragging Logic
      if (isDraggingSlider && displayData && displayData.length > 0) {
        const xInPlot = (e.clientX - containerRect.left) - plotAreaBounds.left;
        const ratio = Math.max(0, Math.min(1, xInPlot / plotAreaBounds.width));
        const index = Math.round(ratio * (displayData.length - 1));
        const item = displayData[index];
        if (item) {
          setTempSplitDate(item.name);
        }
      } else if (mouseYRelativeToContainer >= plotAreaTop && mouseYRelativeToContainer <= plotAreaBottom) {
        // 计算相对于绘图区域顶部的坐标
        const yInPlotArea = mouseYRelativeToContainer - plotAreaTop
        setMouseY(yInPlotArea)
        setMouseX(e.clientX - containerRect.left) // Store X for tooltip positioning
      } else {
        // 鼠标不在绘图区域内，不显示虚线
        setMouseY(null)
      }
    }

    const handleMouseLeave = () => {
      setMouseY(null);
      setMouseX(null);
      setActiveZone(null);
      if (isDraggingSlider) {
        setIsDraggingSlider(false); // Auto-drop slider if leaving container
        setTempSplitDate(null);
      }
    }

    // MouseUp to commit slider change
    const handleMouseUpContainer = () => {
      if (isDraggingSlider) {
        setIsDraggingSlider(false);
        if (tempSplitDate) {
          backtest.triggerBacktest(tempSplitDate);
        }
        setTempSplitDate(null);
      }
    }

    container.addEventListener('mousemove', handleMouseMove)
    container.addEventListener('mouseleave', handleMouseLeave)
    container.addEventListener('mouseup', handleMouseUpContainer)

    return () => {
      container.removeEventListener('mousemove', handleMouseMove)
      container.removeEventListener('mouseleave', handleMouseLeave)
      container.removeEventListener('mouseup', handleMouseUpContainer)
    }
  }, [plotAreaBounds, lastUpdateRef, isDraggingSlider, displayData, tempSplitDate, backtest])

  // 重置视图
  const handleReset = useCallback(() => {
    setViewStartIndex(0)
    setViewEndIndex(chartData.length - 1)
  }, [chartData.length])

  // Filter Logic
  // @ts-ignore
  const visibleZones = (anomalyZones || []).filter((z: any) => {
    if (trendAlgo === 'all') return true;
    return (z.method || 'plr') === trendAlgo;
  });

  // Filter Anomalies
  // @ts-ignore
  // Filter Anomalies - Memoized to prevent re-renders
  // @ts-ignore
  const visibleAnomalies = useMemo(() => {
    return (anomalies || []).filter((a: any) => {
      if (anomalyAlgo === 'all') return true;
      return (a.method || 'bcpd') === anomalyAlgo;
    });
  }, [anomalies, anomalyAlgo]);

  // 如果标题包含"预测"，则不显示（因为外层已有"价格走势分析"标题）
  const shouldShowTitle = title && !title.includes('预测')

  // Memoize Ticks to prevent re-calculation on every render/drag
  const memoizedTicks = useMemo(() => {
    if (isZoomed) return undefined;
    // ALWAYS use visibleZones (Raw Intervals) as requested by user, even in Semantic Mode
    const sourceZones = visibleZones || [];
    if (!sourceZones) return undefined;

    // Extract dates from zones (start/end)
    const dates = sourceZones.flatMap((z: any) => [z.startDate, z.endDate]);

    return Array.from(new Set(dates)).filter(d => displayData.some((p: any) => p.name === d)).sort();
  }, [isZoomed, visibleZones, displayData]);

  // ------------------------------------------------------------------
  // Memoized Chart Elements to prevent Jitter
  // ------------------------------------------------------------------

  // 1. Semantic Zones (Areas)
  const semanticZoneElements = useMemo(() => {
    if (!useSemanticRegimes || !displayData || displayData.length === 0) return null;

    // Helper to clamp dates to visible range to ensure rendering
    const visibleStartName = displayData[0].name as string;
    const visibleEndName = displayData[displayData.length - 1].name as string;

    // We need indices to compare order because dates are strings
    // chartData contains all data in order
    const getIndex = (name: string) => chartData.findIndex((d: any) => d.name === name);

    const visibleStartIndex = viewStartIndex; // optimization: use existing state
    const visibleEndIndex = viewEndIndex;

    return semanticRegimes.map((regime: any, idx: number) => {
      const sentiment = regime.sentiment || regime.displayType;
      const isPositive = sentiment === 'positive' || sentiment === 'up';
      const isNegative = sentiment === 'negative' || sentiment === 'down';
      const isSideways = sentiment === 'sideways' || sentiment === 'neutral';
      const fill = isPositive ? '#ef4444' : (isNegative ? '#10b981' : '#6b7280');
      const isPrediction = regime.isPrediction;
      const baseOpacity = isPrediction ? 0.15 : (isSideways ? 0.2 : 0.3);
      const uniqueKey = `regime-area-${regime.startDate}-${idx}`;

      // Clamp logic
      const rStartIdx = getIndex(regime.startDate);
      const rEndIdx = getIndex(regime.endDate);

      // If completely out of view, skip
      if (rEndIdx < visibleStartIndex || rStartIdx > visibleEndIndex) return null;

      // Clamp start/end to visible view
      const clampStartIdx = Math.max(rStartIdx, visibleStartIndex);
      const clampEndIdx = Math.min(rEndIdx, visibleEndIndex);

      const x1 = chartData[clampStartIdx]?.name;
      const x2 = chartData[clampEndIdx]?.name;

      if (!x1 || !x2) return null;

      // Re-calculate return rate based on visible chart data for accuracy
      const startPoint = chartData[clampStartIdx];
      const endPoint = chartData[clampEndIdx];
      let displayRate = regime.totalChange;

      // Try to calculate dynamic return
      if (startPoint && endPoint) {
        // Use the first available price key (History or Prediction)
        const getVal = (p: any) => p['历史价格'] ?? p['实际值'] ?? p['预测价格'] ?? p['close'];
        const sv = getVal(startPoint);
        const ev = getVal(endPoint);
        if (typeof sv === 'number' && typeof ev === 'number' && sv !== 0) {
          const rate = (ev - sv) / sv;
          displayRate = (rate >= 0 ? '+' : '') + (rate * 100).toFixed(2) + '%';
        }
      }

      return (
        <ReferenceArea
          key={uniqueKey}
          x1={x1}
          x2={x2}
          fill={fill}
          fillOpacity={baseOpacity}
          stroke={isPrediction ? fill : "none"}
          strokeDasharray={isPrediction ? "5 5" : undefined}
          className="cursor-pointer hover:opacity-80 transition-opacity"
          onMouseEnter={() => {
            if (!isDraggingSlider && activeZone !== regime) setActiveZone(regime);
          }}
          onMouseLeave={() => {
            if (!isDraggingSlider && activeZone === regime) setActiveZone(null);
          }}
        >
          <Label
            value={displayRate} // Use re-calculated rate
            position="insideTop"
            fill={fill}
            fontSize={10}
            className="font-mono font-bold opacity-70"
          />
        </ReferenceArea>
      );
    });
  }, [useSemanticRegimes, semanticRegimes, displayData, viewStartIndex, viewEndIndex, chartData]);

  // 2. Anomaly Lookup Map (Faster Access)
  const anomalyMap = useMemo(() => {
    const map = new Map();
    visibleAnomalies.forEach((anom: any) => {
      map.set(anom.date, anom);
    });
    return map;
  }, [visibleAnomalies]);

  // 3. Flag Icon Component
  const FlagIcon = (props: any) => {
    const { cx, cy, fill, className, onMouseEnter, onMouseLeave, onClick } = props;
    return (
      <g transform={`translate(${cx}, ${cy})`} className={className}
        onMouseEnter={onMouseLeave} onMouseLeave={onMouseLeave} onClick={onClick}
        style={{ pointerEvents: 'all', cursor: 'pointer' }}
      >
        <line x1="0" y1="0" x2="0" y2="-12" stroke="#9ca3af" strokeWidth="1.5" />
        <path d="M0,-12 L8,-8 L0,-4 Z" fill={fill} stroke="none" />
        <circle cx="0" cy="-12" r="1.5" fill="#9ca3af" />
        {/* Hit area for easier clicking */}
        <rect x="-4" y="-14" width="14" height="16" fill="transparent" />
      </g>
    )
  }

  // 4. Anomaly Flags Elements (Placed near data points, non-interactive)
  const anomalyFlagElements = useMemo(() => {
    if (!yAxisDomain || !displayData) return null;
    if (!visibleAnomalies || visibleAnomalies.length === 0) return null;

    // Create a quick lookup for data values by date
    // We prioritize '历史价格'
    const priceMap = new Map();
    displayData.forEach((d: any) => {
      if (d['历史价格'] !== undefined && d['历史价格'] !== null) {
        priceMap.set(d.name, d['历史价格']);
      }
    });

    return visibleAnomalies.map((anom: any, idx: number) => {
      const uniqueKey = `anomaly-flag-${anom.date}-${idx}`;
      const price = priceMap.get(anom.date);

      // If no price found for this date (e.g. range mismatch), skip or fallback
      // Fallback to top edge if really needed, but user said "plug back onto line"
      // If price is missing, we might not render it or render at 0.
      if (price === undefined) return null;

      const colorMap: Record<string, string> = {
        'signal_service': '#FBBF24',
        'bcpd': '#F59E0B',
        'stl_cusum': '#EF4444',
        'matrix_profile': '#8B5CF6'
      };
      const fill = colorMap[anom.method] || '#FBBF24';

      return (
        <ReferenceDot
          key={uniqueKey}
          x={anom.date}
          y={price}
          r={0}
          shape={(props: any) => (
            <FlagIcon
              {...props}
              fill={fill}
              className="z-0 opacity-80"
              // Purely visual, no interaction
              style={{ pointerEvents: 'none' }}
            />
          )}
          isFront={true}
        />
      );
    });
  }, [visibleAnomalies, yAxisDomain, displayData]);



  // 3. Raw Zones (Areas)
  const rawZoneElements = useMemo(() => {
    if (useSemanticRegimes) return null;
    return visibleZones.map((zone: any, idx: number) => {
      // A股配色：红涨绿跌
      const isPositive = (zone.avg_return || 0) >= 0;
      const zoneColor = isPositive
        ? { fill: 'rgba(239, 68, 68, 0.04)', stroke: '#ef4444' }
        : { fill: 'rgba(34, 197, 94, 0.04)', stroke: '#22c55e' };

      const impact = zone.impact || 0.5;
      const isCalm = zone.zone_type === 'calm';
      const uniqueKey = `zone-${zone.startDate}-${zone.endDate}-${idx}`;

      // FIX: 单日zones需要扩展宽度，否则ReferenceArea不显示
      let displayStartDate = zone.startDate;
      if (zone.startDate === zone.endDate) {
        const startIdx = chartData.findIndex((d: any) => d.name === zone.startDate);
        if (startIdx > 0) {
          displayStartDate = chartData[startIdx - 1].name;
        }
      }

      // Clamp to current view if needed (for Zooming)
      // If the zone is partially visible, we must ensure start/end are within displayData for rendering?
      // Actually Recharts XAxis scale="point" might require points to exist in the current dataKey list.
      // If zoomed, displayData is subset.
      // Check if start/end are in displayData.
      if (displayData.length > 0) {
        const firstVisible = displayData[0].name;
        const lastVisible = displayData[displayData.length - 1].name;

        // Simple string comparison for dates works YYYY-MM-DD
        if (zone.endDate < firstVisible) return null;
        if (displayStartDate > lastVisible) return null;

        // Clamp
        if (displayStartDate < firstVisible) displayStartDate = firstVisible;
        // We don't change zone.endDate if it exceeds lastVisible usually, ReferenceArea handles one side?
        // But for "point" scale, value MUST be in domain.
        if (zone.endDate > lastVisible) {
          // We can't assign to zone.endDate directly (prop).
          // But we can use clamped value for ReferenceArea x2
        }
      }

      return (
        <ReferenceArea
          key={uniqueKey}
          x1={displayStartDate}
          x2={zone.endDate > displayData[displayData.length - 1]?.name ? displayData[displayData.length - 1]?.name : zone.endDate}
          fill={zoneColor.fill}
          fillOpacity={impact * 0.8}
          stroke={zoneColor.stroke}
          strokeOpacity={impact}
          strokeDasharray={isCalm ? '5 5' : undefined}
          onMouseEnter={() => {
            // Optimization: Only update if changed and not dragging
            if (!isDraggingSlider && activeZone !== zone) setActiveZone(zone);
          }}
          onMouseLeave={() => {
            if (!isDraggingSlider && activeZone === zone) setActiveZone(null);
          }}
          className="cursor-pointer transition-all duration-300"
        />
      );
    });
  }, [useSemanticRegimes, visibleZones, chartData]);

  // 4. Semantic Events (Dots)
  const semanticEventElements = useMemo(() => {
    if (!useSemanticRegimes) return null;
    if (!yAxisDomain) return null;

    return semanticRegimes.flatMap((regime: any, idx: any) =>
      regime.events.map((ev: any, evIdx: any) => {
        const dotColor = ev.method === 'bcpd' ? '#fbbf24' : (ev.method === 'matrix_profile' ? '#c084fc' : '#f87171');
        const yPos = yAxisDomain[0] + (yAxisDomain[1] - yAxisDomain[0]) * 0.05;

        return (
          <ReferenceDot
            key={`regime-event-${idx}-${evIdx}`}
            x={ev.date}
            y={yPos}
            r={4}
            fill={dotColor}
            stroke="#fff"
            strokeWidth={1}
            className="cursor-pointer hover:r-6 transition-all"
            isFront={true}
          >
            <Label value="" />
          </ReferenceDot>
        );
      })
    );
  }, [useSemanticRegimes, semanticRegimes, yAxisDomain]);


  return (
    <div className="mt-2">
      {/* 回测控制UI */}
      {hasBacktestSupport && (
        <BacktestControls
          isLoading={backtest.isLoading}
          mae={backtest.metrics?.mae ?? null}
          onReset={backtest.resetBacktest}
        />
      )}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {shouldShowTitle && (
            <h4 className="text-sm font-medium text-gray-300">{title}</h4>
          )}
          {/* Toggle Button Removed as requested */}
        </div>

        <div className="flex items-center gap-2">
          {/* Help Text / Controls */}
          {isZoomed ? (
            <>
              <button
                onClick={handleReset}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-gray-400 hover:text-gray-200 bg-dark-600/50 hover:bg-dark-600 rounded-lg transition-colors"
                title="重置视图"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>重置</span>
              </button>
              <div className="flex items-center gap-1 text-xs text-gray-500 ml-2">
                <Move className="w-3.5 h-3.5" />
                <span>拖拽平移 | 滚轮缩放</span>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Move className="w-3.5 h-3.5" />
              <span>点击图表后：拖拽平移 | 滚轮缩放</span>
            </div>
          )}
        </div>
      </div>
      {visibleZones && visibleZones.length > 0 && (
        <div className="absolute top-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white/70 z-10">
          {visibleZones.length} 个重点区域
        </div>
      )}
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
            onClick={handleChartClick}
            onMouseMove={(state: any) => {
              if (state && state.activeCoordinate) {
                // Recharts provides x relative to the plot area
                setActiveCoordinateX(state.activeCoordinate.x);
              }
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#3a3a4a" />
            <XAxis
              dataKey="name"
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
              angle={isZoomed ? -45 : 0}
              textAnchor={isZoomed ? "end" : "middle"}
              height={isZoomed ? 60 : 30}
              padding={{ left: 0, right: 0 }}
              scale="point" // CRITICAL: Ensures points are on ticks, matching slider math
              // Use explicit ticks from visible zones start/end for major ticks
              ticks={memoizedTicks as (string | number)[] | undefined}
              minTickGap={30}
              interval="preserveStartEnd"
              tick={({ x, y, payload }) => (
                <g transform={`translate(${x},${y})`}>
                  {/* Short vertical line above axis (upwards) - Explicitly inside chart, High Contrast */}
                  <line x1={0} y1={0} x2={0} y2={-10} stroke="#ffffff" strokeWidth={2} strokeOpacity={0.6} />
                  {/* Rotated text to prevent overlap */}
                  <text x={0} y={20} dy={0} textAnchor="end" transform={`rotate(-45, 0, 20)`} fill="#9ca3af" fontSize={10} fontFamily="monospace">
                    {payload.value}
                  </text>
                </g>
              )}
              tickLine={false} // Hide default tick line
            />

            <YAxis
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
              domain={yAxisDomain}
              allowDataOverflow={false}
              padding={{ top: 10, bottom: 10 }} // Add separate padding here if needed instead of domain math
              tickFormatter={(value) => {
                // 格式化 Y 轴刻度标签，处理大数值
                if (isNaN(value) || !isFinite(value)) {
                  return ''
                }

                // 如果数值很大，使用科学计数法或简化显示
                if (Math.abs(value) >= 100000000) {
                  return (value / 100000000).toFixed(1) + '亿'
                } else if (Math.abs(value) >= 10000) {
                  return (value / 10000).toFixed(1) + '万'
                } else if (Math.abs(value) >= 1000) {
                  return (value / 1000).toFixed(1) + 'k'
                } else if (Math.abs(value) >= 1) {
                  return value.toFixed(0)
                } else {
                  return value.toFixed(2)
                }
              }}
              width={60}
            />
            <Tooltip
              content={() => null}
              cursor={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1, strokeDasharray: '3 3' }}
              isAnimationActive={false}
            />
            <Legend
              wrapperStyle={{ fontSize: '12px' }}
            />
            {/* 1. Semantic Regimes (Memoized) */}
            {semanticZoneElements}

            {/* 2. Anomalies (Memoized) - REMOVED for Intrinsic Dots */}


            {/* 3. Raw Zones (Memoized) */}
            {rawZoneElements}

            {/* 4. Mouse Follow Line */}
            {mouseY !== null && plotAreaBounds && (() => {
              // mouseY 已经是相对于绘图区域顶部的坐标
              const effectiveHeight = plotAreaBounds.height
              const dataValue = yAxisDomain[1] - (mouseY / effectiveHeight) * (yAxisDomain[1] - yAxisDomain[0])
              return (
                <ReferenceLine
                  y={dataValue}
                  stroke="#60a5fa"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  label={{
                    value: dataValue.toFixed(2),
                    position: 'right',
                    fill: '#60a5fa',
                    fontSize: 10
                  }}
                />
              )
            })()}

            {/* 5. Backtest Split Line */}
            {/* 5. Backtest Split Line & Slider Handle (Unified) */}
            {(() => {
              // 1. Determine the Split Date
              let targetDate = isDraggingSlider && tempSplitDate ? tempSplitDate : backtest.splitDate;

              // 2. Auto-detect logic if no explicit date (e.g. Prediction Mode default)
              if (!targetDate && chartData && chartData.length > 1) {
                // Try to find the transition point from '历史价格' to '预测价格'
                // We assume sorted data. We look for the first point that has Prediction but previous had History (or just first prediction).
                for (let i = 0; i < chartData.length - 1; i++) {
                  const current = chartData[i];
                  const next = chartData[i + 1];
                  const currHist = (current as any)['历史价格'];
                  const nextPred = (next as any)['预测价格'];

                  // If current is end of history, and next starts prediction
                  if (currHist !== null && currHist !== undefined && nextPred !== null && nextPred !== undefined) {
                    targetDate = next.name as string;
                    break;
                  }
                }

                // Fallback: If no clean crossover, just take first point with prediction?
                if (!targetDate) {
                  const firstPred = chartData.find((d: any) => (d as any)['预测价格'] !== null);
                  if (firstPred) targetDate = firstPred.name as string;
                }
              }

              if (!targetDate) return null;

              // 3. Visibility Check (Must be in current displayData to render)
              const isVisible = displayData.some((d: any) => d.name === targetDate);
              if (!isVisible) return null;

              return (
                <>
                  <ReferenceLine
                    x={targetDate}
                    stroke="#f97316"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                  />
                  <ReferenceDot
                    x={targetDate}
                    y={yAxisDomain[0]}
                    r={8}
                    isFront={true}
                    shape={(props: any) => {
                      const { cx } = props;
                      // Calculate bottom of chart area
                      const chartBottom = plotAreaBounds
                        ? plotAreaBounds.top + plotAreaBounds.height
                        : (props.viewBox ? props.viewBox.y + props.viewBox.height : 300);

                      return (
                        <g
                          style={{ cursor: 'ew-resize' }}
                          onMouseDown={(e: any) => {
                            e.stopPropagation();
                            e.preventDefault();
                            setIsDraggingSlider(true);
                          }}
                        >
                          {/* Touch Target */}
                          <circle cx={cx} cy={chartBottom} r={15} fill="transparent" />
                          {/* Handle visual */}
                          <circle cx={cx} cy={chartBottom} r={8} fill="#f97316" stroke="white" strokeWidth={2} />
                          <circle cx={cx} cy={chartBottom} r={3} fill="white" />
                        </g>
                      );
                    }}
                  />
                </>
              );
            })()}

            {/* 6. Chart Lines */}
            {backtest.chartData ? (
              <>
                <Line
                  type="monotone"
                  dataKey="历史价格"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6, fill: '#0c0c0c', stroke: '#a855f7', strokeWidth: 2 }}
                  isAnimationActive={false}
                  name="历史价格"
                />
                <Line
                  type="monotone"
                  dataKey="实际值"
                  stroke="#6b7280"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={{ r: 6, fill: '#0c0c0c', stroke: '#6b7280', strokeWidth: 2 }}
                  connectNulls={false}
                  isAnimationActive={false} // Performance critical for drag
                  name="实际值 (Ground Truth)"
                />
                <Line
                  type="monotone"
                  dataKey="回测预测"
                  stroke="#06b6d4"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 6, fill: '#0c0c0c', stroke: '#06b6d4', strokeWidth: 2 }}
                  isAnimationActive={false} // Prevents "growing" effect on re-render
                  name="回测预测"
                />
              </>
            ) : (
              data.datasets.map((dataset: any, index: any) => {
                const isPrediction = dataset.label === '预测价格';
                return (
                  <Line
                    key={dataset.label}
                    type="monotone"
                    dataKey={dataset.label}
                    stroke={dataset.color}
                    strokeWidth={2}
                    dot={false}
                    activeDot={isPrediction ? false : { r: 6, strokeWidth: 2 }} // Disable dots for prediction
                    isAnimationActive={false}
                    connectNulls={false}
                  />
                )
              })
            )}

            {/* 7. Semantic Event Dots (Removed legacy yellow dots) */}
            {/* {semanticEventElements} */}

            {/* 8. Anomaly Flags (Top Row) */}
            {anomalyFlagElements}
            {(() => {
              // console.log("[MessageContent] Anomalies Prop:", anomalies?.length || 0);
              // console.log("[MessageContent] Visible Anomalies:", visibleAnomalies.length);
              // console.log("[MessageContent] Prediction Zones:", prediction_semantic_zones?.length || 0);
              if (anomalies && anomalies.length > 0 && visibleAnomalies.length === 0) {
                console.warn("[MessageContent] WARNING: Anomalies exist but none are visible! Check date format match.",
                  "Anomaly Sample:", anomalies[0],
                  "ChartData Sample:", chartData[0]
                );
              }
              return null;
            })()}

          </LineChart>
        </ResponsiveContainer>

        {/* Slider Logic Moved Here (Outside SVG/ResponsiveContainer) */}



      </div>


      {
        isZoomed && (
          <div className="mt-2 text-xs text-gray-500 text-center">
            当前视图：{chartData[viewStartIndex]?.name} 至 {chartData[viewEndIndex]?.name}
            ({viewEndIndex - viewStartIndex + 1} / {chartData.length} 个数据点)
          </div>
        )
      }

      <AnimatePresence>
        {/* Event Capsule - Bloomberg 风格事件摘要 */}
        {(() => {
          const shouldShow = activeZone && useSemanticRegimes && activeZone.events && activeZone.events.length > 0;
          if (!shouldShow) return null;

          // Calculate Fixed Position
          const container = chartContainerRef.current;
          if (!container) return null;
          const rect = container.getBoundingClientRect();

          // Position: Right of mouse if space allows, otherwise Left.
          const top = rect.top + (mouseY || 20) + 20;
          const left = rect.left + (mouseX || 60) + 20;

          return (
            <PortalTooltip style={{ top, left, pointerEvents: 'none' }}>
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="bg-black/90 border border-white/10 backdrop-blur-md
                        px-4 py-3 rounded-lg shadow-2xl min-w-[320px] max-w-lg"
              >

                {/* Header: Total Change & Effect */}
                <div className="flex flex-col gap-1 w-full mb-3 border-b border-white/5 pb-2 sticky top-0 bg-[#020203]/95 z-10">
                  {/* Row 1: Zone Info */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {(activeZone.impact || 0) > 0.7 && (
                        <span className="text-lg animate-pulse" title="High Impact">✨</span>
                      )}
                      <span className={`text-xs px-2 py-0.5 rounded font-mono font-bold border ${(activeZone.avg_return || 0) >= 0
                        ? 'bg-red-500/10 text-red-400 border-red-500/20'
                        : 'bg-green-500/10 text-green-400 border-green-500/20'
                        }`}>
                        {((activeZone.avg_return || 0) >= 0 ? '+' : '')}
                        {((activeZone.avg_return || 0) * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-white/40 font-mono">
                        {activeZone.startDate} ~ {activeZone.endDate}
                      </span>
                    </div>
                  </div>

                  {/* Row 2: Hovered Price Info (Separate Row) */}
                  <div className="w-full mt-2 pt-2 border-t border-white/10">
                    {(() => {
                      // Calculate current price based on mouseX
                      if (mouseX !== null && plotAreaBounds) {
                        const ratio = (mouseX - plotAreaBounds.left) / plotAreaBounds.width;
                        const idx = Math.round(ratio * (displayData.length - 1));
                        const safeIdx = Math.max(0, Math.min(idx, displayData.length - 1));
                        const item = displayData[safeIdx];
                        if (item) {
                          const price = item['历史价格'] ?? item['回测预测'] ?? item['实际值'];
                          const date = item.name;
                          return (
                            <div className="flex justify-between items-center text-xs w-full">
                              <span className="text-gray-400 font-mono">{date}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-gray-500">当前价格:</span>
                                <span className="text-violet-400 font-bold font-mono text-sm"> {/* Increased font size */}
                                  {typeof price === 'number' ? price.toFixed(2) : '-'}
                                </span>
                              </div>
                            </div>
                          )
                        }
                      }
                      return null;
                    })()}
                  </div>
                </div>

                <div className="space-y-4 pt-2">
                  <div className="text-[10px] text-white/40 uppercase tracking-widest font-bold flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse"></span>
                    Event Flow
                  </div>
                  <div className="relative pl-1">
                    {/* Timeline Line */}
                    <div className="absolute left-[3px] top-1 bottom-1 w-px bg-gradient-to-b from-white/20 via-white/10 to-transparent"></div>

                    {activeZone.events.map((ev: any, idx: number) => (
                      <div key={idx} className="relative pl-5 py-1 mb-2 group">
                        {/* Timeline Dot */}
                        <div className={`absolute left-0 top-2.5 w-[7px] h-[7px] rounded-full border border-black/50 transition-colors duration-300 ${(ev.avg_return || ((ev.endPrice - ev.startPrice) / ev.startPrice)) >= 0
                          ? 'bg-red-400 group-hover:bg-red-300'
                          : 'bg-green-400 group-hover:bg-green-300'
                          }`}></div>

                        {/* Content Card */}
                        <div className="flex flex-col">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[10px] text-gray-500 font-mono">{ev.startDate}</span>
                            <span className={`text-[10px] font-bold font-mono px-1 rounded ${(ev.avg_return !== undefined ? ev.avg_return : ((ev.endPrice - ev.startPrice) / ev.startPrice)) >= 0
                              ? 'text-red-400 bg-red-400/10'
                              : 'text-green-400 bg-green-400/10'
                              }`}>
                              {((ev.avg_return !== undefined ? ev.avg_return : ((ev.endPrice - ev.startPrice) / ev.startPrice)) * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="text-xs text-gray-200 leading-snug font-medium group-hover:text-white transition-colors">
                            {ev.summary || ev.event_summary || ev.type?.toUpperCase() || 'Event'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            </PortalTooltip>
          );
        })()}
      </AnimatePresence>

      {/* 新闻侧边栏 */}
      {
        ticker && (
          <ChartNewsSidebar
            isOpen={newsSidebarOpen}
            onClose={handleCloseSidebar}
            news={newsData}
            loading={newsLoading}
            selectedDate={selectedDate}
            ticker={ticker}
          />
        )
      }
    </div >
  )
}

