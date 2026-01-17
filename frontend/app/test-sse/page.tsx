/**
 * SSE Streaming Test Page
 * ========================
 * 
 * 简单的测试页面，用于验证SSE流式thinking效果
 * 
 * 用法:
 * 1. 访问 /test-sse
 * 2. 输入消息 (例如: "分析茅台")
 * 3. 观察thinking内容逐字显示
 */

'use client'

import { useState } from 'react'
import { useSSEStream } from '@/hooks/useSSEStream'
import { useTypewriter } from '@/hooks/useTypewriter'

export default function TestSSEPage() {
    const [inputText, setInputText] = useState('')
    const [isConnected, setIsConnected] = useState(false)
    const [thinkingContent, setThinkingContent] = useState('')
    const [intent, setIntent] = useState<any>(null)
    const [error, setError] = useState<string | null>(null)
    const [sseUrl, setSSEUrl] = useState<string | null>(null)

    // 使用打字机效果显示thinking
    const displayedThinking = useTypewriter(thinkingContent, { enabled: true })

    // SSE连接
    const { status, retryCount, close } = useSSEStream(sseUrl, {
        onSessionCreated: (data) => {
            console.log('[SSE Test] Session created:', data)
        },
        onThinkingChunk: (data) => {
            console.log('[SSE Test] Thinking chunk:', data.chunk)
            setThinkingContent(data.accumulated)
        },
        onThinkingComplete: (data) => {
            console.log('[SSE Test] Thinking complete:', data.thinking_content)
            setThinkingContent(data.thinking_content)
            // 测试完成，主动断开连接
            setTimeout(() => {
                console.log('[SSE Test] Auto-disconnecting after thinking complete')
                setSSEUrl(null)
            }, 100)
        },
        onIntentDetermined: (data) => {
            console.log('[SSE Test] Intent:', data)
            setIntent(data)
        },
        onError: (data) => {
            console.error('[SSE Test] Error:', data)
            setError(data.error)
        },
        onConnectionChange: (status) => {
            console.log('[SSE Test] Connection status:', status)
            setIsConnected(status === 'open')
        },
        autoReconnect: false,  // 禁用自动重连，测试页面手动控制
    })

    const handleConnect = async () => {
        if (!inputText.trim()) {
            alert('请输入消息')
            return
        }

        setThinkingContent('')
        setIntent(null)
        setError(null)

        const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

        // 构造SSE URL (GET参数)
        const params = new URLSearchParams({
            message: inputText,
            model: 'prophet',
            context: ''
        })

        const url = `${API_BASE}/api/v2/stream/analysis?${params.toString()}`
        setSSEUrl(url)
    }

    const handleDisconnect = () => {
        setSSEUrl(null)
        setIsConnected(false)
    }

    return (
        <div className="min-h-screen bg-gray-900 text-white p-8">
            <div className="max-w-4xl mx-auto">
                <h1 className="text-3xl font-bold mb-8">SSE Streaming Test</h1>

                {/* 输入区 */}
                <div className="bg-gray-800 rounded-lg p-6 mb-6">
                    <label className="block text-sm font-medium mb-2">
                        输入消息:
                    </label>
                    <div className="flex gap-4">
                        <input
                            type="text"
                            className="flex-1 bg-gray-700 border border-gray-600 rounded px-4 py-2"
                            placeholder="例如: 分析茅台"
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !isConnected) {
                                    handleConnect()
                                }
                            }}
                            disabled={isConnected}
                        />
                        {!isConnected ? (
                            <button
                                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded font-medium"
                                onClick={handleConnect}
                                disabled={isConnected}
                            >
                                连接
                            </button>
                        ) : (
                            <button
                                className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded font-medium"
                                onClick={handleDisconnect}
                            >
                                断开
                            </button>
                        )}
                    </div>
                </div>

                {/* 状态显示 */}
                <div className="bg-gray-800 rounded-lg p-6 mb-6">
                    <h2 className="text-xl font-semibold mb-4">连接状态</h2>
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <div className={`w-3 h-3 rounded-full ${status === 'open' ? 'bg-green-500' :
                                status === 'connecting' ? 'bg-yellow-500' :
                                    status === 'error' ? 'bg-red-500' :
                                        'bg-gray-500'
                                }`} />
                            <span className="text-sm">状态: {status}</span>
                        </div>
                        {retryCount > 0 && (
                            <div className="text-sm text-yellow-400">
                                重试次数: {retryCount}
                            </div>
                        )}
                        {error && (
                            <div className="text-sm text-red-400">
                                错误: {error}
                            </div>
                        )}
                    </div>
                </div>

                {/* Thinking内容 (打字机效果) */}
                <div className="bg-gray-800 rounded-lg p-6 mb-6">
                    <h2 className="text-xl font-semibold mb-4">Thinking (打字机效果)</h2>
                    {displayedThinking ? (
                        <div className="text-sm whitespace-pre-wrap font-mono bg-gray-900 p-4 rounded">
                            {displayedThinking}
                        </div>
                    ) : (
                        <div className="text-gray-500 text-sm">等待thinking内容...</div>
                    )}
                    <div className="mt-2 text-xs text-gray-500">
                        长度: {displayedThinking.length} / {thinkingContent.length}
                    </div>
                </div>

                {/* Intent信息 */}
                {intent && (
                    <div className="bg-gray-800 rounded-lg p-6">
                        <h2 className="text-xl font-semibold mb-4">Intent</h2>
                        <pre className="text-xs overflow-auto">
                            {JSON.stringify(intent, null, 2)}
                        </pre>
                    </div>
                )}

                {/* 使用说明 */}
                <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-6 mt-6">
                    <h3 className="text-lg font-semibold mb-2">测试说明</h3>
                    <ol className="text-sm space-y-1 list-decimal list-inside">
                        <li>输入消息 (例如: "分析茅台")</li>
                        <li>点击"连接"按钮</li>
                        <li>观察Thinking内容逐字显示 (打字机效果)</li>
                        <li>查看Intent识别结果</li>
                        <li>打开浏览器控制台查看事件日志</li>
                    </ol>
                </div>

                {/* Debug信息 */}
                <div className="bg-gray-800 rounded-lg p-4 mt-6">
                    <details>
                        <summary className="cursor-pointer text-sm font-medium">
                            Debug Info
                        </summary>
                        <div className="mt-4 text-xs space-y-2">
                            <div>SSE URL: {sseUrl || 'Not connected'}</div>
                            <div>API Base: {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}</div>
                        </div>
                    </details>
                </div>
            </div>
        </div>
    )
}
