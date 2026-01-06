'use client'

import { TrendingUp, TrendingDown, Activity, BarChart3, FileText, ExternalLink } from 'lucide-react'

export function AnalysisPanel() {
  return (
    <aside className="w-80 border-l border-white/5 bg-dark-800/30 flex flex-col overflow-hidden">
      {/* 股票信息头部 */}
      <div className="p-5 border-b border-white/5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-lg font-bold">
              茅
            </div>
            <div>
              <h3 className="font-semibold">贵州茅台</h3>
              <p className="text-xs text-gray-500">600519.SH</p>
            </div>
          </div>
          <button className="p-2 hover:bg-dark-600 rounded-lg transition-colors">
            <ExternalLink className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        
        {/* 实时价格 */}
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-bold">¥1,850.00</span>
          <div className="flex items-center text-green-400 text-sm">
            <TrendingUp className="w-4 h-4 mr-1" />
            <span>+2.35%</span>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">2024-12-27 15:00 收盘</p>
      </div>

      {/* 时序特征 */}
      <div className="p-5 border-b border-white/5">
        <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-3">时序特征</h4>
        <div className="space-y-3">
          <FeatureBar label="趋势强度" value={0.78} color="violet" />
          <FeatureBar label="季节性" value={0.32} color="cyan" />
          <FeatureBar label="波动性" value={0.45} color="orange" />
          <FeatureBar label="自相关" value={0.89} color="green" />
        </div>
      </div>

      {/* 模型对比 */}
      <div className="p-5 border-b border-white/5">
        <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-3">模型对比</h4>
        <div className="space-y-2">
          <ModelRow name="AutoARIMA" mase={0.82} selected />
          <ModelRow name="Prophet" mase={0.91} />
          <ModelRow name="Chronos" mase={0.95} />
          <ModelRow name="SeasonalNaive" mase={1.00} baseline />
        </div>
      </div>

      {/* 相关研报 */}
      <div className="flex-1 overflow-y-auto p-5">
        <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-3">相关研报</h4>
        <div className="space-y-2">
          <ReportItem 
            title="贵州茅台2024年报前瞻"
            institution="中信证券"
            rating="买入"
            date="2024-12-20"
          />
          <ReportItem 
            title="白酒行业深度：龙头稳健增长"
            institution="华泰证券"
            rating="增持"
            date="2024-12-18"
          />
          <ReportItem 
            title="茅台批价企稳，关注春节动销"
            institution="国泰君安"
            rating="买入"
            date="2024-12-15"
          />
        </div>
      </div>
    </aside>
  )
}

// 特征进度条组件
function FeatureBar({ label, value, color }: { 
  label: string
  value: number
  color: 'violet' | 'cyan' | 'orange' | 'green'
}) {
  const colorClasses = {
    violet: 'bg-violet-500',
    cyan: 'bg-cyan-500',
    orange: 'bg-orange-500',
    green: 'bg-green-500',
  }
  
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300 font-mono">{value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 bg-dark-600 rounded-full overflow-hidden">
        <div 
          className={`h-full rounded-full transition-all ${colorClasses[color]}`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  )
}

// 模型行组件
function ModelRow({ name, mase, selected, baseline }: {
  name: string
  mase: number
  selected?: boolean
  baseline?: boolean
}) {
  return (
    <div className={`flex items-center justify-between p-2 rounded-lg ${
      selected ? 'bg-violet-500/20 border border-violet-500/30' : 'hover:bg-dark-600/50'
    }`}>
      <div className="flex items-center gap-2">
        {selected && <div className="w-1.5 h-1.5 rounded-full bg-violet-500" />}
        <span className={`text-sm ${selected ? 'text-violet-300 font-medium' : 'text-gray-400'}`}>
          {name}
        </span>
        {baseline && (
          <span className="px-1.5 py-0.5 bg-gray-700 rounded text-[10px] text-gray-500">基准</span>
        )}
      </div>
      <span className={`text-sm font-mono ${selected ? 'text-violet-400' : 'text-gray-500'}`}>
        {mase.toFixed(2)}
      </span>
    </div>
  )
}

// 研报项组件
function ReportItem({ title, institution, rating, date }: {
  title: string
  institution: string
  rating: string
  date: string
}) {
  const ratingColor = rating === '买入' ? 'text-green-400 bg-green-500/20' : 'text-yellow-400 bg-yellow-500/20'
  
  return (
    <div className="p-3 bg-dark-600/30 rounded-lg hover:bg-dark-600/50 cursor-pointer transition-colors">
      <div className="flex items-start justify-between gap-2 mb-1">
        <h5 className="text-sm text-gray-300 line-clamp-1">{title}</h5>
        <span className={`px-1.5 py-0.5 rounded text-[10px] flex-shrink-0 ${ratingColor}`}>
          {rating}
        </span>
      </div>
      <div className="flex items-center gap-2 text-[10px] text-gray-500">
        <span>{institution}</span>
        <span>·</span>
        <span>{date}</span>
      </div>
    </div>
  )
}
