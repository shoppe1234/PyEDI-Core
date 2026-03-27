import { InfographicThemeProps, WORKFLOW_STEPS, CLI_COMMANDS, QUICK_TIPS } from './types'

const NOTE_COLORS = ['bg-yellow-200', 'bg-blue-200', 'bg-green-200', 'bg-orange-200', 'bg-pink-200']
const NOTE_ROTATIONS = ['-rotate-2', 'rotate-[2.5deg]', '-rotate-[1.5deg]', 'rotate-3', '-rotate-[2.8deg]']
const PIN_COLORS = ['#dc2626', '#2563eb', '#16a34a', '#ea580c', '#db2777']
const YARN_COLOR = '#92400e'

const TIP_COLORS = ['bg-yellow-100', 'bg-pink-100', 'bg-green-100', 'bg-blue-100']
const TIP_ROTATIONS_LIST = ['rotate-[1.5deg]', '-rotate-2', 'rotate-[2.2deg]', '-rotate-[1.8deg]']

function Pushpin({ color }: { color: string }) {
  return (
    <svg width="20" height="24" viewBox="0 0 20 24" className="absolute -top-2 left-1/2 -translate-x-1/2 z-10">
      <circle cx="10" cy="8" r="5" fill={color} stroke={color} strokeWidth="1" opacity="0.9" />
      <ellipse cx="10" cy="6" rx="2" ry="1.5" fill="white" opacity="0.35" />
      <line x1="10" y1="13" x2="10" y2="22" stroke="#78716c" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function PaperClip() {
  return (
    <svg width="24" height="48" viewBox="0 0 24 48" className="absolute -top-3 right-4 z-10" style={{ filter: 'drop-shadow(1px 1px 1px rgba(0,0,0,0.15))' }}>
      <path
        d="M8 4 V36 C8 42 16 42 16 36 V10 C16 6 8 6 8 10 V32"
        fill="none"
        stroke="#a8a29e"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="5" y="5" width="8" height="8" rx="1" />
      <path d="M3 11 V3 H11" />
    </svg>
  )
}

export default function StickyNotesTheme({ onNavigate }: InfographicThemeProps) {
  return (
    <div className="cork-bg rounded-lg p-6 pb-8 border-2 border-amber-800/30 shadow-inner relative overflow-hidden">
      {/* Header — pinned label */}
      <div className="mb-8 flex items-center gap-3">
        <div className="relative inline-block">
          <span className="text-xl font-extrabold text-amber-900 tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
            Case Board: PyEDI Workflow
          </span>
          <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-amber-800/20" />
        </div>
      </div>

      {/* Workflow sticky notes with yarn connections */}
      <div className="relative mb-10">
        {/* Yarn SVG layer behind notes */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none z-0"
          viewBox="0 0 900 160"
          preserveAspectRatio="none"
        >
          {[0, 1, 2, 3].map((i) => {
            const x1 = 90 + i * 180
            const x2 = 90 + (i + 1) * 180
            const droopY = 130 + (i % 2 === 0 ? 20 : 10)
            return (
              <path
                key={i}
                d={`M${x1} 60 Q${(x1 + x2) / 2} ${droopY}, ${x2} 60`}
                fill="none"
                stroke={YARN_COLOR}
                strokeWidth="2"
                strokeLinecap="round"
                opacity="0.5"
                strokeDasharray="6 4"
              />
            )
          })}
        </svg>

        <div className="flex flex-wrap items-start justify-center gap-4 relative z-10">
          {WORKFLOW_STEPS.map((step, i) => (
            <button
              key={step.pageKey}
              onClick={() => onNavigate?.(step.pageKey)}
              className={`
                relative ${NOTE_COLORS[i]} ${NOTE_ROTATIONS[i]}
                w-36 p-4 pt-6 text-left cursor-pointer shadow-md
                transition-all duration-300
                hover:-translate-y-1 hover:shadow-lg hover:rotate-0
                rounded-sm
              `}
            >
              <Pushpin color={PIN_COLORS[i]} />
              <div className="text-amber-800/50 text-xs font-bold mb-1">{i + 1}.</div>
              <div className="font-bold text-gray-800 text-base leading-tight">{step.title}</div>
              <div className="text-gray-600 text-sm mt-1 leading-snug">{step.subtitle}</div>
              {/* Folded corner effect */}
              <div className="absolute bottom-0 right-0 w-4 h-4 bg-gradient-to-tl from-black/[0.06] to-transparent" />
            </button>
          ))}
        </div>
      </div>

      {/* CLI — manila index card */}
      <div className="relative max-w-2xl mx-auto mb-8 rotate-[0.5deg]">
        <PaperClip />
        <div
          className="bg-amber-50 rounded-sm shadow-md p-5 pt-6 border border-amber-200/60"
          style={{
            backgroundImage: 'repeating-linear-gradient(transparent, transparent 27px, rgba(147,197,253,0.18) 27px, rgba(147,197,253,0.18) 28px)',
            backgroundPositionY: '42px',
          }}
        >
          {/* Red margin line */}
          <div className="absolute top-0 bottom-0 left-10 w-px bg-red-300/30" />

          <div className="mb-4 pl-4">
            <span className="text-lg font-extrabold text-amber-900" style={{ fontFamily: 'Georgia, serif' }}>
              CLI Quick Reference
            </span>
          </div>

          <div className="space-y-3 pl-4">
            {CLI_COMMANDS.map((cmd, i) => (
              <div key={i} className="flex items-start gap-2 group">
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-sm font-semibold text-gray-800 break-all">
                    $ {cmd.command}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5 pl-3">{cmd.description}</div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(cmd.command) }}
                  className="mt-0.5 p-1 rounded text-amber-400 hover:text-amber-700 hover:bg-amber-100 transition-colors cursor-pointer flex-shrink-0"
                  title="Copy command"
                >
                  <CopyIcon />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tips — Post-it grid */}
      <div className="max-w-xl mx-auto">
        <div className="mb-3">
          <span className="text-base font-extrabold text-amber-800" style={{ fontFamily: 'Georgia, serif' }}>
            Quick Tips
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {QUICK_TIPS.map((tip, i) => (
            <button
              key={tip.pageKey}
              onClick={() => onNavigate?.(tip.pageKey)}
              className={`
                relative ${TIP_COLORS[i]} ${TIP_ROTATIONS_LIST[i]}
                rounded-sm p-3 pt-5 text-left cursor-pointer shadow-sm
                hover:shadow-md hover:-translate-y-0.5 transition-all duration-200
                ${i % 2 === 1 ? 'animate-float' : ''}
              `}
            >
              {/* Tape strip */}
              <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-10 h-3 bg-white/40 rotate-2 rounded-sm" />
              <div className="mt-1">
                <span className="font-bold text-gray-800 text-sm">{tip.label}: </span>
                <span className="text-gray-600 text-xs leading-snug">{tip.text}</span>
              </div>
              {/* Folded corner */}
              <div className="absolute bottom-0 right-0 w-3 h-3 bg-gradient-to-tl from-black/[0.05] to-transparent" />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
