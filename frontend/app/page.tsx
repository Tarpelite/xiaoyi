import { ChatArea } from '@/components/chat/ChatArea'

export default function Home() {
  return (
    <div className="flex h-screen gradient-mesh">
      {/* 主对话区 */}
      <ChatArea />
    </div>
  )
}
