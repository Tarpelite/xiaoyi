/**
 * Session Types
 * ==============
 * 
 * Data structures for multi-session management
 */

export interface SessionMetadata {
    session_id: string
    title: string
    created_at: string
    updated_at: string
    message_count: number
}

export interface SessionListItem extends SessionMetadata {
    preview?: string  // First message preview
    isActive?: boolean
}
