/**
 * useSessionManager Hook
 * =======================
 * 
 * Manages session list and active session state
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import type { SessionMetadata } from '@/lib/types/session'
import { listSessions, deleteSession as apiDeleteSession, updateSessionTitle as apiUpdateSessionTitle } from '@/lib/api/sessions'

export function useSessionManager() {
    const [sessions, setSessions] = useState<SessionMetadata[]>([])
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    // Load sessions on mount
    const loadSessions = useCallback(async () => {
        try {
            setIsLoading(true)
            const sessionList = await listSessions()
            setSessions(sessionList)

            // Restore last active session from localStorage
            const storedSessionId = typeof window !== 'undefined'
                ? localStorage.getItem('chat_session_id')
                : null

            if (storedSessionId && sessionList.some(s => s.session_id === storedSessionId)) {
                setActiveSessionId(storedSessionId)
            } else if (sessionList.length > 0) {
                // Default to most recent session
                setActiveSessionId(sessionList[0].session_id)
            }
        } catch (error) {
            console.error('Failed to load sessions:', error)
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        loadSessions()
    }, [loadSessions])

    // Create new session
    const createNewSession = useCallback(() => {
        // Clear current session ID - new session will be created on first message
        setActiveSessionId(null)
        if (typeof window !== 'undefined') {
            localStorage.removeItem('chat_session_id')
        }
    }, [])

    // Switch to a different session
    const switchSession = useCallback((sessionId: string) => {
        setActiveSessionId(sessionId)
        if (typeof window !== 'undefined') {
            localStorage.setItem('chat_session_id', sessionId)
        }
    }, [])

    // Delete session
    const deleteSession = useCallback(async (sessionId: string) => {
        try {
            await apiDeleteSession(sessionId)

            // Update local state
            setSessions(prev => prev.filter(s => s.session_id !== sessionId))

            // If deleting active session, switch to another or create new
            if (activeSessionId === sessionId) {
                const remainingSessions = sessions.filter(s => s.session_id !== sessionId)
                if (remainingSessions.length > 0) {
                    switchSession(remainingSessions[0].session_id)
                } else {
                    createNewSession()
                }
            }
        } catch (error) {
            console.error('Failed to delete session:', error)
            throw error
        }
    }, [sessions, activeSessionId, switchSession, createNewSession])

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
        try {
            const sessionList = await listSessions()
            setSessions(sessionList)
        } catch (error) {
            console.error('Failed to refresh sessions:', error)
        }
    }, [])

    // Auto-refresh sessions every 3 seconds to detect new sessions
    useEffect(() => {
        const interval = setInterval(() => {
            refreshSessions()
        }, 3000)

        return () => clearInterval(interval)
    }, [refreshSessions])

    return {
        sessions,
        activeSessionId,
        isLoading,
        createNewSession,
        switchSession,
        deleteSession,
        renameSession,
        refreshSessions,
    }
}
