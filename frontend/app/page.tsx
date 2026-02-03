'use client'

import { Suspense } from 'react'
import { ChatArea } from '@/components/chat/ChatArea'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { useSessionManager } from '@/hooks/useSessionManager'

function HomeContent() {
  const {
    sessions,
    activeSessionId,
    chatKey,
    createNewSession,
    switchSession,
    deleteSession,
    renameSession,
    refreshSessions,
    isAuthenticated,
    login,
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
        key={`${activeSessionId || 'new'}-${chatKey}`}
        sessionId={activeSessionId}
        onSessionCreated={() => {
          // 只刷新会话列表，不切换会话
          // 原因：切换会话会导致 key 变化，组件重新挂载，中断正在进行的流
          // ChatArea 内部已经有正确的 sessionId，会自动更新 URL
          refreshSessions()
        }}
      />
    </div>
  )
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="flex h-screen gradient-mesh items-center justify-center">
        <div className="text-white/60">加载中...</div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  )
}
