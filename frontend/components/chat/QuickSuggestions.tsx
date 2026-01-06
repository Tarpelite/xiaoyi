'use client'

interface QuickSuggestionsProps {
  suggestions: string[]
  onSelect: (suggestion: string) => void
}

export function QuickSuggestions({ suggestions, onSelect }: QuickSuggestionsProps) {
  return (
    <div className="px-6 pb-2">
      <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
        <span className="text-[10px] text-gray-500 flex-shrink-0">快捷追问:</span>
        <div className="flex gap-2">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => onSelect(suggestion)}
              className="px-3 py-1.5 bg-dark-600/50 hover:bg-dark-500/50 border border-white/5 hover:border-violet-500/30 rounded-full text-xs text-gray-400 hover:text-gray-200 whitespace-nowrap transition-all"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
