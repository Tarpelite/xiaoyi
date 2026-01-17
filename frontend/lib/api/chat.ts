// API 基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 获取快速追问建议
export async function getSuggestions(sessionId?: string | null): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analysis/suggestions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId || null,
      }),
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }

    const data = await response.json()
    return data.suggestions || []
  } catch (error) {
    console.error('获取快速追问建议失败:', error)
    // 返回默认建议
    return [
      '帮我分析一下茅台，预测下个季度走势',
      '查看最近的市场趋势',
      '对比几只白酒股的表现',
      '生成一份投资分析报告',
    ]
  }
}


