import type { InfographicThemeProps } from './types'
import { WORKFLOW_STEPS, CLI_COMMANDS, QUICK_TIPS } from './types'

const STAGE_COLORS = [
  { border: 'border-pink-500', text: 'text-pink-600', bg: 'bg-pink-500', stroke: '#ec4899', shadow: 'shadow-[4px_4px_0px_#be185d]' },
  { border: 'border-blue-500', text: 'text-blue-600', bg: 'bg-blue-500', stroke: '#3b82f6', shadow: 'shadow-[4px_4px_0px_#1d4ed8]' },
  { border: 'border-green-400', text: 'text-green-600', bg: 'bg-green-400', stroke: '#4ade80', shadow: 'shadow-[4px_4px_0px_#15803d]' },
  { border: 'border-orange-500', text: 'text-orange-600', bg: 'bg-orange-500', stroke: '#f97316', shadow: 'shadow-[4px_4px_0px_#c2410c]' },
  { border: 'border-violet-500', text: 'text-violet-600', bg: 'bg-violet-500', stroke: '#8b5cf6', shadow: 'shadow-[4px_4px_0px_#5b21b6]' },
]

const HINT_COLORS = [
  { bg: 'bg-pink-100', border: 'border-pink-500', label: 'text-pink-600' },
  { bg: 'bg-blue-100', border: 'border-blue-500', label: 'text-blue-600' },
  { bg: 'bg-green-100', border: 'border-green-500', label: 'text-green-600' },
  { bg: 'bg-orange-100', border: 'border-orange-500', label: 'text-orange-600' },
]

function ArcadeIcon({ step, color }: { step: number; color: string }) {
  const common = { fill: 'none', stroke: color, strokeWidth: 3, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (step) {
    case 0:
      return (
        <svg width="30" height="30" viewBox="0 0 30 30">
          <rect x="4" y="4" width="22" height="22" rx="2" {...common} strokeWidth={2.5} />
          <path d="M10 15.5 L13.5 19 L21 11" {...common} />
        </svg>
      )
    case 1:
      return (
        <svg width="30" height="30" viewBox="0 0 30 30">
          <rect x="7" y="5" width="16" height="20" rx="2" {...common} strokeWidth={2.5} />
          <path d="M11 5 V3 H19 V5" {...common} strokeWidth={2.5} />
          <path d="M11 12 H19 M11 16 H16" {...common} strokeWidth={2} />
        </svg>
      )
    case 2:
      return (
        <svg width="30" height="30" viewBox="0 0 30 30">
          <rect x="3" y="6" width="14" height="14" rx="1" {...common} strokeWidth={2.5} />
          <rect x="13" y="10" width="14" height="14" rx="1" {...common} strokeWidth={2.5} />
        </svg>
      )
    case 3:
      return (
        <svg width="30" height="30" viewBox="0 0 30 30">
          <path d="M5 10 H25" {...common} strokeWidth={2.5} />
          <rect x="15" y="7" width="6" height="6" rx="1" fill={color} fillOpacity={0.3} stroke={color} strokeWidth={2} />
          <path d="M5 20 H25" {...common} strokeWidth={2.5} />
          <rect x="9" y="17" width="6" height="6" rx="1" fill={color} fillOpacity={0.3} stroke={color} strokeWidth={2} />
        </svg>
      )
    case 4:
      return (
        <svg width="30" height="30" viewBox="0 0 30 30">
          <path d="M4 6 H26 L19 16 V24 H11 V16 Z" {...common} strokeWidth={2.5} />
        </svg>
      )
    default:
      return null
  }
}

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="5" y="5" width="8" height="8" rx="1" />
      <path d="M3 11 V3 H11" />
    </svg>
  )
}

function PixelStar({ className }: { className?: string }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" className={className}>
      <rect x="5" y="0" width="2" height="2" fill="currentColor" />
      <rect x="3" y="2" width="6" height="2" fill="currentColor" />
      <rect x="0" y="4" width="12" height="4" fill="currentColor" />
      <rect x="3" y="8" width="6" height="2" fill="currentColor" />
      <rect x="5" y="10" width="2" height="2" fill="currentColor" />
    </svg>
  )
}

export default function RetroArcadeTheme({ onNavigate }: InfographicThemeProps) {
  return (
    <div className="arcade-bg rounded-lg p-6 pb-8 border-4 border-violet-400">
      {/* Game header */}
      <div className="mb-6 flex items-center gap-3">
        <PixelStar className="text-amber-400" />
        <span className="font-mono uppercase tracking-widest text-violet-600 font-bold text-lg">
          Select Stage
        </span>
        <PixelStar className="text-amber-400" />
        <div className="flex-1" />
        <span className="font-mono text-xs text-violet-400 uppercase">Player 1</span>
      </div>

      {/* Workflow stages */}
      <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
        {WORKFLOW_STEPS.map((step, i) => (
          <div key={step.pageKey} className="flex items-center">
            <button
              onClick={() => onNavigate?.(step.pageKey)}
              className={`
                relative bg-white border-4 ${STAGE_COLORS[i].border} rounded-lg
                px-4 py-4 w-36 text-left cursor-pointer
                transition-all duration-150
                hover:scale-105 hover:${STAGE_COLORS[i].shadow}
                group
              `}
            >
              <div className="flex items-center justify-between mb-2">
                <ArcadeIcon step={i} color={STAGE_COLORS[i].stroke} />
                <span className={`font-mono uppercase text-[10px] font-bold ${STAGE_COLORS[i].text} opacity-70`}>
                  LVL {i + 1}
                </span>
              </div>
              <div className={`font-bold text-base ${STAGE_COLORS[i].text}`}>{step.title}</div>
              <div className="text-xs text-gray-500 mt-0.5 leading-snug">{step.subtitle}</div>
            </button>

            {/* Chunky arrow connector */}
            {i < WORKFLOW_STEPS.length - 1 && (
              <span className={`font-mono font-bold text-lg mx-1 ${STAGE_COLORS[i].text} opacity-50`}>
                &gt;&gt;
              </span>
            )}
          </div>
        ))}
      </div>

      {/* CLI — Command Input panel */}
      <div className="max-w-2xl mx-auto mb-8">
        <div className="bg-white border-4 border-violet-400 rounded-lg p-5">
          <div className="mb-4 flex items-center gap-2">
            <span className="font-mono uppercase tracking-wider font-bold text-violet-600 text-sm">
              Command Input
            </span>
            <div className="flex-1 border-b-2 border-violet-200" />
          </div>

          <div className="space-y-3">
            {CLI_COMMANDS.map((cmd, i) => (
              <div key={i} className="flex items-start gap-2 group">
                <span className="font-mono text-violet-400 font-bold text-sm mt-0.5">&gt;</span>
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-sm text-gray-800 font-semibold break-all">
                    {cmd.command}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 pl-2">{cmd.description}</div>
                </div>
                <button
                  onClick={() => navigator.clipboard?.writeText(cmd.command)}
                  className="mt-0.5 p-1 rounded text-gray-300 hover:text-violet-600 hover:bg-violet-50 transition-colors cursor-pointer flex-shrink-0"
                  title="Copy command"
                >
                  <CopyIcon />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tips — Power-up hints */}
      <div className="max-w-xl mx-auto">
        <div className="mb-3 flex items-center gap-2">
          <PixelStar className="text-amber-400" />
          <span className="font-mono uppercase tracking-wider font-bold text-violet-600 text-sm">
            Power-Ups
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {QUICK_TIPS.map((tip, i) => (
            <button
              key={tip.pageKey}
              onClick={() => onNavigate?.(tip.pageKey)}
              className={`
                ${HINT_COLORS[i].bg} border-l-4 ${HINT_COLORS[i].border}
                rounded-lg p-3 text-left cursor-pointer
                hover:shadow-md hover:scale-[1.02] transition-all duration-150
              `}
            >
              <div className={`font-mono uppercase text-[10px] font-bold ${HINT_COLORS[i].label} mb-1`}>
                Hint {i + 1}
              </div>
              <span className="font-bold text-gray-700 text-sm">{tip.label}: </span>
              <span className="text-gray-600 text-xs leading-snug">{tip.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
