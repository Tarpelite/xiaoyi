/**
 * SessionListItem Component
 * ==========================
 * 
 * Individual session item in the sidebar list
 * Features: hover edit/delete, active state, rename inline
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { MessageSquare, Trash2, Edit2, Check, X } from 'lucide-react'
import type { SessionMetadata } from '@/lib/types/session'

interface SessionListItemProps {
    session: SessionMetadata
    isActive: boolean
    onSelect: () => void
    onDelete: () => void
    onRename: (newTitle: string) => void
}

export function SessionListItem({
    session,
    isActive,
    onSelect,
    onDelete,
    onRename,
}: SessionListItemProps) {
    const [isEditing, setIsEditing] = useState(false)
    const [editValue, setEditValue] = useState(session.title)
    const [isHovered, setIsHovered] = useState(false)

    // 同步session.title变化到editValue
    useEffect(() => {
        setEditValue(session.title)
    }, [session.title])

    // 当会话切换时，取消编辑状态
    useEffect(() => {
        if (!isActive && isEditing) {
            handleRenameCancel()
        }
    }, [isActive])

    const handleRenameSubmit = useCallback(() => {
        console.log('[SessionListItem] handleRenameSubmit called', editValue)
        if (editValue.trim() && editValue !== session.title) {
            onRename(editValue.trim())
        }
        setIsEditing(false)
    }, [editValue, session.title, onRename])

    const handleRenameCancel = useCallback(() => {
        console.log('[SessionListItem] handleRenameCancel called')
        setEditValue(session.title)
        setIsEditing(false)
    }, [session.title])

    // Format relative time
    const getRelativeTime = (isoDate: string) => {
        const date = new Date(isoDate)
        const now = new Date()
        const diff = now.getTime() - date.getTime()

        const minutes = Math.floor(diff / 60000)
        const hours = Math.floor(diff / 3600000)
        const days = Math.floor(diff / 86400000)

        if (minutes < 1) return 'Just now'
        if (minutes < 60) return `${minutes}m ago`
        if (hours < 24) return `${hours}h ago`
        if (days < 7) return `${days}d ago`
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }

    return (
        <div
            className={`group relative mb-1 rounded-lg transition-all ${isActive
                ? 'bg-violet-600/20 border border-violet-500/30'
                : 'hover:bg-dark-600 border border-transparent'
                }`}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {isEditing ? (
                // 编辑模式：不使用button包裹，直接显示编辑表单
                <div className="w-full px-3 py-2.5">
                    <div className="flex items-start gap-2">
                        <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400" />
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1 pr-0">
                                <input
                                    type="text"
                                    value={editValue}
                                    onChange={(e) => setEditValue(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') handleRenameSubmit()
                                        if (e.key === 'Escape') handleRenameCancel()
                                    }}
                                    className="flex-1 min-w-0 px-2 py-1 bg-dark-700 border border-violet-500/50 rounded text-sm text-gray-200 focus:outline-none focus:border-violet-500"
                                    autoFocus
                                />
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        console.log('[SessionListItem] Confirm button clicked')
                                        e.preventDefault()
                                        e.stopPropagation()
                                        handleRenameSubmit()
                                    }}
                                    className="p-1 hover:bg-dark-500 rounded flex-shrink-0"
                                >
                                    <Check className="w-3.5 h-3.5 text-green-400" />
                                </button>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        console.log('[SessionListItem] Cancel button clicked')
                                        e.preventDefault()
                                        e.stopPropagation()
                                        handleRenameCancel()
                                    }}
                                    className="p-1 hover:bg-dark-500 rounded flex-shrink-0"
                                >
                                    <X className="w-3.5 h-3.5 text-red-400" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            ) : (
                // 正常模式：可点击的session按钮
                <button
                    onClick={onSelect}
                    className="w-full text-left px-3 py-2.5 relative"
                >
                    <div className="flex items-start gap-2">
                        <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400" />

                        <div className="flex-1 min-w-0">
                            <div className="text-sm text-gray-200 truncate pr-12">
                                {session.title}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5">
                                {getRelativeTime(session.updated_at)}
                            </div>
                        </div>
                    </div>
                </button>
            )}

            {/* Hover Actions */}
            {!isEditing && isHovered && (
                <div className="absolute right-2 top-2 flex items-center gap-1 bg-dark-800 rounded-lg border border-white/10 p-1">
                    <button
                        onClick={(e) => {
                            e.stopPropagation()
                            setIsEditing(true)
                        }}
                        className="p-1 hover:bg-dark-600 rounded transition-colors"
                        title="Rename"
                    >
                        <Edit2 className="w-3.5 h-3.5 text-gray-400" />
                    </button>
                    <button
                        onClick={(e) => {
                            e.stopPropagation()
                            onDelete()
                        }}
                        className="p-1 hover:bg-red-600/20 rounded transition-colors"
                        title="Delete"
                    >
                        <Trash2 className="w-3.5 h-3.5 text-gray-400 hover:text-red-400" />
                    </button>
                </div>
            )}
        </div>
    )
}
