/**
 * Sessions API Client
 * ====================
 *
 * API functions for session management
 */

import type { SessionMetadata } from '../types/session'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface CreateSessionResponse {
    session_id: string
    title: string
    created_at: string
}

/**
 * Create a new session
 */
export async function createSession(title?: string): Promise<CreateSessionResponse> {
    const response = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: title || null }),
    })

    if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`)
    }

    return response.json()
}

/**
 * Get all sessions
 */
export async function listSessions(): Promise<SessionMetadata[]> {
    const response = await fetch(`${API_BASE}/api/sessions`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    })

    if (!response.ok) {
        throw new Error(`Failed to fetch sessions: ${response.statusText}`)
    }

    return response.json()
}

/**
 * Delete a session
 */
export async function deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
    })

    if (!response.ok) {
        throw new Error(`Failed to delete session: ${response.statusText}`)
    }
}

/**
 * Update session title
 */
export async function updateSessionTitle(
    sessionId: string,
    title: string
): Promise<void> {
    const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title }),
    })

    if (!response.ok) {
        throw new Error(`Failed to update session: ${response.statusText}`)
    }
}
