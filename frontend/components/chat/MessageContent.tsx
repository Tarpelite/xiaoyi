'use client'

import { useState, useMemo, useRef, useCallback, useEffect, Fragment } from 'react'
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
  const { title, data, chartType = 'line', sessionId, messageId, originalData, anomalyZones = [], semantic_zones = [], ticker, anomalies = [] } = content as any

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
      console.log('[MessageContent] Restored from URL - date:', savedDate, 'sidebar:', savedSidebarOpen);
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
        setNewsData(data.news || []);
      } catch (error) {
        console.error('Failed to load news:', error);
        setNewsData([]);
      } finally {
        setNewsLoading(false);
      }
    };
    fetchNews();
  }, [selectedDate, ticker]);  // 移除newsSidebarOpen依赖，确保刷新后自动加载

  // 图表点击处理
  const handleChartClick = useCallback((e: any) => {
    if (e && e.activeLabel && ticker) {
      const date = e.activeLabel as string;
      setSelectedDate(date);
      setNewsSidebarOpen(true);

      // 持久化到URL
      const params = new URLSearchParams(window.location.search);
      params.set('selectedDate', date);
      params.set('sidebarOpen', 'true');
      window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
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
  const [plotAreaBounds, setPlotAreaBounds] = useState<{ top: number; height: number } | null>(null) // 绘图区域边界

  // 滑块拖拽状态
  const [isDraggingSlider, setIsDraggingSlider] = useState(false)
  const [tempSplitDate, setTempSplitDate] = useState<string | null>(null) // 拖拽时的临时分割日期

  // 计算当前显示的数据
  const displayData = useMemo(() => {
    return chartData.slice(viewStartIndex, viewEndIndex + 1)
  }, [chartData, viewStartIndex, viewEndIndex])

  // DIAGNOSTIC: Check if zone dates exist in chartData AND their positions
  useEffect(() => {
    if (anomalyZones && anomalyZones.length > 0 && chartData.length > 0) {
      const chartDates = new Set(chartData.map((d: any) => d.name))
      console.log('[DIAGNOSTIC] chartData range:', chartData[0]?.name, 'to', chartData[chartData.length - 1]?.name, `(${chartData.length} points)`)
      console.log('[DIAGNOSTIC] viewStartIndex:', viewStartIndex, 'viewEndIndex:', viewEndIndex, 'visible:', viewEndIndex - viewStartIndex + 1, 'points')

      anomalyZones.forEach((zone: any, idx: any) => {
        const startIndex = chartData.findIndex((d: any) => d.name === zone.startDate)
        const endIndex = chartData.findIndex((d: any) => d.name === zone.endDate)
        const isInViewport = startIndex >= viewStartIndex && endIndex <= viewEndIndex
        const hasStart = chartDates.has(zone.startDate)
        const hasEnd = chartDates.has(zone.endDate)

        console.log(`[DIAGNOSTIC] Zone ${idx} (${zone.startDate}-${zone.endDate}): start=${hasStart}(idx=${startIndex}), end=${hasEnd}(idx=${endIndex}), inViewport=${isInViewport}`)
      })
    }
  }, [anomalyZones, chartData, viewStartIndex, viewEndIndex])

  // Debug: Log anomaly data when received
  useEffect(() => {
    if (anomalies && anomalies.length > 0) {
      console.log(`[Anomaly Rendering] Received ${anomalies.length} anomalies:`, anomalies);
      console.log('[Anomaly Rendering] Chart Y-axis domain:', yAxisDomain);
      console.log('[Anomaly Rendering] Chart date range:', chartData[0]?.name, 'to', chartData[chartData.length - 1]?.name);

      // Check which anomalies are in valid date range
      const chartDates = new Set(chartData.map((d: any) => d.name));
      anomalies.forEach((anom: any, idx: number) => {
        const inDateRange = chartDates.has(anom.date);
        const inYRange = anom.price >= yAxisDomain[0] && anom.price <= yAxisDomain[1];
        console.log(`[Anomaly ${idx}] ${anom.method} at ${anom.date}: price=${anom.price}, inDateRange=${inDateRange}, inYRange=${inYRange}`);
      });
    }
  }, [anomalies, chartData, yAxisDomain]);

  // --- Semantic Regimes Logic ---
  const semanticRegimes = useMemo(() => {
    // 1. If Backend already provided Semantic Zones, use them directly!
    // This supports "Event Flow" feature and robust backend merging
    if (semantic_zones.length > 0) {
      // Ensure we enrich them with frontend interactions (like active state) although rendering loop handles that
      // Just return them, they are already formatted
      return semantic_zones;
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
  }, [anomalyZones, chartData, trendAlgo, anomalies, data.datasets]);

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
        setPlotAreaBounds({ top: plotTop, height: plotHeight })
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

      if (plotHeight > 0) {
        setPlotAreaBounds({ top: plotTop, height: plotHeight })
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
      const containerRect = container.getBoundingClientRect()
      const mouseYRelativeToContainer = e.clientY - containerRect.top

      // 检查鼠标是否在绘图区域内
      const plotAreaTop = plotAreaBounds.top
      const plotAreaBottom = plotAreaTop + plotAreaBounds.height

      if (mouseYRelativeToContainer >= plotAreaTop && mouseYRelativeToContainer <= plotAreaBottom) {
        // 计算相对于绘图区域顶部的坐标
        const yInPlotArea = mouseYRelativeToContainer - plotAreaTop
        setMouseY(yInPlotArea)
      } else {
        // 鼠标不在绘图区域内，不显示虚线
        setMouseY(null)
      }
    }

    const handleMouseLeave = () => setMouseY(null)

    container.addEventListener('mousemove', handleMouseMove)
    container.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      container.removeEventListener('mousemove', handleMouseMove)
      container.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [plotAreaBounds])

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
  const visibleAnomalies = (anomalies || []).filter((a: any) => {
    if (anomalyAlgo === 'all') return true;
    return (a.method || 'bcpd') === anomalyAlgo;
  });

  // 如果标题包含"预测"，则不显示（因为外层已有"价格走势分析"标题）
  const shouldShowTitle = title && !title.includes('预测')

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
        {shouldShowTitle && (
          <h4 className="text-sm font-medium text-gray-300">{title}</h4>
        )}
        <div className="flex items-center gap-2">
          <AlgoSelect
            label="趋势"
            value={trendAlgo}
            onChange={setTrendAlgo}
            options={[
              { label: '分段线性', value: 'plr' },
              { label: '市场状态', value: 'hmm' },
              { label: '突变点', value: 'pelt' },
              { label: '全部', value: 'all' }
            ]}
          />
          <AlgoSelect
            label="异常"
            value={anomalyAlgo}
            onChange={setAnomalyAlgo}
            options={[
              { label: '全部', value: 'all' },
              { label: 'BCPD', value: 'bcpd' },
              { label: 'STL', value: 'stl_cusum' },
              { label: 'Matrix', value: 'matrix_profile' }
            ]}
          />
          <div className="h-4 w-px bg-white/10 mx-1"></div>
          <button
            onClick={() => setUseSemanticRegimes(!useSemanticRegimes)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg transition-colors border ${useSemanticRegimes
              ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
              : 'text-gray-400 border-white/5 hover:bg-white/5'
              }`}
            title="切换语义化行情视角"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Semantic</span>
          </button>
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
              domain={yAxisDomain}
              allowDataOverflow={false}
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
            {/* 异常区域与悬浮提示 - Bloomberg风格 */}
            {/* 区域渲染逻辑：语义合并 vs 原始分段 */}
            {/* 1. Semantic Regimes: Areas */}
            {useSemanticRegimes && semanticRegimes.map((regime: any, idx: number) => {
              const isSideways = regime.displayType === 'sideways';
              const isUp = regime.displayType === 'up';

              // A-share colors: Red for Up, Green for Down
              const fill = isUp ? '#ef4444' : (isSideways ? '#6b7280' : '#10b981');
              const opacity = isSideways ? 0.2 : 0.3;

              const uniqueKey = `regime-area-${regime.startDate}-${idx}`;

              return (
                <ReferenceArea
                  key={uniqueKey}
                  x1={regime.startDate}
                  x2={regime.endDate}
                  fill={fill}
                  fillOpacity={opacity}
                  stroke="none"
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => console.log('View Regime Summary:', regime)}
                >
                  <Label
                    value={regime.totalChange}
                    position="insideTop"
                    fill={fill}
                    fontSize={10}
                    className="font-mono font-bold opacity-70"
                  />
                </ReferenceArea>
              );
            })}

            {/* 2. Semantic Regimes: Event Dots */}
            {useSemanticRegimes && semanticRegimes.flatMap((regime: any, idx: any) =>
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
            )}

            {/* 3. Legacy Zones (Non-Semantic View) */}
            {!useSemanticRegimes && visibleZones.map((zone: any, idx: number) => {
              // A股配色：红涨绿跌
              const isPositive = (zone.avg_return || 0) >= 0
              const zoneColor = isPositive
                ? { fill: 'rgba(239, 68, 68, 0.04)', stroke: '#ef4444' }  // 红色=上涨
                : { fill: 'rgba(34, 197, 94, 0.04)', stroke: '#22c55e' }   // 绿色=下跌

              const impact = zone.impact || 0.5
              const isCalm = zone.zone_type === 'calm'

              // 使用唯一key：startDate-endDate组合
              const uniqueKey = `zone-${zone.startDate}-${zone.endDate}-${idx}`

              // FIX: 单日zones需要扩展宽度，否则ReferenceArea不显示
              let displayStartDate = zone.startDate
              if (zone.startDate === zone.endDate) {
                const startIdx = chartData.findIndex((d: any) => d.name === zone.startDate)
                if (startIdx > 0) {
                  displayStartDate = chartData[startIdx - 1].name
                }
              }

              return (
                <ReferenceArea
                  key={uniqueKey}
                  x1={displayStartDate}
                  x2={zone.endDate}
                  fill={zoneColor.fill}
                  fillOpacity={activeZone === zone ? impact * 1.5 : impact * 0.8}
                  stroke={zoneColor.stroke}
                  strokeOpacity={impact}
                  strokeDasharray={isCalm ? '5 5' : undefined}
                  onMouseEnter={() => setActiveZone(zone)}
                  // onMouseLeave removed to persist summary for reading
                  onClick={(e) => { e.stopPropagation(); setActiveZone(zone); }}
                  className="cursor-pointer transition-all duration-300"
                />
              )
            })}

            {/* 异常点 - ReferenceDot (仅在非Semantic模式下显示) */}
            {!useSemanticRegimes && visibleAnomalies.map((anomaly: any, idx: number) => {
              // Validate anomaly has required fields
              if (!anomaly.date || anomaly.price === undefined) {
                console.warn(`[Anomaly Rendering] Skipping anomaly ${idx}: missing date or price`, anomaly);
                return null;
              }

              // Check if date exists in FULL chartData (not just displayData which is zoom-filtered)
              const dateExists = chartData.some((d: any) => d.name === anomaly.date);
              if (!dateExists) {
                // Date not in dataset at all (weekends or missing data)
                return null;
              }

              // Determine color based on algorithm type
              const colorMap: Record<string, string> = {
                'bcpd': '#F59E0B',        // Amber for BCPD
                'stl_cusum': '#EF4444',   // Red for STL+CUSUM
                'matrix_profile': '#8B5CF6' // Purple for Matrix Profile
              };
              const dotColor = colorMap[anomaly.method] || '#F59E0B';

              return (
                <ReferenceDot
                  key={`anomaly-${anomaly.method}-${idx}`}
                  x={anomaly.date}
                  y={anomaly.price}
                  r={6}
                  fill={dotColor}
                  stroke="#fff"
                  strokeWidth={2}
                  className="cursor-pointer hover:r-8 transition-all"
                >
                  <Label
                    value="!"
                    position="center"
                    fill="#fff"
                    fontSize={10}
                    fontWeight="bold"
                  />
                </ReferenceDot>
              );
            })}

            {/* 鼠标跟随的水平参考线 */}
            {mouseY !== null && plotAreaBounds && (() => {
              // mouseY 已经是相对于绘图区域顶部的坐标
              const effectiveHeight = plotAreaBounds.height

              // 计算对应的数据值
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
            {/* 回测分割线 - 垂直参考线 */}
            {((hasBacktestSupport && backtest.splitDate) || (isDraggingSlider && tempSplitDate)) && (() => {
              // 拖拽时使用临时日期，否则使用回测分割日期
              const splitDate = (isDraggingSlider && tempSplitDate) ? tempSplitDate : backtest.splitDate
              if (!splitDate) return null

              // 检查分割日期是否在当前显示的数据中
              const splitDataPoint = displayData.find((item: any) => item.name === splitDate)
              if (splitDataPoint) {
                return (
                  <ReferenceLine
                    x={splitDate}
                    stroke="#f97316"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                  />
                )
              }
              return null
            })()}
            {/* 回测模式：3条线 */}
            {backtest.chartData ? (
              <>
                <Line
                  type="monotone"
                  dataKey="历史价格"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  name="历史价格"
                />
                <Line
                  type="monotone"
                  dataKey="实际值"
                  stroke="#6b7280"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={{ r: 2 }}
                  activeDot={{ r: 4 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  name="实际值 (Ground Truth)"
                />
                <Line
                  type="monotone"
                  dataKey="回测预测"
                  stroke="#06b6d4"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  name="回测预测"
                />
              </>
            ) : (
              /* 正常模式：原有数据集 */
              data.datasets.map((dataset: any, index: any) => (
                <Line
                  key={dataset.label}
                  type="monotone"
                  dataKey={dataset.label}
                  stroke={dataset.color || colors[index % colors.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))
            )}
          </LineChart>
        </ResponsiveContainer>

        {/* X 轴滑块 - 明显的滑块圆点 */}
        {((hasBacktestSupport && originalData && originalData.length > 60) || (data.datasets.some((d: any) => d.label === '历史价格') && data.datasets.some((d: any) => d.label === '预测价格'))) && plotAreaBounds && (() => {
          // 计算分割点：拖拽时使用临时日期，否则使用回测分割点或历史价格和预测价格的分界点
          let splitDate = isDraggingSlider && tempSplitDate ? tempSplitDate : backtest.splitDate
          let splitIndexInChart = -1

          if (splitDate) {
            // 回测模式：使用指定的分割点
            splitIndexInChart = chartData.findIndex((item: any) => item.name === splitDate)
          } else {
            // 正常模式：查找历史价格和预测价格的分界点
            // 找到最后一个有历史价格值的点，下一个点就是预测价格的起点
            for (let i = chartData.length - 1; i >= 0; i--) {
              const item = chartData[i]
              const historicalPrice = (item as any)['历史价格']
              if (historicalPrice !== null && historicalPrice !== undefined) {
                // 找到下一个有预测价格的点作为分界点
                if (i + 1 < chartData.length) {
                  const nextItem = chartData[i + 1]
                  const predictedPrice = (nextItem as any)['预测价格']
                  if (predictedPrice !== null && predictedPrice !== undefined) {
                    splitIndexInChart = i + 1
                    splitDate = nextItem.name as string
                    break
                  }
                }
                // 如果没有找到预测价格，使用当前点
                if (splitIndexInChart < 0) {
                  splitIndexInChart = i
                  splitDate = item.name as string
                  break
                }
              }
            }
          }

          if (!splitDate || splitIndexInChart < 0) return null

          // 检查是否在当前显示范围内
          const isInView = splitIndexInChart >= viewStartIndex && splitIndexInChart <= viewEndIndex

          // 计算位置比例（相对于当前显示的 displayData）
          // 需要找到分割日期在 displayData 中的索引，而不是在 chartData 中的索引
          let positionRatio = 0
          const splitIndexInDisplayData = displayData.findIndex((item: any) => item.name === splitDate)

          if (splitIndexInDisplayData >= 0) {
            // 在显示数据中找到，计算位置比例
            const displayDataLength = displayData.length
            // Recharts 的 X 轴是均匀分布的，所以位置比例就是索引比例
            // 但需要考虑第一个和最后一个点的位置（它们不在边缘，而是在中间）
            if (displayDataLength > 1) {
              positionRatio = splitIndexInDisplayData / (displayDataLength - 1)
            } else {
              positionRatio = 0
            }
          } else if (isDraggingSlider) {
            // 拖拽时，即使不在显示数据中，也根据位置计算显示
            if (splitIndexInChart < viewStartIndex) {
              positionRatio = 0 // 在视图左侧
            } else {
              positionRatio = 1 // 在视图右侧
            }
          } else {
            // 不在显示数据中且不在拖拽，不显示
            return null
          }

          // X 轴位置
          // plotAreaBounds.top + plotAreaBounds.height 是绘图区域的底部，也就是 X 轴线的位置
          // 滑块圆点应该直接显示在 X 轴线上
          const xAxisLineTop = plotAreaBounds.top + plotAreaBounds.height
          // 滑块圆点在 X 轴线上，所以顶部位置是 X 轴线位置减去圆点半径（8px）以居中
          const sliderTop = xAxisLineTop - 8

          return (
            <>
              {/* 滑块圆点容器 - 覆盖绘图区域 */}
              <div
                className="absolute pointer-events-none z-30"
                style={{
                  left: '60px', // Y 轴宽度
                  right: '10px', // 右侧边距
                  top: `${sliderTop}px`, // X 轴线位置（减去圆点半径以居中）
                  height: '16px'
                }}
              >
                {/* 滑块圆点 - 在 X 轴上明显显示，支持拖拽 */}
                <div
                  className="absolute pointer-events-auto group"
                  style={{
                    left: `${positionRatio * 100}%`, // 在绘图区域内的位置比例
                    transform: 'translateX(-50%)', // 居中对齐
                    width: '16px',
                    height: '16px'
                  }}
                  onMouseDown={(e) => {
                    e.stopPropagation() // 阻止触发图表拖拽
                    e.preventDefault()
                    const container = chartContainerRef.current
                    if (!container) return

                    // 开始拖拽
                    setIsDraggingSlider(true)

                    const updateSplitPoint = (clientX: number, isFinal: boolean = false) => {
                      const svg = container.querySelector('svg')
                      if (!svg) return

                      const svgRect = svg.getBoundingClientRect()
                      const plotLeft = svgRect.left
                      const plotWidth = svgRect.width

                      // 计算鼠标在绘图区域内的位置比例
                      const mouseX = clientX - plotLeft
                      const positionRatio = Math.max(0, Math.min(1, mouseX / plotWidth))

                      // 计算对应的数据点索引
                      const viewRange = viewEndIndex - viewStartIndex + 1
                      const relativeIndex = Math.round(positionRatio * viewRange)
                      const targetIndex = viewStartIndex + relativeIndex

                      // 找到对应的日期
                      if (targetIndex >= 0 && targetIndex < chartData.length && originalData) {
                        const targetDate = chartData[targetIndex].name
                        if (typeof targetDate === 'string') {
                          const originalIndex = originalData.findIndex((p: any) => p.date === targetDate)
                          if (originalIndex >= 60 && originalIndex < originalData.length) {
                            if (isFinal) {
                              // 释放鼠标时才触发回测更新
                              backtest.triggerBacktest(targetDate)
                              setIsDraggingSlider(false)
                              setTempSplitDate(null)
                            } else {
                              // 拖拽过程中只更新临时日期，用于显示滑块位置
                              setTempSplitDate(targetDate)
                            }
                          }
                        }
                      }
                    }

                    const handleMouseMove = (e: MouseEvent) => {
                      updateSplitPoint(e.clientX, false) // 拖拽中，不触发回测
                    }

                    const handleMouseUp = (e: MouseEvent) => {
                      updateSplitPoint(e.clientX, true) // 释放时，触发回测
                      window.removeEventListener('mousemove', handleMouseMove)
                      window.removeEventListener('mouseup', handleMouseUp)
                    }

                    // 立即更新一次（拖拽开始）
                    updateSplitPoint(e.clientX, false)

                    // 绑定全局事件以支持拖拽
                  }}
                >
                  {/* 滑块圆点 - 大而明显 */}
                  {/* Main Chart Area */}

                  <div className="w-full h-full bg-orange-400 rounded-full shadow-xl shadow-orange-400/50 border-2 border-orange-300 cursor-grab active:cursor-grabbing hover:scale-125 hover:shadow-orange-400/70 transition-all duration-200 flex items-center justify-center">
                    {/* 内部白点 */}
                    <div className="w-2 h-2 bg-white/90 rounded-full" />
                  </div>

                  {/* 日期标签 - 悬停时显示 */}
                  <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 px-2 py-1 text-xs text-orange-300 bg-dark-800/95 backdrop-blur-sm rounded-md border border-orange-400/40 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg">
                    {splitDate}
                  </div>
                </div>
              </div>

              {/* 滑块交互区域 - 覆盖 X 轴区域，支持拖拽 */}
              <div
                className="absolute cursor-pointer z-20"
                style={{
                  left: '60px', // Y 轴宽度
                  right: '10px', // 右侧边距
                  top: `${xAxisLineTop - 10}px`, // X 轴线上方一点，方便交互
                  height: `20px` // 交互区域高度，覆盖 X 轴线及其附近区域
                }}
                onMouseDown={(e) => {
                  e.stopPropagation()
                  const container = chartContainerRef.current
                  if (!container) return

                  // 开始拖拽
                  setIsDraggingSlider(true)

                  const updateSplitPoint = (clientX: number, isFinal: boolean = false) => {
                    const svg = container.querySelector('svg')
                    if (!svg) return

                    const svgRect = svg.getBoundingClientRect()
                    const plotLeft = svgRect.left
                    const plotWidth = svgRect.width

                    // 计算鼠标在绘图区域内的位置比例
                    const mouseX = clientX - plotLeft
                    const positionRatio = Math.max(0, Math.min(1, mouseX / plotWidth))

                    // 计算对应的数据点索引
                    const viewRange = viewEndIndex - viewStartIndex + 1
                    const relativeIndex = Math.round(positionRatio * viewRange)
                    const targetIndex = viewStartIndex + relativeIndex

                    // 找到对应的日期
                    if (targetIndex >= 0 && targetIndex < chartData.length && originalData) {
                      const targetDate = chartData[targetIndex].name
                      if (typeof targetDate === 'string') {
                        const originalIndex = originalData.findIndex((p: any) => p.date === targetDate)
                        if (originalIndex >= 60 && originalIndex < originalData.length) {
                          if (isFinal) {
                            // 释放鼠标时才触发回测更新
                            backtest.triggerBacktest(targetDate)
                            setIsDraggingSlider(false)
                            setTempSplitDate(null)
                          } else {
                            // 拖拽过程中只更新临时日期，用于显示滑块位置
                            setTempSplitDate(targetDate)
                          }
                        }
                      }
                    }
                  }

                  const handleMouseMove = (e: MouseEvent) => {
                    updateSplitPoint(e.clientX, false) // 拖拽中，不触发回测
                  }

                  const handleMouseUp = (e: MouseEvent) => {
                    updateSplitPoint(e.clientX, true) // 释放时，触发回测
                    window.removeEventListener('mousemove', handleMouseMove)
                    window.removeEventListener('mouseup', handleMouseUp)
                  }

                  // 立即更新一次（拖拽开始）
                  updateSplitPoint(e.clientX, false)

                  // 绑定全局事件以支持拖拽
                  window.addEventListener('mousemove', handleMouseMove)
                  window.addEventListener('mouseup', handleMouseUp)
                }}
              >
                {/* 悬停提示 - 轻微高亮 */}
                <div className="absolute inset-0 opacity-0 hover:opacity-[0.02] bg-orange-400 transition-opacity pointer-events-none" />
              </div>
            </>
          )
        })()}
      </div>

      {isZoomed && (
        <div className="mt-2 text-xs text-gray-500 text-center">
          当前视图：{chartData[viewStartIndex]?.name} 至 {chartData[viewEndIndex]?.name}
          ({viewEndIndex - viewStartIndex + 1} / {chartData.length} 个数据点)
        </div>
      )}

      {/* 异常区悬浮卡片 */}
      <AnimatePresence>
        {/* Event Capsule - Bloomberg风格事件摘要 */}
        {activeZone && activeZone.event_summary && (
          <div className="absolute top-16 left-1/2 -translate-x-1/2 z-50
                        bg-[#020203] border border-white/10 
                        px-4 py-2.5 rounded-lg shadow-2xl max-w-lg
                        animate-in fade-in-0 slide-in-from-top-2 duration-200">
            <div className="flex items-center gap-3">
              {/* 高影响力标记 */}
              {(activeZone.impact || 0) > 0.7 && (
                <span className="text-lg animate-pulse">✨</span>
              )}

              {/* 事件摘要 */}
              <span className="text-sm text-white/90 font-sans flex-1">
                {activeZone.event_summary}
              </span>

              {/* 涨跌幅badge - A股红涨绿跌 */}
              <span className={`text-xs px-2.5 py-1 rounded font-mono whitespace-nowrap font-semibold ${(activeZone.avg_return || 0) >= 0
                ? 'bg-red-500/20 text-red-400 border border-red-500/30'  // 红涨
                : 'bg-green-500/20 text-green-400 border border-green-500/30'  // 绿跌
                }`}>
                {((activeZone.avg_return || 0) >= 0 ? '+' : '')}
                {((activeZone.avg_return || 0) * 100).toFixed(1)}%
              </span>
            </div>

            {/* 日期范围小字 */}
            <div className="mt-1.5 text-xs text-white/40 font-mono">
              {activeZone.startDate} ~ {activeZone.endDate}
            </div>
          </div>
        )}

        {/* 原有的简单悬浮提示（作为fallback） */}
        {activeZone && !activeZone.event_summary && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="absolute top-4 left-1/2 transform -translate-x-1/2 z-50"
          >
            <div className="glass rounded-xl p-3 shadow-2xl max-w-md border border-white/10">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${activeZone.sentiment === 'positive' ? 'bg-green-500' : activeZone.sentiment === 'negative' ? 'bg-red-500' : 'bg-violet-500'}`} />
                  <span className="text-gray-400 text-xs">{activeZone.startDate} - {activeZone.endDate}</span>
                </div>
              </div>
              <p className="text-gray-200 text-sm leading-relaxed">{activeZone.summary}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 新闻侧边栏 */}
      {ticker && (
        <ChartNewsSidebar
          isOpen={newsSidebarOpen}
          onClose={handleCloseSidebar}
          news={newsData}
          loading={newsLoading}
          selectedDate={selectedDate}
          ticker={ticker}
        />
      )}
    </div>
  )
}

