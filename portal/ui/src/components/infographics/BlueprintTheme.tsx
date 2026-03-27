import { InfographicThemeProps, WORKFLOW_STEPS, CLI_COMMANDS, QUICK_TIPS } from './types'

function BlueprintIcon({ step }: { step: number }) {
  const common = { fill: 'none', stroke: '#22d3ee', strokeWidth: 1.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (step) {
    case 0: // Validate — checkmark in circle
      return (
        <svg width="28" height="28" viewBox="0 0 28 28">
          <circle cx="14" cy="14" r="10" {...common} />
          <path d="M9 14.5 L12.5 18 L19 11" {...common} />
        </svg>
      )
    case 1: // Onboard — clipboard
      return (
        <svg width="28" height="28" viewBox="0 0 28 28">
          <rect x="7" y="5" width="14" height="18" rx="1.5" {...common} />
          <path d="M11 5 V4 C11 3 12 2.5 13 2.5 H15 C16 2.5 17 3 17 4 V5" {...common} />
          <path d="M11 12 H18 M11 15 H16 M11 18 H17" {...common} strokeWidth={1} />
        </svg>
      )
    case 2: // Compare — overlapping squares
      return (
        <svg width="28" height="28" viewBox="0 0 28 28">
          <rect x="4" y="6" width="13" height="13" rx="1.5" {...common} />
          <rect x="11" y="10" width="13" height="13" rx="1.5" {...common} />
          <path d="M8 13 L14 17" {...common} strokeWidth={1} />
        </svg>
      )
    case 3: // Rules — sliders
      return (
        <svg width="28" height="28" viewBox="0 0 28 28">
          <path d="M6 9 H22" {...common} strokeWidth={1} />
          <circle cx="16" cy="9" r="2.5" {...common} />
          <path d="M6 15 H22" {...common} strokeWidth={1} />
          <circle cx="11" cy="15" r="2.5" {...common} />
          <path d="M6 21 H22" {...common} strokeWidth={1} />
          <circle cx="18" cy="21" r="2.5" {...common} />
        </svg>
      )
    case 4: // Pipeline — funnel
      return (
        <svg width="28" height="28" viewBox="0 0 28 28">
          <path d="M5 6 H23 L17 15 V22 H11 V15 Z" {...common} />
          <path d="M9 9 H19" {...common} strokeWidth={1} strokeDasharray="2 2" />
        </svg>
      )
    default:
      return null
  }
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <rect x="4.5" y="4.5" width="7" height="7" rx="1" />
      <path d="M2.5 9.5 V2.5 H9.5" />
    </svg>
  )
}

function CornerMark({ position }: { position: 'tl' | 'tr' | 'bl' | 'br' }) {
  const size = 16
  const paths: Record<string, string> = {
    tl: `M0 ${size} V0 H${size}`,
    tr: `M${size - size} 0 H${size} V${size}`,
    bl: `M0 0 V${size} H${size}`,
    br: `M0 ${size} H${size} V0`,
  }
  const posClass: Record<string, string> = {
    tl: 'top-2 left-2',
    tr: 'top-2 right-2',
    bl: 'bottom-2 left-2',
    br: 'bottom-2 right-2',
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`absolute ${posClass[position]}`}
      fill="none"
      stroke="rgba(34,211,238,0.4)"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d={paths[position]} />
    </svg>
  )
}

export default function BlueprintTheme({ onNavigate }: InfographicThemeProps) {
  return (
    <div className="relative bg-indigo-950 blueprint-bg rounded-lg p-6 border border-cyan-500/30 overflow-hidden">
      {/* Corner registration marks */}
      <CornerMark position="tl" />
      <CornerMark position="tr" />
      <CornerMark position="bl" />
      <CornerMark position="br" />

      {/* Section header */}
      <div className="mb-6 flex items-center gap-3">
        <span className="font-mono text-cyan-300 text-sm uppercase tracking-widest">System Workflow</span>
        <div className="flex-1 h-px bg-cyan-500/20" />
        <span className="font-mono text-cyan-500/40 text-xs">REV 1.0</span>
      </div>

      {/* Dimension line above workflow */}
      <div className="mb-2 flex items-center px-4">
        <svg width="100%" height="12" viewBox="0 0 800 12" preserveAspectRatio="none" className="overflow-visible">
          {/* Endcaps and line */}
          <line x1="20" y1="2" x2="20" y2="10" stroke="rgba(34,211,238,0.3)" strokeWidth="1" />
          <line x1="20" y1="6" x2="780" y2="6" stroke="rgba(34,211,238,0.3)" strokeWidth="1" />
          <line x1="780" y1="2" x2="780" y2="10" stroke="rgba(34,211,238,0.3)" strokeWidth="1" />
          {/* Step markers */}
          {[0, 1, 2, 3, 4].map((i) => (
            <g key={i}>
              <line x1={20 + i * 190} y1="2" x2={20 + i * 190} y2="10" stroke="rgba(34,211,238,0.3)" strokeWidth="1" />
              <text x={20 + i * 190 + 8} y="5" fill="rgba(34,211,238,0.3)" fontSize="7" fontFamily="monospace">
                {`STEP ${i + 1}`}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* Workflow steps with connector lines */}
      <div className="flex flex-wrap items-stretch justify-center gap-0 mb-10">
        {WORKFLOW_STEPS.map((step, i) => (
          <div key={step.pageKey} className="flex items-center">
            <button
              onClick={() => onNavigate?.(step.pageKey)}
              className="
                relative border border-cyan-400/50 font-mono
                px-4 py-4 w-36 text-left cursor-pointer
                transition-all duration-200
                hover:border-cyan-300 hover:bg-cyan-950/30
                group
              "
            >
              {/* Step number circle */}
              <div className="absolute -top-3 -left-3 w-6 h-6 rounded-full border border-cyan-400/60 bg-indigo-950 flex items-center justify-center">
                <span className="text-cyan-400 text-[10px] font-mono font-bold">{i + 1}</span>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <BlueprintIcon step={i} />
              </div>
              <div className="text-white font-medium text-sm">{step.title}</div>
              <div className="text-cyan-300/70 text-xs mt-0.5">{step.subtitle}</div>
            </button>

            {/* Arrow connector */}
            {i < WORKFLOW_STEPS.length - 1 && (
              <svg width="28" height="16" viewBox="0 0 28 16" className="flex-shrink-0 mx-0.5">
                <line x1="2" y1="8" x2="20" y2="8" stroke="rgba(34,211,238,0.5)" strokeWidth="1" />
                <polygon points="19,4 27,8 19,12" fill="rgba(34,211,238,0.5)" />
              </svg>
            )}
          </div>
        ))}
      </div>

      {/* CLI specification table */}
      <div className="max-w-2xl mx-auto mb-8">
        <div className="mb-3 flex items-center gap-3">
          <span className="font-mono text-cyan-300 text-sm uppercase tracking-widest">Specification Table</span>
          <div className="flex-1 h-px bg-cyan-500/20" />
        </div>

        <table className="w-full border-collapse font-mono">
          <thead>
            <tr className="border-b border-cyan-500/20">
              <th className="text-left text-cyan-300 text-xs uppercase tracking-wider py-2 px-3 w-3/5">Command</th>
              <th className="text-left text-cyan-300 text-xs uppercase tracking-wider py-2 px-3">Function</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {CLI_COMMANDS.map((cmd, i) => (
              <tr key={i} className="border-b border-cyan-500/10 group hover:bg-cyan-950/20 transition-colors">
                <td className="text-white text-sm py-2.5 px-3 break-all">$ {cmd.command}</td>
                <td className="text-cyan-200/70 text-xs py-2.5 px-3">{cmd.description}</td>
                <td className="py-2.5 px-1">
                  <button
                    onClick={() => navigator.clipboard?.writeText(cmd.command)}
                    className="p-1 rounded text-cyan-500/30 hover:text-cyan-300 hover:bg-cyan-500/10 transition-colors cursor-pointer"
                    title="Copy command"
                  >
                    <CopyIcon />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Notes section */}
      <div className="max-w-2xl mx-auto">
        <div className="mb-3 flex items-center gap-3">
          <span className="font-mono text-cyan-300 text-sm uppercase tracking-widest">Notes</span>
          <div className="flex-1 h-px bg-cyan-500/20" />
        </div>

        <div className="space-y-2">
          {QUICK_TIPS.map((tip, i) => (
            <button
              key={tip.pageKey}
              onClick={() => onNavigate?.(tip.pageKey)}
              className="
                w-full text-left pl-4 py-2 border-l-2 border-cyan-400/40
                cursor-pointer hover:border-cyan-300 hover:bg-cyan-950/20 transition-all
              "
            >
              <span className="font-mono text-cyan-400/60 text-xs mr-2">NOTE {i + 1}:</span>
              <span className="font-mono text-cyan-300 font-medium text-sm">{tip.label}</span>
              <span className="font-mono text-cyan-100/80 text-xs ml-1.5">{tip.text}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Title block — bottom right */}
      <div className="mt-6 flex justify-end">
        <div className="border border-cyan-500/30 px-4 py-2 font-mono">
          <div className="text-cyan-300 text-xs">PyEDI-Core &mdash; System Workflow</div>
          <div className="text-cyan-500/40 text-[10px] mt-0.5">DWG NO. PYE-001 &bull; SCALE: 1:1</div>
        </div>
      </div>
    </div>
  )
}
