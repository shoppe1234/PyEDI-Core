import type { InfographicThemeProps } from './types'
import { WORKFLOW_STEPS, CLI_COMMANDS, QUICK_TIPS } from './types'

const STEP_COLORS = [
  { border: 'border-blue-500', text: 'text-blue-500', bg: 'bg-blue-500', stroke: '#3b82f6', hoverBorder: 'hover:border-blue-500' },
  { border: 'border-indigo-500', text: 'text-indigo-500', bg: 'bg-indigo-500', stroke: '#6366f1', hoverBorder: 'hover:border-indigo-500' },
  { border: 'border-purple-500', text: 'text-purple-500', bg: 'bg-purple-500', stroke: '#a855f7', hoverBorder: 'hover:border-purple-500' },
  { border: 'border-amber-500', text: 'text-amber-500', bg: 'bg-amber-500', stroke: '#f59e0b', hoverBorder: 'hover:border-amber-500' },
  { border: 'border-green-500', text: 'text-green-500', bg: 'bg-green-500', stroke: '#22c55e', hoverBorder: 'hover:border-green-500' },
]

const ROTATIONS = ['-rotate-1', 'rotate-[0.5deg]', '-rotate-[0.5deg]', 'rotate-1', '-rotate-1']

const RADII = [
  'rounded-tl-xl rounded-tr-sm rounded-bl-md rounded-br-2xl',
  'rounded-tl-sm rounded-tr-2xl rounded-bl-xl rounded-br-md',
  'rounded-tl-2xl rounded-tr-md rounded-bl-sm rounded-br-xl',
  'rounded-tl-md rounded-tr-xl rounded-bl-2xl rounded-br-sm',
  'rounded-tl-xl rounded-tr-sm rounded-bl-2xl rounded-br-md',
]

const CLI_MARKER_COLORS = ['text-blue-600', 'text-purple-600', 'text-green-600']

const TIP_BG = ['bg-yellow-50', 'bg-blue-50', 'bg-green-50', 'bg-pink-50']
const TIP_DOT = ['bg-yellow-400', 'bg-blue-400', 'bg-green-400', 'bg-pink-400']
const TIP_ROTATIONS = ['rotate-[0.8deg]', '-rotate-[0.6deg]', '-rotate-[1deg]', 'rotate-[0.5deg]']

function SketchIcon({ step, color }: { step: number; color: string }) {
  const common = { fill: 'none', stroke: color, strokeWidth: 2.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (step) {
    case 0: // Validate — checkmark in circle
      return (
        <svg width="36" height="36" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="13" {...common} strokeDasharray="3 2" />
          <path d="M12 18.5 L16.5 23 L25 13.5" {...common} />
        </svg>
      )
    case 1: // Onboard — clipboard
      return (
        <svg width="36" height="36" viewBox="0 0 36 36">
          <rect x="9" y="7" width="18" height="23" rx="2" {...common} />
          <path d="M14 7 V5.5 C14 4.5 15 4 16 4 H20 C21 4 22 4.5 22 5.5 V7" {...common} />
          <path d="M14 15 H23 M14 19 H20 M14 23 H22" {...common} strokeWidth={2} />
        </svg>
      )
    case 2: // Compare — overlapping squares
      return (
        <svg width="36" height="36" viewBox="0 0 36 36">
          <rect x="6" y="8" width="16" height="16" rx="2" {...common} />
          <rect x="14" y="13" width="16" height="16" rx="2" {...common} />
          <path d="M11 16 L17 21" {...common} strokeWidth={2} />
        </svg>
      )
    case 3: // Rules — sliders
      return (
        <svg width="36" height="36" viewBox="0 0 36 36">
          <path d="M8 12 H28" {...common} strokeWidth={2} />
          <circle cx="20" cy="12" r="3" {...common} fill={color} fillOpacity={0.2} />
          <path d="M8 19 H28" {...common} strokeWidth={2} />
          <circle cx="14" cy="19" r="3" {...common} fill={color} fillOpacity={0.2} />
          <path d="M8 26 H28" {...common} strokeWidth={2} />
          <circle cx="23" cy="26" r="3" {...common} fill={color} fillOpacity={0.2} />
        </svg>
      )
    case 4: // Pipeline — funnel
      return (
        <svg width="36" height="36" viewBox="0 0 36 36">
          <path d="M7 8 H29 L21 20 V28 H15 V20 Z" {...common} />
          <path d="M12 12 H24" {...common} strokeWidth={1.5} strokeDasharray="2 3" />
        </svg>
      )
    default:
      return null
  }
}

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="5" y="5" width="8" height="8" rx="1" />
      <path d="M3 11 V3 H11" />
    </svg>
  )
}

export default function WhiteboardTheme({ onNavigate }: InfographicThemeProps) {
  return (
    <div className="sketch-bg rounded-xl p-6 pb-8 border-2 border-dashed border-gray-300">
      {/* Section label — hand-drawn style */}
      <div className="mb-6 flex items-center gap-3">
        <span className="text-xl font-extrabold text-gray-700 tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
          Portal Workflow
        </span>
        <svg width="80" height="8" viewBox="0 0 80 8" className="mt-1">
          <path d="M0 4 Q10 0, 20 4 T40 4 T60 4 T80 4" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>

      {/* Workflow steps with arrows */}
      <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
        {WORKFLOW_STEPS.map((step, i) => (
          <div key={step.pageKey} className="flex items-center">
            <button
              onClick={() => onNavigate?.(step.pageKey)}
              className={`
                relative bg-white border-2 border-dashed ${STEP_COLORS[i].border} ${RADII[i]} ${ROTATIONS[i]}
                px-5 py-4 w-40 text-left cursor-pointer
                transition-all duration-200
                hover:scale-105 hover:border-solid hover:shadow-lg
                group
              `}
            >
              <div className="flex items-center gap-2 mb-1">
                <SketchIcon step={i} color={STEP_COLORS[i].stroke} />
                <span className={`text-xs font-mono ${STEP_COLORS[i].text} opacity-60`}>#{i + 1}</span>
              </div>
              <div className={`font-bold text-base ${STEP_COLORS[i].text}`}>{step.title}</div>
              <div className="text-xs text-gray-500 mt-0.5 leading-snug">{step.subtitle}</div>
            </button>

            {/* Dashed arrow between cards */}
            {i < WORKFLOW_STEPS.length - 1 && (
              <svg width="36" height="24" viewBox="0 0 36 24" className="mx-1 flex-shrink-0">
                <path
                  d={`M2 ${12 + (i % 2 === 0 ? -2 : 2)} C12 ${12 + (i % 2 === 0 ? 4 : -4)}, 24 ${12 + (i % 2 === 0 ? -3 : 3)}, 30 12`}
                  fill="none"
                  stroke={STEP_COLORS[i].stroke}
                  strokeWidth="2"
                  strokeDasharray="8 4"
                  strokeLinecap="round"
                  className="animate-draw"
                  style={{ strokeDashoffset: 1000 }}
                />
                <polygon
                  points="28,8 34,12 28,16"
                  fill={STEP_COLORS[i].stroke}
                  opacity={0.7}
                />
              </svg>
            )}
          </div>
        ))}
      </div>

      {/* CLI Commands panel */}
      <div className="bg-white border-[3px] border-dashed border-gray-400 rounded-lg p-5 mb-8 rotate-[0.3deg] max-w-2xl mx-auto">
        <div className="mb-4">
          <span className="text-lg font-extrabold text-gray-700 tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
            CLI Commands
          </span>
          <svg width="120" height="8" viewBox="0 0 120 8" className="block mt-0.5">
            <path d="M0 5 Q15 1, 30 5 T60 5 T90 5 T120 5" fill="none" stroke="#6b7280" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        </div>

        <div className="space-y-3">
          {CLI_COMMANDS.map((cmd, i) => (
            <div key={i} className="flex items-start gap-2 group">
              <div className="flex-1 min-w-0">
                <div className={`font-mono text-sm font-semibold ${CLI_MARKER_COLORS[i]} break-all`}>
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

      {/* Quick Tips — sticky-note style cards */}
      <div className="max-w-xl mx-auto">
        <div className="mb-3">
          <span className="text-base font-extrabold text-gray-600" style={{ fontFamily: 'Georgia, serif' }}>
            Quick Tips
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {QUICK_TIPS.map((tip, i) => (
            <button
              key={tip.pageKey}
              onClick={() => onNavigate?.(tip.pageKey)}
              className={`
                ${TIP_BG[i]} ${TIP_ROTATIONS[i]} rounded-md p-3 text-left cursor-pointer
                shadow-sm hover:shadow-md hover:scale-[1.03] transition-all duration-200 border border-transparent hover:border-gray-200
                relative
              `}
            >
              <div className={`absolute top-2 left-2 w-2.5 h-2.5 rounded-full ${TIP_DOT[i]}`} />
              <div className="pl-5">
                <span className="font-bold text-gray-700 text-sm">{tip.label}: </span>
                <span className="text-gray-600 text-xs leading-snug">{tip.text}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
