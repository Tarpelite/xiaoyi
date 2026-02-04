'use client'

import React, { Suspense, useState, useEffect } from 'react'
import { ChatArea } from '@/components/chat/ChatArea'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { ProfileCompletionModal } from '@/components/modals/ProfileCompletionModal'
import { useSessionManager } from '@/hooks/useSessionManager'
import { useAuth } from '@/context/AuthContext'

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

  const { needsProfileCompletion } = useAuth()
  const [showProfileCompletion, setShowProfileCompletion] = useState(false)

  // 当检测到需要补全资料时，显示模态框
  useEffect(() => {
    if (needsProfileCompletion && isAuthenticated) {
      setShowProfileCompletion(true)
    } else {
      setShowProfileCompletion(false)
    }
  }, [needsProfileCompletion, isAuthenticated])

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

      {/* 资料补全模态框 */}
      <ProfileCompletionModal
        isOpen={showProfileCompletion}
        onClose={() => setShowProfileCompletion(false)}
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
