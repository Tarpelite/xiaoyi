'use client'

import { FileText, TrendingUp, AlertTriangle } from 'lucide-react'
import type { Message } from './ChatArea'

interface AnalysisCardsProps {
  analysis: NonNullable<Message['analysis']>
}

export function AnalysisCards({ analysis }: AnalysisCardsProps) {
  return (
    <div className="grid grid-cols-3 gap-3 max-w-3xl">
      {/* 研报共识卡片 */}
      {analysis.reportConsensus && (
        <ReportConsensusCard data={analysis.reportConsensus} />
      )}
      
      {/* 模型预测卡片 */}
      {analysis.modelPrediction && (
        <ModelPredictionCard data={analysis.modelPrediction} />
      )}
      
      {/* 异常检测卡片 */}
      {analysis.anomalyDetection && (
        <AnomalyDetectionCard data={analysis.anomalyDetection} />
      )}
    </div>
  )
}

// 研报共识卡片
function ReportConsensusCard({ data }: { 
  data: NonNullable<Message['analysis']>['reportConsensus'] 
}) {
  if (!data) return null
  
  const total = data.ratings.buy + data.ratings.hold + data.ratings.sell
  const buyPercent = Math.round((data.ratings.buy / total) * 100)
  
  return (
    <div className="glass rounded-xl p-4 hover-lift cursor-pointer">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center">
          <FileText className="w-4 h-4 text-violet-400" />
        </div>
        <div>
          <div className="text-xs font-medium text-gray-300">研报共识</div>
          <div className="text-[10px] text-gray-500">覆盖 {data.totalReports} 份</div>
        </div>
      </div>
      
      {/* 评级分布 */}
      <div className="mb-3">
        <div className="flex gap-1 h-2 rounded-full overflow-hidden bg-dark-600">
          <div 
            className="bg-green-500 rounded-l-full transition-all" 
            style={{ width: `${buyPercent}%` }}
          />
          <div 
            className="bg-yellow-500" 
            style={{ width: `${Math.round((data.ratings.hold / total) * 100)}%` }}
          />
          <div 
            className="bg-red-500 rounded-r-full" 
            style={{ width: `${Math.round((data.ratings.sell / total) * 100)}%` }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px]">
          <span className="text-green-400">买入 {data.ratings.buy}</span>
          <span className="text-yellow-400">持有 {data.ratings.hold}</span>
          <span className="text-red-400">卖出 {data.ratings.sell}</span>
        </div>
      </div>
      
      {/* 目标价 */}
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] text-gray-500">目标价</span>
        <div className="text-right">
          <span className="text-lg font-bold text-violet-400">¥{data.avgTargetPrice}</span>
          <span className="text-[10px] text-green-400 ml-1">
            +{Math.round(((data.avgTargetPrice - data.currentPrice) / data.currentPrice) * 100)}%
          </span>
        </div>
      </div>
    </div>
  )
}

// 模型预测卡片
function ModelPredictionCard({ data }: { 
  data: NonNullable<Message['analysis']>['modelPrediction'] 
}) {
  if (!data) return null
  
  const isPositive = data.prediction > 0
  
  return (
    <div className="glass rounded-xl p-4 hover-lift cursor-pointer">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
          <TrendingUp className="w-4 h-4 text-cyan-400" />
        </div>
        <div>
          <div className="text-xs font-medium text-gray-300">模型预测</div>
          <div className="text-[10px] text-gray-500">{data.model}</div>
        </div>
      </div>
      
      {/* 预测结果 */}
      <div className="text-center mb-3">
        <div className={`text-3xl font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {isPositive ? '+' : ''}{data.prediction}%
        </div>
        <div className="text-[10px] text-gray-500">下季度预期涨幅</div>
      </div>
      
      {/* 模型指标 */}
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-gray-500">MASE</span>
        <span className="text-cyan-400 font-mono">{data.mase}</span>
      </div>
      <div className="flex items-center justify-between text-[10px] mt-1">
        <span className="text-gray-500">95%置信</span>
        <span className="text-gray-400 font-mono">
          ¥{data.confidenceInterval[0]}-{data.confidenceInterval[1]}
        </span>
      </div>
    </div>
  )
}

// 异常检测卡片
function AnomalyDetectionCard({ data }: { 
  data: NonNullable<Message['analysis']>['anomalyDetection'] 
}) {
  if (!data) return null
  
  return (
    <div className="glass rounded-xl p-4 hover-lift cursor-pointer">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-orange-400" />
        </div>
        <div>
          <div className="text-xs font-medium text-gray-300">异常检测</div>
          <div className="text-[10px] text-gray-500">近90天</div>
        </div>
      </div>
      
      {/* 异常数量 */}
      <div className="text-center mb-3">
        <div className="text-3xl font-bold text-orange-400">{data.count}</div>
        <div className="text-[10px] text-gray-500">个异常波动</div>
      </div>
      
      {/* 异常列表 */}
      <div className="space-y-1">
        {data.anomalies.slice(0, 2).map((anomaly, index) => (
          <div key={index} className="flex items-center justify-between text-[10px]">
            <span className="text-gray-500">{anomaly.date}</span>
            <span className={anomaly.change > 0 ? 'text-green-400' : 'text-red-400'}>
              {anomaly.change > 0 ? '+' : ''}{anomaly.change}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
