'use client'

import { useState } from 'react'
import { Plus, Database, TrendingUp, Settings, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'

// 模拟历史对话数据
const mockConversations = [
  { id: '1', title: '茅台 Q1 预测分析', preview: '预测上涨8.5%，建议买入...', time: '今天 14:32', icon: '📈' },
  { id: '2', title: '新能源行业研报整理', preview: '整合了15份研报观点...', time: '昨天 09:15', icon: '🔍' },
  { id: '3', title: '宁德时代异常检测', preview: '发现3个异常波动点...', time: '12月26日', icon: '⚠️' },
]

export function Sidebar() {
  const [activeConversation, setActiveConversation] = useState<string | null>('1')

  return (
    <aside className="w-72 border-r border-white/5 flex flex-col bg-dark-800/50">
      {/* Logo */}
      <div className="p-5 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg glow-purple">
            <span className="text-xl">🔮</span>
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
              小易猜猜
            </h1>
            <p className="text-[10px] text-gray-500 tracking-wider">TIMEAGENT v1.0</p>
          </div>
        </div>
      </div>

      {/* 新建对话按钮 */}
      <div className="p-4">
        <button className="w-full py-2.5 px-4 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition-all hover-lift">
          <Plus className="w-4 h-4" />
          新建分析
        </button>
      </div>

      {/* 数据源区域 */}
      <div className="px-4 mb-4">
        <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 px-2">我的数据</div>
        <div className="space-y-1">
          {/* TODO: 这里可以让新手来实现数据源选择组件 */}
          <DataSourceItem 
            icon={<Database className="w-4 h-4 text-violet-400" />}
            title="研报数据库"
            subtitle="12,847 份研报 · 5年"
            active
            hasIndicator
          />
          <DataSourceItem 
            icon={<TrendingUp className="w-4 h-4 text-cyan-400" />}
            title="A股行情"
            subtitle="实时更新"
          />
        </div>
      </div>

      {/* 历史对话 */}
      <div className="flex-1 overflow-y-auto px-4">
        <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 px-2">历史对话</div>
        <div className="space-y-1">
          {mockConversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              {...conv}
              active={activeConversation === conv.id}
              onClick={() => setActiveConversation(conv.id)}
            />
          ))}
        </div>
      </div>

      {/* 底部用户信息 */}
      <div className="p-4 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center text-sm font-bold">
            李
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium">李明</div>
            <div className="text-[10px] text-gray-500">私募研究员</div>
          </div>
          <button className="p-2 hover:bg-dark-600 rounded-lg transition-colors">
            <Settings className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </div>
    </aside>
  )
}

// 数据源项组件 - 可以拆分出去让新手实现
interface DataSourceItemProps {
  icon: React.ReactNode
  title: string
  subtitle: string
  active?: boolean
  hasIndicator?: boolean
}

function DataSourceItem({ icon, title, subtitle, active, hasIndicator }: DataSourceItemProps) {
  return (
    <div className={cn(
      "flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors",
      active ? "bg-dark-600/50 border border-violet-500/30" : "hover:bg-dark-600/30"
    )}>
      <div className={cn(
        "w-8 h-8 rounded-lg flex items-center justify-center",
        active ? "bg-violet-500/20" : "bg-gray-700/50"
      )}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-200 truncate">{title}</div>
        <div className="text-[10px] text-gray-500">{subtitle}</div>
      </div>
      {hasIndicator && (
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse-soft" />
      )}
    </div>
  )
}

// 对话项组件 - 可以拆分出去让新手实现
interface ConversationItemProps {
  id: string
  title: string
  preview: string
  time: string
  icon: string
  active?: boolean
  onClick?: () => void
}

function ConversationItem({ title, preview, time, icon, active, onClick }: ConversationItemProps) {
  return (
    <div 
      className={cn(
        "p-3 rounded-lg cursor-pointer transition-colors",
        active 
          ? "bg-dark-600/50 border border-white/5" 
          : "hover:bg-dark-600/30"
      )}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs">{icon}</span>
        <span className="text-sm font-medium text-gray-200">{title}</span>
      </div>
      <p className="text-xs text-gray-500 line-clamp-1">{preview}</p>
      <div className="text-[10px] text-gray-600 mt-1">{time}</div>
    </div>
  )
}
