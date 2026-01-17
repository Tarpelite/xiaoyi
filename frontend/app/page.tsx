'use client'

import { ChatArea } from '@/components/chat/ChatArea'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { useSessionManager } from '@/hooks/useSessionManager'

export default function Home() {
  const {
    sessions,
    activeSessionId,
    createNewSession,
    switchSession,
    deleteSession,
    renameSession,
  } = useSessionManager()

  return (
    <div className="flex h-screen gradient-mesh">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={createNewSession}
        onSelectSession={switchSession}
        onDeleteSession={deleteSession}
        onRenameSession={renameSession}
      />

      {/* Main Chat Area */}
      <ChatArea
        key={activeSessionId || 'new'}
        sessionId={activeSessionId}
      />
    </div>
  )
}
