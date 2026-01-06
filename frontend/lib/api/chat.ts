import type { Message, Step, TextContent, ChartContent, TableContent } from '@/components/chat/ChatArea'
import { PREDICTION_STEPS } from '@/components/chat/ChatArea'

// API 基础URL（假设FastAPI后端运行在本地）
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 生成时序数据（模拟从 akshare 获取）
function generateTimeSeriesData(): { table: TableContent; chart: ChartContent } {
  const now = new Date()
  const dates: string[] = []
  const prices: number[] = []
  const volumes: number[] = []
  
  // 生成过去365天的数据
  for (let i = 365; i > 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    dates.push(date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }))
    // 模拟价格数据（1800-1900之间波动）
    const basePrice = 1850
    const price = basePrice + Math.sin(i / 30) * 50 + Math.random() * 20 - 10
    prices.push(Math.round(price * 100) / 100)
    // 模拟成交量
    volumes.push(Math.floor(1000000 + Math.random() * 500000))
  }
  
  // 生成表格数据（最近20条）
  const recent20Dates = dates.slice(-20)
  const recent20Prices = prices.slice(-20)
  const recent20Volumes = volumes.slice(-20)
  
  const tableData: TableContent = {
    type: 'table',
    title: '历史时序数据（最近20条）',
    headers: ['日期', '收盘价', '成交量'],
    rows: recent20Dates.map((date, index) => [
      date,
      recent20Prices[index].toFixed(2),
      recent20Volumes[index].toLocaleString(),
    ]),
  }
  
  // 生成图表数据（完整365天）
  // 为了性能，图表数据可以采样（每5天一个点）
  const sampledDates: string[] = []
  const sampledPrices: number[] = []
  for (let i = 0; i < dates.length; i += 5) {
    sampledDates.push(dates[i])
    sampledPrices.push(prices[i])
  }
  
  const chartData: ChartContent = {
    type: 'chart',
    title: '历史价格趋势（365天）',
    data: {
      labels: sampledDates,
      datasets: [
        {
          label: '收盘价',
          data: sampledPrices,
          color: '#8b5cf6',
        },
      ],
    },
  }
  
  return { table: tableData, chart: chartData }
}

// 发送消息并获取流式响应
export async function* sendMessageStream(
  message: string,
  onStepUpdate?: (steps: Step[]) => void
): AsyncGenerator<{ type: 'step' | 'content'; data: any }, void, unknown> {
  try {
    // ========== 第一步：发送时序数据（从 akshare 获取） ==========
    // 模拟从 akshare 获取数据的延迟
    await new Promise(resolve => setTimeout(resolve, 300))
    
    const timeSeriesData = generateTimeSeriesData()
    
    // 发送表格数据
    yield { type: 'content', data: timeSeriesData.table }
    
    // 短暂延迟，让用户看到表格
    await new Promise(resolve => setTimeout(resolve, 200))
    
    // 发送图表数据
    yield { type: 'content', data: timeSeriesData.chart }
    
    // ========== 第二步：初始化步骤并开始执行 ==========
    // 初始化步骤状态
    const steps: Step[] = PREDICTION_STEPS.map(step => ({
      ...step,
      status: 'pending' as const,
    }))
    
    // 模拟步骤执行（实际应该从后端SSE流中获取）
    for (let i = 0; i < steps.length; i++) {
      // 更新当前步骤为运行中
      steps[i].status = 'running'
      steps[i].message = '处理中...'
      onStepUpdate?.(steps.map(s => ({ ...s })))
      
      yield { type: 'step', data: steps.map(s => ({ ...s })) }
      
      // 模拟处理时间
      await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1000))
      
      // 完成当前步骤
      steps[i].status = 'completed'
      steps[i].message = getStepMessage(i)
      onStepUpdate?.(steps.map(s => ({ ...s })))
      
      yield { type: 'step', data: steps.map(s => ({ ...s })) }
    }
    
    // ========== 第三步：生成最终分析结果内容 ==========
    const contents = await generateResponseContent(message)
    
    for (const content of contents) {
      yield { type: 'content', data: content }
    }
    
  } catch (error) {
    console.error('API Error:', error)
    throw error
  }
}

// 获取步骤完成消息
function getStepMessage(stepIndex: number): string {
  const messages = [
    '已获取历史数据 365 天',
    '趋势强度: 0.78, 季节性: 0.32',
    '检测到 2 个异常波动点',
    'AutoARIMA 模型最优 (MASE: 0.82)',
    '生成未来 90 天预测',
    '图表已生成',
    '分析报告已生成',
  ]
  return messages[stepIndex] || '完成'
}

// 生成响应内容（模拟，实际应该从后端获取）
async function generateResponseContent(message: string): Promise<(TextContent | ChartContent | TableContent)[]> {
  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 500))
  
  const contents: (TextContent | ChartContent | TableContent)[] = []
  
  // 添加文本内容
  contents.push({
    type: 'text',
    text: `好的！我已经完成了对 **600519.SH 贵州茅台** 的分析。以下是详细结果：`,
  })
  
  // 添加表格内容（模型对比）
  contents.push({
    type: 'table',
    title: '模型性能对比',
    headers: ['模型', 'MASE', 'MAE', 'RMSE'],
    rows: [
      ['AutoARIMA', 0.82, 45.2, 58.3],
      ['Prophet', 0.91, 50.1, 64.5],
      ['Chronos', 0.95, 52.8, 67.2],
      ['SeasonalNaive', 1.00, 55.6, 71.4],
    ],
  })
  
  // 添加图表内容（预测图）
  const now = new Date()
  const labels: string[] = []
  const historicalData: number[] = []
  const forecastData: number[] = []
  
  // 生成历史数据（过去30天）
  for (let i = 30; i > 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    labels.push(date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))
    historicalData.push(1800 + Math.random() * 100 - 50)
  }
  
  // 生成预测数据（未来30天）
  const lastPrice = historicalData[historicalData.length - 1]
  for (let i = 1; i <= 30; i++) {
    const date = new Date(now)
    date.setDate(date.getDate() + i)
    labels.push(date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))
    forecastData.push(lastPrice + (i * 2) + Math.random() * 20 - 10)
  }
  
  // 合并所有标签
  const allLabels = [...labels]
  
  // 历史数据：前面是实际数据，后面是null（不显示）
  const historicalDataFull = [...historicalData, ...new Array(30).fill(null)]
  
  // 预测数据：前面是null（不显示），后面是预测数据
  const forecastDataFull = [...new Array(30).fill(null), ...forecastData]
  
  contents.push({
    type: 'chart',
    title: '价格预测趋势图',
    data: {
      labels: allLabels,
      datasets: [
        {
          label: '历史价格',
          data: historicalDataFull,
          color: '#8b5cf6',
        },
        {
          label: '预测价格',
          data: forecastDataFull,
          color: '#06b6d4',
        },
      ],
    },
  })
  
  // 添加最终文本总结
  contents.push({
    type: 'text',
    text: `**预测结论：**
    
根据 AutoARIMA 模型分析，预计下个季度贵州茅台股价将**上涨 8.5%**，目标价位在 **¥1920 - ¥2050** 区间。

**关键指标：**
- 当前价格：¥1,850.00
- 预测涨幅：+8.5%
- 置信区间：¥1,920 - ¥2,050
- 模型准确度：MASE 0.82（优于基准模型）

建议关注春节动销情况和批价走势。`,
  })
  
  return contents
}

// 实际API调用函数（当后端准备好时使用）
export async function* sendMessageStreamReal(
  message: string,
  model: string = 'prophet',
  onStepUpdate?: (steps: Step[]) => void
): AsyncGenerator<{ type: 'step' | 'content'; data: any }, void, unknown> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, model }),
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('No response body')
  }

  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      // 跳过空行
      if (!line.trim()) continue
      
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          
          if (data.type === 'step') {
            onStepUpdate?.(data.steps)
            yield { type: 'step', data: data.steps }
          } else if (data.type === 'content') {
            // 后端会先发送时序数据，然后发送步骤更新，最后发送分析结果
            yield { type: 'content', data: data.content }
          } else if (data.type === 'error') {
            // 处理错误
            throw new Error(data.message || 'Unknown error')
          }
        } catch (e) {
          console.error('Parse error:', e, 'Line:', line)
        }
      }
    }
  }
}

