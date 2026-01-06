'use client'

import { Check, Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Step } from './ChatArea'

interface StepProgressProps {
  steps: Step[]
}

export function StepProgress({ steps }: StepProgressProps) {
  return (
    <div className="space-y-2 mt-4">
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center gap-3">
          {/* 步骤图标 */}
          <div className="flex-shrink-0">
            {step.status === 'completed' && (
              <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center animate-in fade-in zoom-in duration-300">
                <Check className="w-4 h-4 text-green-400" />
              </div>
            )}
            {step.status === 'running' && (
              <div className="w-6 h-6 rounded-full bg-violet-500/20 flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-violet-400 animate-spin" />
              </div>
            )}
            {step.status === 'failed' && (
              <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center">
                <X className="w-4 h-4 text-red-400" />
              </div>
            )}
            {step.status === 'pending' && (
              <div className="w-6 h-6 rounded-full bg-dark-600 border border-white/10 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-gray-500" />
              </div>
            )}
          </div>

          {/* 步骤信息 */}
          <div className="flex-1">
            <div className={cn(
              "text-sm",
              step.status === 'completed' && "text-green-400",
              step.status === 'running' && "text-violet-400",
              step.status === 'failed' && "text-red-400",
              step.status === 'pending' && "text-gray-500"
            )}>
              {step.name}
            </div>
            {step.message && (
              <div className="text-xs text-gray-500 mt-0.5">{step.message}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

