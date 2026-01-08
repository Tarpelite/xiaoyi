'use client'

import { Check, Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Step } from './ChatArea'

interface StepProgressProps {
  steps: Step[]
}

export function StepProgress({ steps }: StepProgressProps) {
  return (
    <div className="flex items-center justify-between gap-2 py-2">
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center flex-1">
          {/* 步骤节点 */}
          <div className="flex flex-col items-center flex-1">
            {/* 步骤图标 */}
            <div className="flex-shrink-0 relative">
              {step.status === 'completed' && (
                <div className="w-8 h-8 rounded-full bg-green-500/20 border-2 border-green-500/50 flex items-center justify-center animate-in fade-in zoom-in duration-300">
                  <Check className="w-4 h-4 text-green-400" />
                </div>
              )}
              {step.status === 'running' && (
                <div className="w-8 h-8 rounded-full bg-violet-500/20 border-2 border-violet-500/50 flex items-center justify-center">
                  <Loader2 className="w-4 h-4 text-violet-400 animate-spin" />
                </div>
              )}
              {step.status === 'failed' && (
                <div className="w-8 h-8 rounded-full bg-red-500/20 border-2 border-red-500/50 flex items-center justify-center">
                  <X className="w-4 h-4 text-red-400" />
                </div>
              )}
              {step.status === 'pending' && (
                <div className="w-8 h-8 rounded-full bg-dark-600 border-2 border-white/10 flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-gray-500" />
                </div>
              )}
            </div>

            {/* 步骤名称 */}
            <div className="mt-2 text-center">
              <div className={cn(
                "text-xs font-medium",
                step.status === 'completed' && "text-green-400",
                step.status === 'running' && "text-violet-400",
                step.status === 'failed' && "text-red-400",
                step.status === 'pending' && "text-gray-500"
              )}>
                {step.name}
              </div>
            </div>
          </div>

          {/* 连接线 */}
          {index < steps.length - 1 && (
            <div className={cn(
              "flex-1 h-0.5 mx-2 -mt-6 transition-all",
              step.status === 'completed' 
                ? "bg-gradient-to-r from-green-500/50 to-green-500/20" 
                : "bg-dark-600"
            )} />
          )}
        </div>
      ))}
    </div>
  )
}

