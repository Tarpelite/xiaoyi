/**
 * Sidebar Component
 * ==================
 * 
 * Collapsible sidebar for multi-session management
 * Gemini-style design with new chat button and session list
 */

'use client'

import { useState } from 'react'
import { PanelLeftClose, PanelLeft, Plus, Settings } from 'lucide-react'
import { SessionListItem } from './SessionListItem'
import type { SessionMetadata } from '@/lib/types/session'

interface SidebarProps {
    sessions: SessionMetadata[]
    activeSessionId: string | null
    onNewChat: () => void
    onSelectSession: (sessionId: string) => void
    onDeleteSession: (sessionId: string) => void
    onRenameSession: (sessionId: string, newTitle: string) => void
}

export function Sidebar({
    sessions,
    activeSessionId,
    onNewChat,
    onSelectSession,
    onDeleteSession,
    onRenameSession,
}: SidebarProps) {
    const [collapsed, setCollapsed] = useState(false)

    return (
        <>
            {/* Desktop Sidebar */}
            <aside
                className={`hidden md:flex flex-col bg-dark-800/50 border-r border-white/5 transition-all duration-300 ${collapsed ? 'w-16' : 'w-[280px]'
                    }`}
            >
                {/* Top Section - Toggle & New Chat */}
                <div className="h-14 border-b border-white/5 flex items-center justify-between px-3">
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="p-2 hover:bg-dark-600 rounded-lg transition-colors"
                        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    >
                        {collapsed ? (
                            <PanelLeft className="w-5 h-5 text-gray-400" />
                        ) : (
                            <PanelLeftClose className="w-5 h-5 text-gray-400" />
                        )}
                    </button>

                    {!collapsed && (
                        <button
                            onClick={onNewChat}
                            className="flex items-center gap-2 px-3 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg transition-colors text-sm font-medium"
                        >
                            <Plus className="w-4 h-4" />
                            New Chat
                        </button>
                    )}
                </div>

                {/* Middle Section - Session List */}
                <div className="flex-1 overflow-y-auto py-2 px-2">
                    {!collapsed ? (
                        sessions.length > 0 ? (
                            sessions.map((session) => (
                                <SessionListItem
                                    key={session.session_id}
                                    session={session}
                                    isActive={session.session_id === activeSessionId}
                                    onSelect={() => onSelectSession(session.session_id)}
                                    onDelete={() => onDeleteSession(session.session_id)}
                                    onRename={(newTitle) => onRenameSession(session.session_id, newTitle)}
                                />
                            ))
                        ) : (
                            <div className="text-center text-gray-500 text-sm mt-8 px-4">
                                No conversations yet
                            </div>
                        )
                    ) : (
                        // Collapsed view - show minimal indicators
                        sessions.slice(0, 5).map((session) => (
                            <button
                                key={session.session_id}
                                onClick={() => onSelectSession(session.session_id)}
                                className={`w-full h-10 rounded-lg mb-1 transition-colors ${session.session_id === activeSessionId
                                    ? 'bg-violet-600/20 border border-violet-500/30'
                                    : 'hover:bg-dark-600'
                                    }`}
                                title={session.title}
                            >
                                <div className="w-2 h-2 rounded-full bg-gray-400 mx-auto" />
                            </button>
                        ))
                    )}
                </div>

                {/* Bottom Section - Settings */}
                {!collapsed && (
                    <div className="border-t border-white/5 p-3">
                        <button className="flex items-center gap-3 w-full px-3 py-2 hover:bg-dark-600 rounded-lg transition-colors text-sm text-gray-300">
                            <Settings className="w-4 h-4" />
                            Settings
                        </button>
                    </div>
                )}
            </aside>

            {/* Mobile Drawer - TODO: Implement drawer for mobile */}
        </>
    )
}
