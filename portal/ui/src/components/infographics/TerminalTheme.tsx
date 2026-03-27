import { InfographicThemeProps, WORKFLOW_STEPS, CLI_COMMANDS, QUICK_TIPS } from './types'

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <rect x="4.5" y="4.5" width="7" height="7" rx="1" />
      <path d="M2.5 9.5 V2.5 H9.5" />
    </svg>
  )
}

export default function TerminalTheme({ onNavigate }: InfographicThemeProps) {
  return (
    <div
      className="relative bg-gray-950 rounded-lg p-6 border border-green-500/30 scanline overflow-hidden"
      style={{ boxShadow: '0 0 30px rgba(34,197,94,0.1)' }}
    >
      {/* macOS-style title bar */}
      <div className="flex items-center gap-2 mb-5 pb-3 border-b border-green-500/15">
        <div className="w-3 h-3 rounded-full bg-red-500/70" />
        <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
        <div className="w-3 h-3 rounded-full bg-green-500/70" />
        <span className="ml-3 font-mono text-xs text-green-500/50">pyedi@portal:~/dashboard $</span>
      </div>

      {/* Boot header */}
      <div className="font-mono text-green-500/40 text-xs mb-1">$ cat /proc/pyedi/workflow</div>
      <div className="font-mono text-green-400 text-sm font-bold mb-4 tracking-wider">
        ╔══════════════════════════════════════╗
        <br />
        ║&nbsp;&nbsp;PYEDI WORKFLOW &mdash; PROCESS MAP&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║
        <br />
        ╚══════════════════════════════════════╝
      </div>

      {/* Workflow steps */}
      <div className="flex flex-wrap items-center justify-center gap-0 mb-8">
        {WORKFLOW_STEPS.map((step, i) => (
          <div key={step.pageKey} className="flex items-center">
            <button
              onClick={() => onNavigate?.(step.pageKey)}
              className="
                border border-green-500/40 font-mono
                px-3 py-3 w-32 text-left cursor-pointer
                transition-all duration-200
                hover:bg-green-950 hover:border-green-400
                group
              "
            >
              <div className="text-green-500 text-xs mb-1 font-bold">[{i + 1}]</div>
              <div className="text-green-400 font-medium text-sm uppercase tracking-wide">{step.title}</div>
              <div className="text-green-600 text-xs mt-1 leading-snug">{step.subtitle}</div>
            </button>

            {i < WORKFLOW_STEPS.length - 1 && (
              <span className="font-mono text-green-500 text-sm mx-1 flex-shrink-0">━━►</span>
            )}
          </div>
        ))}
      </div>

      {/* CLI section — native terminal */}
      <div className="mb-8">
        <div className="font-mono text-green-500/40 text-xs mb-3">$ man pyedi --commands</div>
        <div className="space-y-3 pl-2">
          {CLI_COMMANDS.map((cmd, i) => (
            <div key={i} className="group flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-mono text-xs text-green-700/70 mb-0.5"># {cmd.description}</div>
                <div className="font-mono text-sm">
                  <span className="text-green-600">$ </span>
                  <span className="text-green-400">{cmd.command}</span>
                  {i === CLI_COMMANDS.length - 1 && (
                    <span className="text-green-400 animate-cursor ml-0.5">█</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => navigator.clipboard?.writeText(cmd.command)}
                className="mt-2 p-1 rounded text-green-700/40 hover:text-green-400 hover:bg-green-500/10 transition-colors cursor-pointer flex-shrink-0"
                title="Copy command"
              >
                <CopyIcon />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Tips — log output */}
      <div>
        <div className="font-mono text-green-500/40 text-xs mb-3">$ tail -f /var/log/pyedi/tips.log</div>
        <div className="space-y-1.5 pl-2">
          {QUICK_TIPS.map((tip, i) => (
            <button
              key={tip.pageKey}
              onClick={() => onNavigate?.(tip.pageKey)}
              className="
                w-full text-left font-mono text-xs cursor-pointer
                hover:underline transition-colors block
              "
            >
              <span className="text-green-700/50">00:0{i + 1} {'>'} </span>
              <span className="text-cyan-400">[INFO]</span>
              {' '}
              <span className="text-yellow-400">[{tip.label}]</span>
              {' '}
              <span className="text-green-300/80">{tip.text}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Status bar */}
      <div className="mt-6 pt-3 border-t border-green-500/15 flex justify-between font-mono text-[10px] text-green-600/40">
        <span>PID 4201 | MEM 24MB | CPU 0.2%</span>
        <span>pyedi v2.1.0 | portal session active</span>
      </div>
    </div>
  )
}
