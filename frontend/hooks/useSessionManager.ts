/**
 * useSessionManager Hook
 * =======================
 *
 * Manages session list and active session state
 * Syncs session ID with URL query parameter for bookmarking/sharing
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import type { SessionMetadata } from '@/lib/types/session'
import { listSessions, deleteSession as apiDeleteSession, updateSessionTitle as apiUpdateSessionTitle } from '@/lib/api/sessions'
import { useAuth } from '@/context/AuthContext'

export function useSessionManager() {
    const router = useRouter()
    const searchParams = useSearchParams()

    const [sessions, setSessions] = useState<SessionMetadata[]>([])
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isInitialized, setIsInitialized] = useState(false)
    const [chatKey, setChatKey] = useState(0)

    // Auth state from Context
    const { user, isAuthenticated, login, accessToken, isLoading: isLoadingAuth } = useAuth()

    // Helper: Update URL with session ID
    const updateUrl = useCallback((sessionId: string | null) => {
        if (sessionId) {
            router.replace(`/?session=${sessionId}`, { scroll: false })
        } else {
            router.replace('/', { scroll: false })
        }
    }, [router])

    // Load sessions on login or mount
    useEffect(() => {
        const loadSessions = async () => {
            const urlSessionId = searchParams.get('session')

            // ✅ 修复：等待 Auth 初始化完成
            if (isLoadingAuth) {
                return
            }

            try {
                setIsLoading(true)

                if (isAuthenticated && user && accessToken) {
                    // Load Sessions only if authenticated
                    const sessionList = await listSessions()
                    setSessions(sessionList)

                    if (urlSessionId && sessionList.some(s => s.session_id === urlSessionId)) {
                        setActiveSessionId(urlSessionId)
                    }
                } else {
                    setSessions([])
                }
            } catch (error) {
                console.error('[useSessionManager] Failed to load sessions:', error)
            } finally {
                setIsLoading(false)
                setIsInitialized(true)
            }
        }

        loadSessions()
    }, [isAuthenticated, user, searchParams, accessToken, isLoadingAuth])

    // Create new session
    const createNewSession = useCallback(() => {
        setActiveSessionId(null)
        updateUrl(null)
        // 增加 chatKey 强制 ChatArea 重新挂载（即使 activeSessionId 已经是 null）
        setChatKey(prev => prev + 1)
    }, [updateUrl])

    // Switch to a different session
    const switchSession = useCallback((sessionId: string) => {
        setActiveSessionId(sessionId)
        updateUrl(sessionId)
    }, [updateUrl])

    // Delete session
    const deleteSession = useCallback(async (sessionId: string) => {
        try {
            await apiDeleteSession(sessionId)

            // 使用函数式更新，在回调中获取最新状态并处理切换逻辑
            setSessions(prev => {
                const remaining = prev.filter(s => s.session_id !== sessionId)

                // 如果删除的是当前活动会话，切换到其他会话
                if (activeSessionId === sessionId) {
                    if (remaining.length > 0) {
                        // 延迟执行，避免在 setState 回调中调用其他 setState
                        setTimeout(() => switchSession(remaining[0].session_id), 0)
                    } else {
                        setTimeout(() => createNewSession(), 0)
                    }
                }

                return remaining
            })
        } catch (error) {
            console.error('Failed to delete session:', error)
            throw error
        }
    }, [activeSessionId, switchSession, createNewSession])  // 移除 sessions 依赖

    // Rename session
    const renameSession = useCallback(async (sessionId: string, newTitle: string) => {
        try {
            await apiUpdateSessionTitle(sessionId, newTitle)

            // Update local state
            setSessions(prev => prev.map(s =>
                s.session_id === sessionId
                    ? { ...s, title: newTitle, updated_at: new Date().toISOString() }
                    : s
            ))
        } catch (error) {
            console.error('Failed to rename session:', error)
            throw error
        }
    }, [])

    // Refresh sessions list (call after creating new message)
    const refreshSessions = useCallback(async () => {
        if (!isAuthenticated || !accessToken) return

        try {
            const sessionList = await listSessions()
            setSessions(sessionList)
        } catch (error) {
            console.error('Failed to refresh sessions:', error)
        }
    }, [isAuthenticated, accessToken])

    // Auto-refresh sessions every 3 seconds to detect new sessions
    useEffect(() => {
        // ✅ 修复：只在已认证且 Auth 完成初始化后才自动刷新
        if (!isAuthenticated || isLoadingAuth) {
            return
        }

        const interval = setInterval(() => {
            refreshSessions()
        }, 3000)

        return () => clearInterval(interval)
    }, [refreshSessions, isAuthenticated, isLoadingAuth])

    return {
        sessions,
        activeSessionId,
        isLoading,
        chatKey,  // 用于 ChatArea 的 key，强制重新挂载
        createNewSession,
        switchSession,
        deleteSession,
        renameSession,
        refreshSessions,
        user,
        isAuthenticated,
        login
    }
}
