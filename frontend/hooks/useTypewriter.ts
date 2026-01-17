/**
 * Typewriter Effect Hook
 * ======================
 * 
 * 实现打字机效果的Hook，支持逐字符渲染
 * 
 * 关键技术:
 * - 使用flushSync强制同步渲染
 * - 避免不必要的重渲染
 */

import { useState, useEffect } from 'react'
import { flushSync } from 'react-dom'

export interface TypewriterOptions {
    enabled?: boolean  // 是否启用打字机效果
    speed?: number     // 打字速度(ms) - 暂未使用，因为我们实时接收chunks
}

/**
 * 打字机效果Hook
 * 
 * @param content 完整内容 (实时更新)
 * @param options 配置选项
 * @returns 当前显示的内容
 */
export function useTypewriter(
    content: string,
    options: TypewriterOptions = {}
): string {
    const { enabled = true } = options
    const [displayedContent, setDisplayedContent] = useState('')

    useEffect(() => {
        if (!enabled) {
            // 不启用打字机，直接显示全部
            setDisplayedContent(content)
            return
        }

        // 内容增长时，使用flushSync立即更新
        if (content.length > displayedContent.length) {
            flushSync(() => {
                setDisplayedContent(content)
            })
        } else if (content.length < displayedContent.length) {
            // 内容减少(新消息)，重置
            setDisplayedContent(content)
        }
    }, [content, enabled, displayedContent.length])

    return displayedContent
}
