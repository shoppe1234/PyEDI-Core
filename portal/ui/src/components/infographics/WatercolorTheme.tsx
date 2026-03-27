import type { InfographicThemeProps } from './types'
import { WORKFLOW_STEPS, CLI_COMMANDS, QUICK_TIPS } from './types'

const WASH_COLORS = [
  { bg: 'bg-rose-100/60', text: 'text-rose-700', dot: 'bg-rose-400', stroke: '#fb7185', shadow: 'shadow-[0_4px_14px_rgba(244,114,182,0.15)]', hoverShadow: 'hover:shadow-[0_8px_20px_rgba(244,114,182,0.25)]' },
  { bg: 'bg-teal-100/60', text: 'text-teal-700', dot: 'bg-teal-400', stroke: '#2dd4bf', shadow: 'shadow-[0_4px_14px_rgba(45,212,191,0.15)]', hoverShadow: 'hover:shadow-[0_8px_20px_rgba(45,212,191,0.25)]' },
  { bg: 'bg-amber-100/60', text: 'text-amber-700', dot: 'bg-amber-400', stroke: '#fbbf24', shadow: 'shadow-[0_4px_14px_rgba(251,191,36,0.15)]', hoverShadow: 'hover:shadow-[0_8px_20px_rgba(251,191,36,0.25)]' },
  { bg: 'bg-violet-100/60', text: 'text-violet-700', dot: 'bg-violet-400', stroke: '#a78bfa', shadow: 'shadow-[0_4px_14px_rgba(167,139,250,0.15)]', hoverShadow: 'hover:shadow-[0_8px_20px_rgba(167,139,250,0.25)]' },
  { bg: 'bg-emerald-100/60', text: 'text-emerald-700', dot: 'bg-emerald-400', stroke: '#34d399', shadow: 'shadow-[0_4px_14px_rgba(52,211,153,0.15)]', hoverShadow: 'hover:shadow-[0_8px_20px_rgba(52,211,153,0.25)]' },
]

const TIP_WASHES = ['bg-rose-50', 'bg-teal-50', 'bg-amber-50', 'bg-violet-50']
const TIP_TEXT = ['text-rose-700', 'text-teal-700', 'text-amber-700', 'text-violet-700']
const TIP_ROTATIONS = ['-rotate-[0.5deg]', 'rotate-[0.8deg]', 'rotate-[0.3deg]', '-rotate-[0.7deg]']

function WashIcon({ step, color }: { step: number; color: string }) {
  const common = { fill: 'none', stroke: color, strokeWidth: 2.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, opacity: 0.8 }
  switch (step) {
    case 0:
      return (
        <svg width="32" height="32" viewBox="0 0 32 32">
          <circle cx="16" cy="16" r="11" {...common} strokeWidth={2} />
          <path d="M11 16.5 L14.5 20 L22 12" {...common} />
        </svg>
      )
    case 1:
      return (
        <svg width="32" height="32" viewBox="0 0 32 32">
          <rect x="8" y="6" width="16" height="20" rx="3" {...common} strokeWidth={2} />
          <path d="M12 6 V5 C12 3.5 13 3 14 3 H18 C19 3 20 3.5 20 5 V6" {...common} strokeWidth={2} />
          <path d="M12 13 H20 M12 17 H17" {...common} strokeWidth={1.5} />
        </svg>
      )
    case 2:
      return (
        <svg width="32" height="32" viewBox="0 0 32 32">
          <rect x="5" y="7" width="14" height="14" rx="3" {...common} strokeWidth={2} />
          <rect x="13" y="11" width="14" height="14" rx="3" {...common} strokeWidth={2} />
        </svg>
      )
    case 3:
      return (
        <svg width="32" height="32" viewBox="0 0 32 32">
          <path d="M7 11 H25" {...common} strokeWidth={2} />
          <circle cx="18" cy="11" r="3" {...common} fill={color} fillOpacity={0.2} />
          <path d="M7 17 H25" {...common} strokeWidth={2} />
          <circle cx="12" cy="17" r="3" {...common} fill={color} fillOpacity={0.2} />
          <path d="M7 23 H25" {...common} strokeWidth={2} />
          <circle cx="21" cy="23" r="3" {...common} fill={color} fillOpacity={0.2} />
        </svg>
      )
    case 4:
      return (
        <svg width="32" height="32" viewBox="0 0 32 32">
          <path d="M6 7 H26 L19 17 V25 H13 V17 Z" {...common} strokeWidth={2} />
        </svg>
      )
    default:
      return null
  }
}

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="5" y="5" width="8" height="8" rx="1.5" />
      <path d="M3 11 V3 H11" />
    </svg>
  )
}

export default function WatercolorTheme({ onNavigate }: InfographicThemeProps) {
  return (
    <div className="watercolor-bg rounded-xl p-6 pb-8 border border-rose-200/40 relative overflow-hidden">
      {/* Background watercolor blobs */}
      <svg className="absolute top-0 right-0 w-64 h-64 pointer-events-none opacity-30" viewBox="0 0 200 200">
        <ellipse cx="140" cy="60" rx="80" ry="60" fill="#fecdd3" />
      </svg>
      <svg className="absolute bottom-0 left-0 w-56 h-56 pointer-events-none opacity-20" viewBox="0 0 200 200">
        <ellipse cx="60" cy="140" rx="70" ry="55" fill="#99f6e4" />
      </svg>

      {/* Section header */}
      <div className="relative mb-6">
        <span className="text-xl font-bold text-gray-700" style={{ fontFamily: 'Georgia, serif' }}>
          Portal Workflow
        </span>
        <div className="mt-1 h-0.5 w-24 bg-gradient-to-r from-rose-300 via-teal-300 to-amber-300 rounded-full" />
      </div>

      {/* Workflow steps */}
      <div className="relative flex flex-wrap items-center justify-center gap-3 mb-10">
        {WORKFLOW_STEPS.map((step, i) => (
          <div key={step.pageKey} className="flex items-center">
            <button
              onClick={() => onNavigate?.(step.pageKey)}
              className={`
                relative ${WASH_COLORS[i].bg} rounded-2xl
                px-5 py-4 w-40 text-left cursor-pointer
                ${WASH_COLORS[i].shadow} ${WASH_COLORS[i].hoverShadow}
                transition-all duration-300
                hover:-translate-y-1
                group
              `}
            >
              {/* Step number dot */}
              <div className={`absolute -top-2 -left-1 w-6 h-6 rounded-full ${WASH_COLORS[i].dot} flex items-center justify-center opacity-80`}>
                <span className="text-white text-[10px] font-bold">{i + 1}</span>
              </div>
              <div className="mb-2">
                <WashIcon step={i} color={WASH_COLORS[i].stroke} />
              </div>
              <div className={`font-bold text-base ${WASH_COLORS[i].text}`}>{step.title}</div>
              <div className="text-xs text-gray-500 mt-0.5 leading-snug">{step.subtitle}</div>
            </button>

            {/* Soft curved connector */}
            {i < WORKFLOW_STEPS.length - 1 && (
              <svg width="32" height="20" viewBox="0 0 32 20" className="mx-1 flex-shrink-0 opacity-40">
                <path
                  d={`M2 10 Q16 ${i % 2 === 0 ? 2 : 18}, 30 10`}
                  fill="none"
                  stroke={WASH_COLORS[i].stroke}
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            )}
          </div>
        ))}
      </div>

      {/* CLI Commands */}
      <div className="relative max-w-2xl mx-auto mb-8">
        <div className="bg-white/70 rounded-xl shadow-sm p-5 border border-gray-100 overflow-hidden">
          {/* Left accent stripe */}
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-rose-300 via-teal-300 to-violet-300 rounded-l-xl" />

          <div className="mb-4 pl-3">
            <span className="text-lg font-bold text-gray-700" style={{ fontFamily: 'Georgia, serif' }}>
              CLI Commands
            </span>
          </div>

          <div className="space-y-3 pl-3">
            {CLI_COMMANDS.map((cmd, i) => (
              <div key={i} className="flex items-start gap-2 group">
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-sm text-gray-700 break-all">
                    $ {cmd.command}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 pl-3">{cmd.description}</div>
                </div>
                <button
                  onClick={() => navigator.clipboard?.writeText(cmd.command)}
                  className="mt-0.5 p-1 rounded text-gray-300 hover:text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer flex-shrink-0"
                  title="Copy command"
                >
                  <CopyIcon />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Tips */}
      <div className="relative max-w-xl mx-auto">
        <div className="mb-3">
          <span className="text-base font-bold text-gray-600" style={{ fontFamily: 'Georgia, serif' }}>
            Quick Tips
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {QUICK_TIPS.map((tip, i) => (
            <button
              key={tip.pageKey}
              onClick={() => onNavigate?.(tip.pageKey)}
              className={`
                ${TIP_WASHES[i]} ${TIP_ROTATIONS[i]} rounded-xl p-3.5 text-left cursor-pointer
                shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200
              `}
            >
              <span className={`font-bold text-sm ${TIP_TEXT[i]}`}>{tip.label}: </span>
              <span className="text-gray-600 text-xs leading-snug">{tip.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
