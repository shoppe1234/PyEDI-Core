# Fix Broken Links — Task List

## Issue 1: Rules Management — No Rules Displayed

| # | Task | Detail | Status |
|---|------|--------|--------|
| 1 | Restore `bevager_810.yaml` | Run `git restore config/compare_rules/bevager_810.yaml` to revert uncommitted corruption (stripped comments, compact reformat, empty `field: ''` rule) | ☐ |
| 2 | Verify rules API response | Hit `GET /api/rules/tiers` and confirm partner-tier counts match expected (bevager: 8 classification, 0 ignore) | ☐ |
| 3 | Verify Rules Management UI | Reload Rules Management page at `localhost:5173` → confirm tier cards and rule lists render correctly | ☐ |

## Issue 2: Dashboard — No SVG Infographic

### Phase 2 — Complete Theme Components

| # | Task | Detail | Status |
|---|------|--------|--------|
| 4 | Stage & commit `WhiteboardTheme.tsx` | File exists at `portal/ui/src/components/infographics/WhiteboardTheme.tsx` (205 lines, untracked) — commit it | ☐ |
| 5 | Create `BlueprintTheme.tsx` | Technical blueprint aesthetic per `dashboard_infographic_orchestration_prompt.md` | ☐ |
| 6 | Create `StickyNotesTheme.tsx` | Corkboard with yarn aesthetic per orchestration prompt | ☐ |
| 7 | Create `TerminalTheme.tsx` | Retro terminal aesthetic per orchestration prompt | ☐ |

### Phase 3 — Integration

| # | Task | Detail | Status |
|---|------|--------|--------|
| 8 | Complete `index.tsx` barrel export | Add theme component imports and `useRandomTheme()` hook to `portal/ui/src/components/infographics/index.tsx` | ☐ |
| 9 | Integrate infographic into `Dashboard.tsx` | Import theme, add infographic section below existing stats/table content | ☐ |
| 10 | Wire `onNavigate` in `App.tsx` | Pass `onNavigate={(p) => setPage(p as Page)}` to `<DashboardPage />` | ☐ |

### Phase 4 — Verify

| # | Task | Detail | Status |
|---|------|--------|--------|
| 11 | Verify SVG renders on dashboard | Reload `localhost:5173/` → confirm infographic with SVG elements appears below stats | ☐ |
| 12 | Verify navigation from infographic | Click workflow step cards → confirm they navigate to correct pages | ☐ |
