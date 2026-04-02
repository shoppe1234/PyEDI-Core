# Fix Broken Links — Orchestration Prompt

**Purpose:** Resume and complete all outstanding work from `instructions/fixBrokenLinks.md`. Two issues remain: (1) Rules Management shows no rules, and (2) Dashboard has no SVG infographic. This prompt picks up exactly where prior work stopped.

**Coding standards:** `CLAUDE.md` and `pycoreEdi/CLAUDE.md`
**Design spec for themes:** `instructions/dashboard_infographic_orchestration_prompt.md`

---

## Rules of Engagement

1. **Sequential** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Use `/frontend-design` skill** — invoke it for each new theme component.

---

## Current State (verified 2026-03-27)

| Item | Status |
|------|--------|
| `config/compare_rules/bevager_810.yaml` | Modified/corrupted — needs `git restore` |
| `portal/ui/src/components/infographics/types.ts` | EXISTS — complete |
| `portal/ui/src/components/infographics/WhiteboardTheme.tsx` | EXISTS — complete (205 lines) |
| `portal/ui/src/components/infographics/index.tsx` | EXISTS — **stub only** (1 line) |
| `portal/ui/src/components/infographics/BlueprintTheme.tsx` | MISSING |
| `portal/ui/src/components/infographics/StickyNotesTheme.tsx` | MISSING |
| `portal/ui/src/components/infographics/TerminalTheme.tsx` | MISSING |
| `portal/ui/src/pages/Dashboard.tsx` | Exists — **not yet integrated** (no onNavigate, no Theme) |
| `portal/ui/src/App.tsx` line 58 | `<DashboardPage />` — **not yet wired** |

---

## Pre-Flight

Before any task, verify the environment is healthy:

```bash
cd ~/VS/pycoreEdi

# Verify git status on the corrupted YAML
git status config/compare_rules/bevager_810.yaml

# Verify infographic directory
ls portal/ui/src/components/infographics/

# TypeScript baseline
cd portal/ui && npx tsc --noEmit && echo "TSC: PASS"
cd ~/VS/pycoreEdi

# Confirm backend is reachable (optional — needed for Issue 1 only)
curl -s http://localhost:8000/api/health && echo "API: OK"
```

If `tsc --noEmit` fails at baseline, **stop and fix before proceeding**.

---

# ISSUE 1: Rules Management — No Rules Displayed

> **Prerequisite:** Pre-flight green.
> **Problem:** `bevager_810.yaml` was corrupted (comments stripped, compact reformat, empty `field: ''` rule added). Rules Management page shows 0 rules.

---

## Task 1.1 — Restore bevager_810.yaml

**Investigate:**
```bash
cd ~/VS/pycoreEdi
git diff config/compare_rules/bevager_810.yaml | head -60
```

Review the diff to confirm the corruption (empty `field: ''` entries, stripped comments, compact reformat). Then:

**Execute:**
```bash
git restore config/compare_rules/bevager_810.yaml
```

**Test Gate:**
```bash
git status config/compare_rules/bevager_810.yaml
# Should show: nothing to commit (file restored)
cat config/compare_rules/bevager_810.yaml | head -20
# Should show original formatting with comments
echo "TASK 1.1: PASS"
```

**No commit needed** — `git restore` reverts the file; nothing to stage.

---

## Task 1.2 — Verify Rules API Response

**Execute:**
```bash
curl -s http://localhost:8000/api/rules/tiers | python -m json.tool
```

**Test Gate:**
- Confirm partner tier for `bevager` is present
- Confirm classification rule count is 8, ignore count is 0
- If API returns error or empty, check that backend is running: `cd portal && uvicorn api.main:app --reload --port 8000 &`

```bash
echo "TASK 1.2: PASS"
```

---

## Task 1.3 — Verify Rules Management UI

**Execute:** Open browser → `http://localhost:5173` → navigate to Rules Management page.

**Test Gate:**
- [ ] Tier cards render (Universal, Transaction-Type, Partner tiers visible)
- [ ] Bevager partner tier shows 8 classification rules, 0 ignore rules
- [ ] Rule list items are displayed (not empty)
- [ ] No console errors in browser DevTools

```bash
echo "ISSUE 1: RULES MANAGEMENT — PASS"
```

---

# ISSUE 2: Dashboard Infographic — Phase 2 (Remaining Themes)

> **Prerequisite:** Issue 1 complete.
> **Context:** Phase 1 is done. WhiteboardTheme.tsx exists. Need 3 more themes, then integration.

---

## Task 2.1 — Commit the Untracked WhiteboardTheme.tsx

WhiteboardTheme.tsx exists but was never committed (shown as untracked in git status).

**Execute:**
```bash
cd ~/VS/pycoreEdi
git add portal/ui/src/components/infographics/WhiteboardTheme.tsx
git commit -m "feat(dashboard): add Whiteboard Sketch infographic theme"
```

**Test Gate:**
```bash
git log --oneline -1
# Should show the commit above
echo "TASK 2.1: PASS"
```

---

## Task 2.2 — Create BlueprintTheme.tsx

**Investigate:**
```bash
cat portal/ui/src/components/infographics/types.ts
cat portal/ui/src/components/infographics/WhiteboardTheme.tsx | head -30
cat portal/ui/src/index.css | grep -A3 "blueprint-bg"
```

**Execute:** Use `/frontend-design` to create `portal/ui/src/components/infographics/BlueprintTheme.tsx`.

**Visual spec:** Technical engineering blueprint. Dark navy/indigo background, thin cyan/white lines. See full spec in `instructions/dashboard_infographic_orchestration_prompt.md` → Task 2.2.

Key requirements:
- `bg-indigo-950` with `blueprint-bg` grid class
- Corner registration marks (L-shaped SVG at each corner)
- Title block bottom-right: `"PyEDI-Core — System Workflow"` in `font-mono text-cyan-300`
- 5 step boxes with `border border-cyan-400/50`, `font-mono`, step number in circle top-left
- Dimension lines above/below boxes (engineering annotation style)
- CLI as a specification table with header row (`font-mono text-xs uppercase`)
- Tips as numbered NOTEs with `border-cyan-400/40` left border
- Must import: `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`
- Default export: `BlueprintTheme`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Temporarily add to `Dashboard.tsx` for visual check:
```typescript
import BlueprintTheme from '../components/infographics/BlueprintTheme'
// Replace existing JSX with: <BlueprintTheme />
```
Open `http://localhost:5173` — verify dark blueprint background, grid lines, all content, then revert Dashboard.tsx.

**Commit:** `feat(dashboard): add Blueprint infographic theme`

---

## Task 2.3 — Create StickyNotesTheme.tsx

**Investigate:**
```bash
cat portal/ui/src/components/infographics/types.ts
cat portal/ui/src/index.css | grep -A3 "cork-bg"
cat portal/ui/src/index.css | grep -A3 "animate-float"
```

**Execute:** Use `/frontend-design` to create `portal/ui/src/components/infographics/StickyNotesTheme.tsx`.

**Visual spec:** Detective investigation board / brainstorming wall — colorful sticky notes on a corkboard, connected by yarn. See full spec in `instructions/dashboard_infographic_orchestration_prompt.md` → Task 2.3.

Key requirements:
- `cork-bg` class for warm corkboard background, `border-2 border-amber-800/30 rounded-lg` wooden frame
- 5 sticky notes with distinct pastel colors (`bg-yellow-200`, `bg-blue-200`, `bg-green-200`, `bg-orange-200`, `bg-pink-200`), unique rotations (-3 to +3deg), SVG pushpin at top
- SVG yarn paths (quadratic bezier, `stroke-width: 2`, catenary droop shape) connecting notes
- CLI as large index card / manila file folder (`bg-amber-50`), ruled lines, paper clip SVG decoration
- Tips as 2x2 Post-it grid with tape decoration (`bg-white/40 rotate-2`), `animate-float` on alternating notes
- Must import: `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`
- Default export: `StickyNotesTheme`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Temporarily render in Dashboard, verify corkboard background, sticky notes, yarn connections, all content. Revert.

**Commit:** `feat(dashboard): add Sticky Notes & Yarn infographic theme`

---

## Task 2.4 — Create TerminalTheme.tsx

**Investigate:**
```bash
cat portal/ui/src/components/infographics/types.ts
cat portal/ui/src/index.css | grep -A5 "scanline"
cat portal/ui/src/index.css | grep -A5 "animate-cursor"
```

**Execute:** Use `/frontend-design` to create `portal/ui/src/components/infographics/TerminalTheme.tsx`.

**Visual spec:** Retro CRT terminal — green text on black, monospace, ASCII art borders, scanline overlay. See full spec in `instructions/dashboard_infographic_orchestration_prompt.md` → Task 2.4.

Key requirements:
- `bg-gray-950 rounded-lg` with `scanline` class, green glow `shadow-[0_0_30px_rgba(34,197,94,0.1)]`
- macOS-style top bar (3 colored circles + `pyedi@portal:~/dashboard $` in `font-mono text-green-500/50`)
- Workflow as bordered flex row, step cells with `border border-green-500/40`, `[1]` style numbering, `━━►` arrows
- CLI native to terminal: `$ command` in `text-green-400`, `# comment` in `text-green-700/70`, blinking cursor (`animate-cursor`) after last command
- Tips as log output: `[INFO]` in `text-cyan-400`, `[TIP]` in `text-yellow-400`, timestamp prefix `00:01 >` per line
- Colors: strictly `green-*` on `gray-950`, accent `cyan-400` and `yellow-400` only
- Must import: `InfographicThemeProps`, `WORKFLOW_STEPS`, `CLI_COMMANDS`, `QUICK_TIPS` from `./types`
- Default export: `TerminalTheme`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Temporarily render in Dashboard, verify dark terminal look, scanlines, all content. Revert.

**Commit:** `feat(dashboard): add Terminal/Hacker infographic theme`

---

### Phase 2 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
ls portal/ui/src/components/infographics/
# Must show: WhiteboardTheme.tsx, BlueprintTheme.tsx, StickyNotesTheme.tsx, TerminalTheme.tsx, types.ts, index.tsx
echo "PHASE 2 GATE: PASS"
```

---

# ISSUE 2: Dashboard Infographic — Phase 3 (Integration)

> **Prerequisite:** Phase 2 gate green.

---

## Task 3.1 — Complete the Barrel Export with Randomizer Hook

**Investigate:**
```bash
cat portal/ui/src/components/infographics/index.tsx
```

Current content is a 1-line stub: `export type { InfographicThemeProps } from './types'`

**Execute:** Replace the entire file with:

```typescript
import { useMemo } from 'react'
import type React from 'react'
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
 * Returns a random infographic theme component, stable for the lifetime of the component.
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

## Task 3.2 — Integrate Infographic into Dashboard.tsx

**Investigate:**
```bash
cat portal/ui/src/pages/Dashboard.tsx
```

Current: 48 lines, `export default function DashboardPage()` with no props, no theme import.

**Execute:** Make these minimal changes to `portal/ui/src/pages/Dashboard.tsx`:

1. Add import at top:
   ```typescript
   import { useRandomTheme } from '../components/infographics'
   ```

2. Change function signature (line 13):
   ```typescript
   export default function DashboardPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
   ```

3. Add randomizer hook as the first line inside the function body (after `{`):
   ```typescript
   const { Theme, themeName } = useRandomTheme()
   ```

4. After the `{recent.length > 0 && ...}` closing block (before the final `</div>`), add:
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

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(dashboard): integrate random infographic theme into Dashboard`

---

## Task 3.3 — Wire onNavigate in App.tsx

**Investigate:**
```bash
cat portal/ui/src/App.tsx
```

Current line 58: `{page === 'dashboard' && <DashboardPage />}`

**Execute:** Change line 58 only:

```tsx
{page === 'dashboard' && <DashboardPage onNavigate={(p) => setPage(p as Page)} />}
```

This follows the exact same pattern already used on lines 62-64 for Compare, Rules, and Onboard.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
# Open http://localhost:5173 — confirm infographic section appears below stats/table on Dashboard
```

**Commit:** `feat(dashboard): wire onNavigate to DashboardPage in App.tsx`

---

### Phase 3 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
echo "PHASE 3 GATE: PASS"
```

---

# ISSUE 2: Dashboard Infographic — Phase 4 (Visual QA)

> **Prerequisite:** Phase 3 gate green.

---

## Task 4.1 — Verify Each Theme Individually

For each of the 4 themes, temporarily pin Dashboard to that theme for testing:

**In `Dashboard.tsx`, replace `<Theme onNavigate={onNavigate} />` with:**
```tsx
<WhiteboardTheme onNavigate={onNavigate} />
```

Open `http://localhost:5173`. Apply checklist:

**Verification checklist (apply to EACH of the 4 themes):**

- [ ] Renders without console errors
- [ ] All 5 workflow steps visible with correct titles and subtitles
- [ ] Clicking each workflow step navigates to the correct page
- [ ] All 3 CLI commands display correctly
- [ ] CLI copy buttons work (clipboard receives command text)
- [ ] All 4 tips display with correct text
- [ ] Clicking each tip navigates to the correct page
- [ ] Visual style is distinctive and matches theme description
- [ ] No overflow or layout break at 1024px width
- [ ] Hover states work on interactive elements
- [ ] No Tailwind class warnings in browser console

Repeat for `BlueprintTheme`, `StickyNotesTheme`, `TerminalTheme`.

**After verifying all 4:**
- Restore `<Theme onNavigate={onNavigate} />` (randomizer)
- Reload page 4+ times — confirm different themes appear
- Confirm theme name label updates to match rendered theme

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
echo "PHASE 4 GATE: PASS"
```

**Commit:** `feat(dashboard): visual QA — all 4 infographic themes verified`

---

# Final Verification

> **Prerequisite:** Phase 4 gate green.

---

## Task 5.1 — Full Regression Check

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
curl -s http://localhost:5173 | head -5 && echo "Frontend: OK"
```

Manually click through all nav items: Dashboard, Validate, Pipeline, Tests, Compare, Rules, Onboard, Config — confirm no regressions.

```bash
echo "ALL DONE — Dashboard infographics production-ready, Rules Management restored"
```

---

## Completion Summary

| Task | What Was Fixed | Test Gate |
|------|---------------|-----------|
| 1.1 | Restored bevager_810.yaml | `git status` clean |
| 1.2 | Verified rules API (8 classification, 0 ignore) | curl response |
| 1.3 | Rules Management UI shows rules | Browser visual check |
| 2.1 | Committed untracked WhiteboardTheme.tsx | `git log` |
| 2.2 | Created BlueprintTheme.tsx | `tsc --noEmit` + browser |
| 2.3 | Created StickyNotesTheme.tsx | `tsc --noEmit` + browser |
| 2.4 | Created TerminalTheme.tsx | `tsc --noEmit` + browser |
| 3.1 | Completed index.tsx barrel + randomizer hook | `tsc --noEmit` |
| 3.2 | Integrated infographic into Dashboard.tsx | `tsc --noEmit` |
| 3.3 | Wired onNavigate in App.tsx | `tsc --noEmit` + browser |
| 4.1 | Visual QA all 4 themes individually | Browser checklist |
| 5.1 | Full regression — all pages working | Manual smoke test |
