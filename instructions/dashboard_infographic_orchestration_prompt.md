# Dashboard Infographic Renderings — Orchestration Prompt

**Purpose:** Build 4 visually distinct infographic rendering themes for the PyEDI Portal Dashboard that fill the white space below the stats grid and recent-processing table. Each rendering explains how PyEDI works from both a portal and CLI perspective. A randomizer selects one theme per page load, giving the end user a fresh experience. Each rendering must be tested individually.

**Design spec:** This file (read fully before starting).
**Coding standards:** `CLAUDE.md`
**Existing portal:** `portal/api/` (FastAPI backend), `portal/ui/` (React + Tailwind frontend)
**Current Dashboard:** `portal/ui/src/pages/Dashboard.tsx` — 48 lines, StatCard grid + recent table
**App shell:** `portal/ui/src/App.tsx` — sidebar nav, page routing via useState

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Match existing patterns** — follow conventions in the codebase exactly. Read neighbor files before writing new ones.
8. **Use the frontend-design skill** — invoke `/frontend-design` for building each theme component. Each theme must be visually distinctive and production-grade — not generic. The 4 themes must look dramatically different from each other.
9. **Server is live** — the frontend runs on 5173. Verify UI in the browser throughout.
10. **No external dependencies** — all 4 themes must use only React + Tailwind CSS + inline SVG. Do not install charting libraries, icon packs, or animation frameworks.

---

## Pre-Flight

Before starting any task, verify the development environment:

```bash
# Start frontend (if not already running)
cd ~/VS/pycoreEdi/portal/ui
npm run dev &

# Verify TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit

# Read current Dashboard to understand baseline
cat portal/ui/src/pages/Dashboard.tsx

# Read App.tsx to understand routing pattern
cat portal/ui/src/App.tsx

# Read index.css to understand Tailwind setup
cat portal/ui/src/index.css

# Confirm components directory doesn't exist yet (or check what's there)
ls portal/ui/src/components/ 2>/dev/null || echo "No components dir yet"
```

If anything fails at baseline, **stop and fix before proceeding**.

---

## Shared Content Specification

All 4 themes render the same information, just with different visual treatments:

### Portal Workflow (5 steps, each clickable via `onNavigate`)

| Step | Page Key | Title | Subtitle |
|------|----------|-------|----------|
| 1 | `validate` | Validate | Compile your DSL schema |
| 2 | `onboard` | Onboard | Register partner & configure rules |
| 3 | `compare` | Compare | Run field-by-field comparisons |
| 4 | `rules` | Rules | Manage severity tiers (hard/soft/ignore) |
| 5 | `pipeline` | Pipeline | View processing results & status |

### CLI Commands (3 commands)

| Command | Description |
|---------|-------------|
| `python -m pycoreedi validate <schema.dsl>` | Compile & validate a DSL schema file |
| `python -m pycoreedi run <config.yaml>` | Run the full processing pipeline |
| `python -m pycoreedi compare <source> <target>` | Compare two files field-by-field |

### Quick Tips (4 tips, each clickable via `onNavigate`)

| Tip | Page Key |
|-----|----------|
| **Start Here:** Upload your DSL schema on the Validate page to compile it into YAML | `validate` |
| **New Partner?** Use the Onboard wizard to register and configure in 3 steps | `onboard` |
| **Pro Tip:** Set up rule tiers (hard/soft/ignore) before running comparisons | `rules` |
| **Check Results:** The Pipeline page shows all processing runs with status tracking | `pipeline` |

---

## Shared TypeScript Interface

All themes must implement this interface:

```typescript
interface InfographicThemeProps {
  onNavigate?: (page: string) => void
}
```

Each theme is a default-exported React component accepting `InfographicThemeProps`.

---

# PHASE 1: Foundation — CSS Utilities + Directory Structure + Shared Types

> **Prerequisite:** Pre-flight green.
> **Deliverables:** CSS animation classes, component directory, shared types file, and barrel export stub.

---

## Task 1.1 — Add CSS Utilities to index.css

**Investigate:**
```bash
cat portal/ui/src/index.css
```

**Execute:**

Add the following CSS after `@import "tailwindcss"` in `portal/ui/src/index.css`:

```css
/* Infographic theme utilities */

/* Whiteboard dot-grid background */
.sketch-bg {
  background-image: radial-gradient(circle, #d1d5db 1px, transparent 1px);
  background-size: 20px 20px;
}

/* Blueprint grid background */
.blueprint-bg {
  background-image:
    linear-gradient(rgba(103, 232, 249, 0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(103, 232, 249, 0.1) 1px, transparent 1px);
  background-size: 24px 24px;
}

/* Cork texture background */
.cork-bg {
  background-image:
    radial-gradient(ellipse at 20% 50%, rgba(180, 140, 100, 0.15) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(160, 120, 80, 0.1) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, rgba(170, 130, 90, 0.12) 0%, transparent 50%);
  background-color: #f5e6d3;
}

/* Terminal scanline overlay */
.scanline::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
  pointer-events: none;
}

/* SVG draw-on animation */
@keyframes sketch-draw {
  from { stroke-dashoffset: 1000; }
  to { stroke-dashoffset: 0; }
}

.animate-draw {
  animation: sketch-draw 1.5s ease-out forwards;
}

/* Typing cursor animation */
@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.animate-cursor {
  animation: blink-cursor 1s step-end infinite;
}

/* Gentle float for sticky notes */
@keyframes gentle-float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-3px); }
}

.animate-float {
  animation: gentle-float 3s ease-in-out infinite;
}
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
# Verify dev server still runs without CSS errors — check browser console
```

**Commit:** `feat(dashboard): add CSS utility classes for infographic themes`

---

## Task 1.2 — Create Directory Structure and Shared Types

**Execute:**

Create the directory and files:

```bash
mkdir -p portal/ui/src/components/infographics
```

Create `portal/ui/src/components/infographics/types.ts`:

```typescript
export interface InfographicThemeProps {
  onNavigate?: (page: string) => void
}

export interface WorkflowStep {
  pageKey: string
  title: string
  subtitle: string
}

export interface CLICommand {
  command: string
  description: string
}

export interface QuickTip {
  label: string
  text: string
  pageKey: string
}

export const WORKFLOW_STEPS: WorkflowStep[] = [
  { pageKey: 'validate', title: 'Validate', subtitle: 'Compile your DSL schema' },
  { pageKey: 'onboard', title: 'Onboard', subtitle: 'Register partner & configure rules' },
  { pageKey: 'compare', title: 'Compare', subtitle: 'Run field-by-field comparisons' },
  { pageKey: 'rules', title: 'Rules', subtitle: 'Manage severity tiers (hard/soft/ignore)' },
  { pageKey: 'pipeline', title: 'Pipeline', subtitle: 'View processing results & status' },
]

export const CLI_COMMANDS: CLICommand[] = [
  { command: 'python -m pycoreedi validate <schema.dsl>', description: 'Compile & validate a DSL schema file' },
  { command: 'python -m pycoreedi run <config.yaml>', description: 'Run the full processing pipeline' },
  { command: 'python -m pycoreedi compare <source> <target>', description: 'Compare two files field-by-field' },
]

export const QUICK_TIPS: QuickTip[] = [
  { label: 'Start Here', text: 'Upload your DSL schema on the Validate page to compile it into YAML', pageKey: 'validate' },
  { label: 'New Partner?', text: 'Use the Onboard wizard to register and configure in 3 steps', pageKey: 'onboard' },
  { label: 'Pro Tip', text: 'Set up rule tiers (hard/soft/ignore) before running comparisons', pageKey: 'rules' },
  { label: 'Check Results', text: 'The Pipeline page shows all processing runs with status tracking', pageKey: 'pipeline' },
]
```

Create `portal/ui/src/components/infographics/index.tsx` (stub — will be completed in Phase 3):

```typescript
export type { InfographicThemeProps } from './types'
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(dashboard): add infographic shared types, constants, and directory structure`

---

### Phase 1 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
ls portal/ui/src/components/infographics/ && echo "Directory: OK"
echo "PHASE 1 GATE: PASS"
```

---

# PHASE 2: Build the 4 Theme Components

> **Prerequisite:** Phase 1 gate green.
> **Deliverables:** 4 visually distinct, fully rendered theme components.

**CRITICAL:** Use the `/frontend-design` skill for EACH theme. Each theme must look dramatically different. Read the visual spec for each theme carefully before invoking the skill.

---

## Task 2.1 — Whiteboard Sketch Theme

**Investigate:**
```bash
cat portal/ui/src/components/infographics/types.ts
cat portal/ui/src/index.css
```

**Execute:**

Use `/frontend-design` to create `portal/ui/src/components/infographics/WhiteboardTheme.tsx`.

**Visual spec for this theme:**

This should look like someone **sketched a workflow diagram on a whiteboard with markers during a standup meeting**. The overall container has a subtle dot-grid background (`sketch-bg` class). Nothing is perfectly aligned.

**Workflow section:**
- 5 step cards arranged horizontally with `flex-wrap`
- Each card: white background, `border: 2px dashed` in a unique color per step (blue, indigo, purple, amber, green), asymmetric border-radius (e.g., `rounded-tl-xl rounded-tr-sm rounded-bl-md rounded-br-2xl`), slight rotation (`-rotate-1`, `rotate-0.5`, `-rotate-0.5`, `rotate-1`, `-rotate-1`)
- Inside each card: a hand-drawn SVG icon (simple, imperfect paths using `stroke-linecap: round` with slight wobble), bold title, lighter subtitle
- Between cards: SVG dashed arrows with slightly curved paths (not straight lines — use cubic bezier with small offsets). Arrows use `stroke-dasharray: 8 4` and the `animate-draw` class for a draw-on effect
- Each card is a `<button>` that calls `onNavigate`
- Hover state: `scale-105`, border becomes solid, slight shadow appears

**CLI section:**
- A "whiteboard panel" (white bg, thick dashed border, slight rotation)
- Header: "CLI Commands" in a bold, slightly oversized font with a hand-drawn wavy underline (SVG path)
- 3 command blocks, each with the command in a slightly different marker color and the description in gray below
- Small "copy" icon button next to each command

**Tips section:**
- 4 small cards in a 2x2 grid, each with a different pastel background (yellow-50, blue-50, green-50, pink-50)
- Each card slightly rotated differently
- A small colored circle "marker dot" at the top-left of each card
- Tip text with the label bolded
- Clickable → `onNavigate`

**Colors:** Blue-500 (Validate), Indigo-500 (Onboard), Purple-500 (Compare), Amber-500 (Rules), Green-500 (Pipeline)

**Must import and use:** `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

To visually verify, temporarily import in Dashboard.tsx:
```typescript
import WhiteboardTheme from '../components/infographics/WhiteboardTheme'
// Add <WhiteboardTheme onNavigate={...} /> in the JSX
```
Check in browser at http://localhost:5173 — verify all 5 workflow steps render, CLI commands show, tips show, clicking steps triggers navigation. Then revert the temporary import.

**Commit:** `feat(dashboard): add Whiteboard Sketch infographic theme`

---

## Task 2.2 — Blueprint Theme

**Investigate:**
```bash
cat portal/ui/src/components/infographics/WhiteboardTheme.tsx | head -30
# (reference the pattern from Task 2.1)
```

**Execute:**

Use `/frontend-design` to create `portal/ui/src/components/infographics/BlueprintTheme.tsx`.

**Visual spec for this theme:**

This should look like a **technical engineering blueprint** — the kind you'd see in an architect's office or a mechanical engineering schematic. Dark navy/indigo background with thin cyan/white lines.

**Overall container:**
- `bg-indigo-950` with `blueprint-bg` grid overlay class
- Thin `border border-cyan-500/30` outer frame
- Corner markers: small L-shaped SVG marks at each corner (like registration marks on a print)
- A title block in the bottom-right: "PyEDI-Core — System Workflow" in small `font-mono text-cyan-300` with a thin border, date stamp

**Workflow section:**
- 5 step boxes arranged horizontally, connected by thin solid cyan lines with arrow markers
- Each box: transparent background with `border border-cyan-400/50`, `font-mono`, step number in a circle at top-left
- Title in `text-white font-medium`, subtitle in `text-cyan-300/70 text-xs`
- "Dimension lines" above or below the boxes (horizontal lines with small perpendicular end-caps, labeled with the step number — like engineering dimension annotations)
- Small inline SVG icons per step (simple geometric line art — checkmark, clipboard, overlapping squares, sliders, funnel)
- Hover: box border brightens to `border-cyan-300`, background gains a faint `bg-cyan-950/30`
- Clickable via `onNavigate`

**CLI section:**
- Rendered as a "specification table" — a bordered table with header row
- Header: `text-cyan-300 font-mono text-xs uppercase tracking-wider` — columns: "Command", "Function"
- Rows: command in `text-white font-mono text-sm`, description in `text-cyan-200/70`
- Table borders in `border-cyan-500/20`
- Copy button styled as a small outlined icon

**Tips section:**
- Rendered as numbered "notes" in a single column, prefixed with "NOTE 1:", "NOTE 2:", etc.
- Each note: thin left border in `border-cyan-400/40`, padding left, text in `text-cyan-100/80`
- Label in `text-cyan-300 font-medium`
- Clickable via `onNavigate`

**Colors:** Monochromatic — `indigo-950` bg, `cyan-300`/`cyan-400`/`cyan-500` for all line work, `white` for primary text

**Must import and use:** `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Temporarily render in Dashboard, verify in browser, then revert. Confirm dark background, grid lines, all content renders, navigation works.

**Commit:** `feat(dashboard): add Blueprint infographic theme`

---

## Task 2.3 — Sticky Notes & Yarn Theme

**Investigate:**
```bash
cat portal/ui/src/components/infographics/types.ts
```

**Execute:**

Use `/frontend-design` to create `portal/ui/src/components/infographics/StickyNotesTheme.tsx`.

**Visual spec for this theme:**

This should look like a **detective investigation board** or a **brainstorming wall** — colorful sticky notes pinned to a corkboard, connected by yarn/string. Think "crime drama evidence board" meets "startup brainstorm session."

**Overall container:**
- `cork-bg` class for the warm, textured corkboard background
- Subtle inner shadow (`shadow-inner`) for depth
- A thin `border-2 border-amber-800/30 rounded-lg` wooden frame effect

**Workflow section:**
- 5 "sticky notes" arranged in a loose, slightly overlapping horizontal row
- Each note: distinct solid pastel color (`bg-yellow-200`, `bg-blue-200`, `bg-green-200`, `bg-orange-200`, `bg-pink-200`), `shadow-md` for 3D depth, unique rotation (-3deg to +3deg range, each different)
- At the top of each note: a small SVG "pushpin" (circle with a spike) in a metallic color (`text-red-600`, `text-blue-600`, etc.)
- Title handwritten-style: `font-bold text-gray-800` (larger)
- Subtitle: `text-gray-600 text-sm`
- Step number written in the top-left corner like "1." in a casual style
- Between notes: SVG "yarn" paths — curved lines with `stroke-width: 2`, colored red or brown, slightly wavy (use quadratic bezier curves). These simulate string/yarn connecting the notes. Give them a subtle droop (catenary curve shape)
- Hover: note lifts up (`-translate-y-1 shadow-lg`), rotation straightens to 0
- Clickable via `onNavigate`

**CLI section:**
- Styled as a larger "index card" or "file folder tab" — cream/manila colored (`bg-amber-50`), slight rotation, horizontal ruled lines (CSS `repeating-linear-gradient` for faint blue lines like lined paper)
- Header: "CLI Quick Reference" in handwriting-style bold
- Commands in `font-mono text-sm` with the `$` prefix
- Descriptions indented below each command
- A small "paper clip" SVG decoration at the top-right corner

**Tips section:**
- 4 small "Post-it" notes in a 2x2 grid (staggered, overlapping slightly)
- Colors: `bg-yellow-100`, `bg-pink-100`, `bg-green-100`, `bg-blue-100`
- Each with a different slight rotation and `shadow-sm`
- Tape decoration: small translucent rectangle at the top of each note (`bg-white/40 rotate-2`)
- The `animate-float` class on alternating notes for subtle movement
- Clickable via `onNavigate`

**Colors:** Warm palette — amber/brown frame, pastel note colors, red/brown yarn

**Must import and use:** `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Temporarily render in Dashboard, verify corkboard background, sticky notes, yarn connections, all content renders, navigation works. Revert.

**Commit:** `feat(dashboard): add Sticky Notes & Yarn infographic theme`

---

## Task 2.4 — Terminal / Hacker Theme

**Investigate:**
```bash
cat portal/ui/src/components/infographics/types.ts
```

**Execute:**

Use `/frontend-design` to create `portal/ui/src/components/infographics/TerminalTheme.tsx`.

**Visual spec for this theme:**

This should look like a **hacker's terminal** or a **retro CRT monitor** — green text on black, monospace everything, ASCII art borders, a scanline overlay, and a faint CRT glow effect.

**Overall container:**
- `bg-gray-950 rounded-lg` with `scanline` class for the overlay
- A faint green glow: `shadow-[0_0_30px_rgba(34,197,94,0.1)]`
- Thin `border border-green-500/30` frame
- Top bar: three small colored circles (red, yellow, green — like a macOS window) followed by `font-mono text-xs text-green-500/50` showing `pyedi@portal:~/dashboard $`

**Workflow section:**
- Rendered as a "command output" — ASCII-art style:
```
┌──────────────────────────────────────────────────────────┐
│  PYEDI WORKFLOW                                          │
├──────┬──────────┬──────────┬──────────┬─────────────────┤
│  [1] │   [2]    │   [3]    │   [4]    │      [5]        │
│ VAL  │  ONBRD   │  COMP    │  RULES   │   PIPELINE      │
│      │          │          │          │                 │
│ DSL  │ Partner  │ Compare  │ Severity │  Results &      │
│ ━━►  │  ━━►     │  ━━►     │  ━━►     │  Status         │
└──────┴──────────┴──────────┴──────────┴─────────────────┘
```
- The actual implementation: a flex row of step "cells" bordered with box-drawing characters (use CSS borders styled to look like ASCII art, or literal Unicode box-drawing in a monospace `<pre>` block)
- Alternatively: each step as a block with `border border-green-500/40`, `font-mono`, green text hierarchy (`text-green-400` title, `text-green-600` subtitle, `text-green-800` decorative chars)
- Arrows between steps: `━━►` in `text-green-500`
- Step numbers in brackets: `[1]`, `[2]`, etc.
- Hover: step block background changes to `bg-green-950`, border brightens
- Clickable via `onNavigate`

**CLI section:**
- This theme IS a terminal, so the CLI section should feel native:
- Each command preceded by a prompt: `$ ` in `text-green-600`
- Command text in `text-green-400 font-mono`
- Description as a "comment": `# description` in `text-green-700/70`
- A blinking cursor (`animate-cursor`) after the last command
- Commands appear to be "typed" — use a subtle reveal animation or just static display

**Tips section:**
- Rendered as "log output" or "man page" style:
- `[INFO]` prefix in `text-cyan-400` for each tip
- `[TIP]` label in `text-yellow-400`
- Tip text in `text-green-300/80`
- Each on its own line, prefixed with a timestamp-like marker: `00:01 >`, `00:02 >`, etc.
- Clickable via `onNavigate` (cursor: pointer, hover underline)

**Colors:** Strictly `green-*` hierarchy on `gray-950`. Accent with `cyan-400` for info tags and `yellow-400` for tip labels only.

**Must import and use:** `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Temporarily render in Dashboard, verify dark terminal look, scanlines, all content renders, navigation works. Revert.

**Commit:** `feat(dashboard): add Terminal/Hacker infographic theme`

---

### Phase 2 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# Verify all 4 theme files exist
ls portal/ui/src/components/infographics/
# Should show: WhiteboardTheme.tsx, BlueprintTheme.tsx, StickyNotesTheme.tsx, TerminalTheme.tsx, types.ts, index.tsx

echo "PHASE 2 GATE: PASS"
```

---

# PHASE 3: Randomizer + Dashboard Integration

> **Prerequisite:** Phase 2 gate green.
> **Deliverables:** Theme randomizer hook, barrel export, Dashboard integration with onNavigate wiring.

---

## Task 3.1 — Complete the Barrel Export with Randomizer Hook

**Investigate:**
```bash
cat portal/ui/src/components/infographics/index.tsx
```

**Execute:**

Replace the stub in `portal/ui/src/components/infographics/index.tsx` with:

```typescript
import { useMemo } from 'react'
import type { InfographicThemeProps } from './types'
import WhiteboardTheme from './WhiteboardTheme'
import BlueprintTheme from './BlueprintTheme'
import StickyNotesTheme from './StickyNotesTheme'
import TerminalTheme from './TerminalTheme'

export type { InfographicThemeProps } from './types'

const THEMES: React.ComponentType<InfographicThemeProps>[] = [
  WhiteboardTheme,
  BlueprintTheme,
  StickyNotesTheme,
  TerminalTheme,
]

export const THEME_NAMES = ['Whiteboard Sketch', 'Blueprint', 'Sticky Notes & Yarn', 'Terminal'] as const

/**
 * Returns a random infographic theme component.
 * Selection is stable for the lifetime of the component (useMemo with empty deps).
 */
export function useRandomTheme(): {
  Theme: React.ComponentType<InfographicThemeProps>
  themeName: string
  themeIndex: number
} {
  return useMemo(() => {
    const idx = Math.floor(Math.random() * THEMES.length)
    return {
      Theme: THEMES[idx],
      themeName: THEME_NAMES[idx],
      themeIndex: idx,
    }
  }, [])
}

export { WhiteboardTheme, BlueprintTheme, StickyNotesTheme, TerminalTheme }
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(dashboard): add theme randomizer hook and barrel exports`

---

## Task 3.2 — Integrate into Dashboard

**Investigate:**
```bash
cat portal/ui/src/pages/Dashboard.tsx
cat portal/ui/src/App.tsx
```

**Execute:**

**Step A:** Modify `portal/ui/src/pages/Dashboard.tsx`:

1. Add import: `import { useRandomTheme, THEME_NAMES } from '../components/infographics'`
2. Change the function signature to accept `onNavigate`:
   ```typescript
   export default function DashboardPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
   ```
3. Inside the component, call the randomizer:
   ```typescript
   const { Theme, themeName } = useRandomTheme()
   ```
4. After the existing `{recent.length > 0 && ...}` block (before the closing `</div>`), add the infographic section:
   ```tsx
   {/* Infographic — randomly selected theme */}
   <div className="mt-8">
     <div className="flex items-center justify-between mb-4">
       <h2 className="text-lg font-bold text-gray-700">How PyEDI Works</h2>
       <span className="text-xs text-gray-400 italic">Theme: {themeName}</span>
     </div>
     <Theme onNavigate={onNavigate} />
   </div>
   ```

**Step B:** Modify `portal/ui/src/App.tsx` line 58:

Change:
```tsx
{page === 'dashboard' && <DashboardPage />}
```
To:
```tsx
{page === 'dashboard' && <DashboardPage onNavigate={(p) => setPage(p as Page)} />}
```

This follows the exact same pattern already used on lines 62-64 for Compare, Rules, and Onboard.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(dashboard): integrate random infographic theme into Dashboard`

---

### Phase 3 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
echo "PHASE 3 GATE: PASS"
```

---

# PHASE 4: Visual Verification of All 4 Themes

> **Prerequisite:** Phase 3 gate green.
> **Deliverables:** Each theme visually verified in the browser. All navigation works.

---

## Task 4.1 — Verify Each Theme Individually

To test each theme without relying on random selection, temporarily modify `Dashboard.tsx` to render a specific theme. For each of the 4 themes:

1. Import the theme directly:
   ```typescript
   import { WhiteboardTheme } from '../components/infographics'
   ```
2. Replace `<Theme onNavigate={onNavigate} />` with `<WhiteboardTheme onNavigate={onNavigate} />`
3. Open http://localhost:5173 and verify:

**Verification checklist (apply to EACH theme):**

- [ ] Theme renders without console errors
- [ ] All 5 workflow steps are visible with correct titles and subtitles
- [ ] Clicking each workflow step navigates to the correct page
- [ ] All 3 CLI commands display correctly
- [ ] CLI copy buttons work (click → clipboard contains command)
- [ ] All 4 tips display with correct text
- [ ] Clicking each tip navigates to the correct page
- [ ] The visual style is distinctive and matches the theme description
- [ ] The theme looks good at typical desktop width (1200-1920px)
- [ ] The theme doesn't overflow or break at 1024px width
- [ ] Hover states work on interactive elements
- [ ] No Tailwind class warnings in console

4. Repeat for `BlueprintTheme`, `StickyNotesTheme`, `TerminalTheme`

**After verifying all 4:**
5. Restore the randomizer (`<Theme onNavigate={onNavigate} />`)
6. Reload the page multiple times — confirm different themes appear
7. Verify the theme name label updates to match the rendered theme

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
# All 4 themes verified visually
echo "PHASE 4 GATE: PASS"
```

**Commit:** `feat(dashboard): verify all 4 infographic themes — visual QA complete`

---

# PHASE 5: Final Verification

> **Prerequisite:** Phase 4 gate green.
> **Deliverables:** Clean final state, all existing functionality preserved.

---

## Task 5.1 — Full Regression Check

```bash
# TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# Dev server runs
curl -s http://localhost:5173 | head -5 && echo "Frontend: OK"

# All existing pages still work — manually click through each nav item:
# Dashboard, Validate, Pipeline, Tests, Compare, Rules, Onboard, Config
# Confirm no regressions

echo "PHASE 5 GATE: PASS — Dashboard infographics are production-ready"
```

**Final commit:** `feat(dashboard): 4-theme randomized infographic system — complete`

---

## File Summary

| File | Action | Purpose |
|---|---|---|
| `portal/ui/src/index.css` | EDIT | Add CSS utility classes for theme backgrounds and animations |
| `portal/ui/src/components/infographics/types.ts` | CREATE | Shared TypeScript interfaces and content constants |
| `portal/ui/src/components/infographics/WhiteboardTheme.tsx` | CREATE | Theme 1: hand-drawn whiteboard sketch |
| `portal/ui/src/components/infographics/BlueprintTheme.tsx` | CREATE | Theme 2: technical engineering blueprint |
| `portal/ui/src/components/infographics/StickyNotesTheme.tsx` | CREATE | Theme 3: corkboard with sticky notes and yarn |
| `portal/ui/src/components/infographics/TerminalTheme.tsx` | CREATE | Theme 4: retro terminal / hacker aesthetic |
| `portal/ui/src/components/infographics/index.tsx` | CREATE | Barrel export + `useRandomTheme()` hook |
| `portal/ui/src/pages/Dashboard.tsx` | EDIT | Accept `onNavigate`, render random theme below existing content |
| `portal/ui/src/App.tsx` | EDIT | Thread `onNavigate` to Dashboard (line 58) |
