# Portal UI — SQLite Comparator Integration — Orchestration Prompt

**Purpose:** Wire all SQLite-backed comparator features (error discovery, reclassification, summary statistics, run diffing) into the portal React UI. All backend endpoints already exist — this is a UI-only implementation.

**Portal UI spec:** `portalUiReadMe.md`
**Backend reference:** `portal/api/routes/compare.py` (275 lines — all endpoints implemented)
**Backend models:** `portal/api/models.py` (CompareRunResponse, CompareSummaryResponse, DiscoveryResponse — all exist)
**UI source:** `portal/ui/src/pages/Compare.tsx` (365 lines), `portal/ui/src/api.ts` (88 lines)
**Coding standards:** `CLAUDE.md`
**Existing tests:** `tests/test_comparator.py` (do not modify)

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start Phase B until Phase A gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments, no renaming.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **No business logic in React** — pages render data from API responses. All processing lives in `pyedi_core/`.
8. **No new npm dependencies** — use only React, Tailwind, and native browser APIs.
9. **Match existing patterns exactly** — follow the Tailwind classes, component structure, and `api.ts` conventions already in the codebase.
10. **Single file** — all new UI goes into `Compare.tsx`. No new component files.
11. **All responses typed as `any`** — match current `api.ts` pattern. No TypeScript interfaces for API responses.
12. **Backend is read-only** — do NOT modify any Python files. All backend endpoints are already implemented and tested.

---

## Pre-Flight

Before starting any task, run these checks:

```bash
# Verify existing Python tests pass (backend must be green)
python -m pytest tests/test_comparator.py -v --tb=short 2>&1 | tail -20
python -m pytest tests/ -v --tb=short 2>&1 | tail -30

# Verify pyedi CLI is functional
python -m pycoreedi compare --list-profiles --config config/config.yaml

# Verify compare engine and all store functions are importable
python -c "from pyedi_core.comparator import compare, export_csv, reclassify; print('Compare engine OK')"
python -c "from pyedi_core.comparator.store import get_runs, get_discoveries, compare_two_runs, get_severity_breakdown; print('Store OK')"

# Verify backend endpoints exist (import check — no server needed)
python -c "
from portal.api.routes.compare import (
    reclassify_run, diff_runs, get_run_summary,
    list_discoveries, apply_discovery_endpoint
)
print('All 5 new endpoints importable')
"

# Verify portal UI builds
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..

# Verify current DB has data for manual testing
python -c "
from pyedi_core.comparator.store import get_runs, init_db
init_db('data/compare.db')
runs = get_runs('data/compare.db')
print(f'DB has {len(runs)} runs')
"
```

If anything fails at baseline, **stop and fix before proceeding**.

---

# PHASE A: API Client + Foundation

> **Prerequisite:** Pre-flight green.
> **Deliverables:** 5 new api.ts methods, tab toggle in Compare.tsx.

---

## Task A1: Add 5 Missing API Methods to api.ts

**Investigate:**
```bash
# Read current api.ts — understand existing patterns
# Read portal/api/routes/compare.py — verify endpoint URLs and methods
```

**Execute:**
1. Read `portal/ui/src/api.ts`
2. Read `portal/api/routes/compare.py` — note exact URL paths and HTTP methods for the 5 unwired endpoints
3. Add 5 new methods inside the `api` object, after `compareUpdateRules` (line ~87), before the closing `}`:

```ts
// Reclassify: re-evaluate diffs with current rules
compareReclassify: (runId: number) =>
  request<any>(`/compare/runs/${runId}/reclassify`, { method: 'POST' }),

// Run diff: compare two runs for new/resolved/changed errors
compareRunDiff: (runIdA: number, runIdB: number) =>
  request<any>(`/compare/runs/${runIdA}/diff/${runIdB}`),

// Summary: severity/segment/field breakdowns + top errors
compareRunSummary: (runId: number) =>
  request<any>(`/compare/runs/${runId}/summary`),

// Discoveries: list unclassified field combos
compareDiscoveries: (profile: string, applied?: boolean) => {
  const params = new URLSearchParams({ profile });
  if (applied !== undefined) params.set('applied', String(applied));
  return request<any[]>(`/compare/discoveries?${params}`);
},

// Apply discovery: promote to classification
compareApplyDiscovery: (discoveryId: number) =>
  request<any>(`/compare/discoveries/${discoveryId}/apply`, { method: 'POST' }),
```

**Test gate:**
```bash
# Build must pass with new methods
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

**Commit:** `feat(portal-ui): add 5 missing compare API methods to api.ts`

---

## Task A2: Add Tab Toggle (Runs | Discoveries)

**Investigate:**
```bash
# Read Compare.tsx — understand the page structure
# Note the pair status filter pattern at lines 284-294 for styling reference
```

**Execute:**
1. Read `portal/ui/src/pages/Compare.tsx`
2. Add new state variable near the top of `ComparePage()`:
   ```ts
   const [view, setView] = useState<'runs' | 'discoveries'>('runs')
   ```
3. Add tab toggle UI immediately after the `<h1>` page title (line 144) and before the error banner:
   ```tsx
   <div className="flex gap-1 mb-4">
     {(['runs', 'discoveries'] as const).map(v => (
       <button
         key={v}
         onClick={() => setView(v)}
         className={`px-3 py-1 rounded text-sm capitalize ${view === v ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
       >
         {v}
       </button>
     ))}
   </div>
   ```
4. Wrap ALL existing content (from "New Comparison" card through "Pair Detail — Diffs") in a conditional:
   ```tsx
   {view === 'runs' && (
     <>
       {/* ...all existing content... */}
     </>
   )}
   ```
5. Add a placeholder for the discoveries view:
   ```tsx
   {view === 'discoveries' && (
     <div className="bg-white rounded-lg shadow p-4">
       <p className="text-sm text-gray-400">Discoveries panel — coming in Phase C.</p>
     </div>
   )}
   ```

**Test gate:**
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
# Manual: open browser, verify tab toggle appears, switching works, existing content hidden/shown correctly
```

**Commit:** `feat(portal-ui): add Runs/Discoveries tab toggle to Compare page`

---

## Phase A Gate

```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Build passes. Tab toggle works. All 5 api.ts methods defined. **Proceed to Phase B.**

---

# PHASE B: Runs Tab Features

> **Prerequisite:** Phase A gate green.
> **Deliverables:** Reclassify button + badge, summary statistics panel, run diff via checkboxes.

---

## Task B1: Reclassify Button + Reclassified Badge

**Investigate:**
```bash
# Read Compare.tsx — find the action button row (lines 192-213)
# Read the run history table row structure (lines 257-271)
# Read portal/api/routes/compare.py — verify POST /runs/{run_id}/reclassify response shape
```

**Execute:**
1. Read `portal/ui/src/pages/Compare.tsx`
2. Add state near other state declarations:
   ```ts
   const [reclassifying, setReclassifying] = useState(false)
   ```
3. Add handler function after `saveRules()` (~line 140):
   ```ts
   const reclassifyRun = async () => {
     if (!selectedRun) return
     setReclassifying(true)
     setError('')
     try {
       await api.compareReclassify(selectedRun.run_id)
       loadRuns()
     } catch (e: any) {
       setError(e.message)
     } finally {
       setReclassifying(false)
     }
   }
   ```
4. Add "Reclassify" button to the button row, after the Export CSV link, conditionally shown when `selectedRun` exists:
   ```tsx
   {selectedRun && (
     <button
       onClick={reclassifyRun}
       disabled={reclassifying}
       className="border border-gray-300 px-4 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
     >
       {reclassifying ? 'Reclassifying...' : 'Reclassify'}
     </button>
   )}
   ```
5. In the Run History table `<tbody>`, modify the `run_id` cell to show a reclassified badge:
   ```tsx
   <td className="py-1 pr-2 font-mono">
     {r.run_id}
     {r.reclassified_from && (
       <span className="ml-1 px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">
         re:{r.reclassified_from}
       </span>
     )}
   </td>
   ```

**Test gate:**
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

**Repair loop:** If build fails, read the error output. Common issues:
- Missing import: verify `api` import is still correct
- JSX syntax error: check for unclosed tags or misplaced braces
- Fix the error and re-run build. Do not proceed until green.

**Manual verification (if portal running):**
1. Select a run → click Reclassify → verify new run appears in history
2. Verify new run shows purple `re:N` badge with original run_id
3. Verify clicking Reclassify on a run with no mismatches still works (creates run with same counts)

**Commit:** `feat(portal-ui): add reclassify button and reclassified_from badge`

---

## Task B2: Summary Statistics Panel with Inline Bars

**Investigate:**
```bash
# Read portal/api/routes/compare.py — get_run_summary() response shape
# The response is: { severity: {hard:N, soft:N, ignore:N}, segments: {seg:N}, fields: {field:N}, top_errors: [{segment, field, count}] }
```

**Execute:**
1. Read `portal/ui/src/pages/Compare.tsx`
2. Add state:
   ```ts
   const [summary, setSummary] = useState<any>(null)
   ```
3. Modify `selectRun()` — after the existing `setPairs(...)` call, add:
   ```ts
   setSummary(await api.compareRunSummary(run.run_id))
   ```
4. In the deselection paths (if any), clear summary: `setSummary(null)`
5. Add new UI section **after the "Run Detail — Pairs" section** and **before the "Pair Detail — Diffs" section**. Only shown when `selectedRun && summary`:

```tsx
{selectedRun && summary && (
  <div className="bg-white rounded-lg shadow p-4 mb-4">
    <h2 className="font-semibold text-sm text-gray-500 uppercase mb-3">
      Run #{selectedRun.run_id} — Summary
    </h2>
    <div className="grid grid-cols-2 gap-4">
      {/* Severity Breakdown */}
      <div>
        <h3 className="text-xs text-gray-500 mb-2 uppercase">Severity</h3>
        {Object.entries(summary.severity || {}).map(([sev, count]: [string, any]) => {
          const max = Math.max(...Object.values(summary.severity || {}).map(Number))
          const pct = max > 0 ? (Number(count) / max) * 100 : 0
          const barColor = sev === 'hard' ? 'bg-red-300' : sev === 'soft' ? 'bg-yellow-300' : 'bg-gray-300'
          return (
            <div key={sev} className="flex items-center gap-2 mb-1">
              <StatusBadge status={sev} />
              <div className="flex-1 bg-gray-100 rounded h-2">
                <div className={`${barColor} h-2 rounded`} style={{ width: `${pct}%` }} />
              </div>
              <span className="text-xs text-gray-600 w-8 text-right">{String(count)}</span>
            </div>
          )
        })}
      </div>

      {/* Segment Breakdown */}
      <div>
        <h3 className="text-xs text-gray-500 mb-2 uppercase">By Segment</h3>
        <div className="max-h-40 overflow-auto">
          {Object.entries(summary.segments || {})
            .sort(([,a]: any, [,b]: any) => b - a)
            .map(([seg, count]: [string, any]) => {
              const max = Math.max(...Object.values(summary.segments || {}).map(Number))
              const pct = max > 0 ? (Number(count) / max) * 100 : 0
              return (
                <div key={seg} className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono w-20 truncate">{seg}</span>
                  <div className="flex-1 bg-gray-100 rounded h-2">
                    <div className="bg-blue-300 h-2 rounded" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-gray-600 w-8 text-right">{String(count)}</span>
                </div>
              )
            })}
        </div>
      </div>

      {/* Field Breakdown */}
      <div>
        <h3 className="text-xs text-gray-500 mb-2 uppercase">By Field</h3>
        <div className="max-h-40 overflow-auto">
          {Object.entries(summary.fields || {})
            .sort(([,a]: any, [,b]: any) => b - a)
            .map(([field, count]: [string, any]) => {
              const max = Math.max(...Object.values(summary.fields || {}).map(Number))
              const pct = max > 0 ? (Number(count) / max) * 100 : 0
              return (
                <div key={field} className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono w-24 truncate">{field}</span>
                  <div className="flex-1 bg-gray-100 rounded h-2">
                    <div className="bg-blue-300 h-2 rounded" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-gray-600 w-8 text-right">{String(count)}</span>
                </div>
              )
            })}
        </div>
      </div>

      {/* Top 10 Errors */}
      <div>
        <h3 className="text-xs text-gray-500 mb-2 uppercase">Top Errors</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-1 pr-2">Segment</th>
              <th className="py-1 pr-2">Field</th>
              <th className="py-1 pr-2 text-right">Count</th>
            </tr>
          </thead>
          <tbody>
            {(summary.top_errors || []).map((e: any, i: number) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-1 pr-2 font-mono">{e.segment}</td>
                <td className="py-1 pr-2 font-mono">{e.field}</td>
                <td className="py-1 pr-2 text-right">{e.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </div>
)}
```

**Test gate:**
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

**Repair loop:** If build fails:
- TypeScript errors on `Object.entries()` — ensure explicit typing with `[string, any]`
- JSX key errors — ensure all `.map()` calls have `key` props
- Fix and re-build. Do not proceed until green.

**Manual verification:**
1. Select a run with mismatches → verify all 4 quadrants populate
2. Verify severity bars are proportionally sized (largest = 100% width)
3. Verify segment/field lists are scrollable if >5 entries
4. Verify top errors table shows up to 10 rows

**Commit:** `feat(portal-ui): add summary statistics panel with inline bar charts`

---

## Task B3: Run Diff via Checkbox Selection

**Investigate:**
```bash
# Read portal/api/routes/compare.py — diff_runs() response shape:
# { new_errors: [{segment, field, severity, ...}], resolved_errors: [...], changed_errors: [...], unchanged_count: int }
```

**Execute:**
1. Read `portal/ui/src/pages/Compare.tsx`
2. Add state:
   ```ts
   const [checkedRuns, setCheckedRuns] = useState<Set<number>>(new Set())
   const [runDiff, setRunDiff] = useState<any>(null)
   const [diffLoading, setDiffLoading] = useState(false)
   ```
3. Add checkbox toggle handler:
   ```ts
   const toggleRunCheck = (runId: number) => {
     setCheckedRuns(prev => {
       const next = new Set(prev)
       if (next.has(runId)) {
         next.delete(runId)
       } else if (next.size < 2) {
         next.add(runId)
       }
       return next
     })
   }
   ```
4. Add diff handler:
   ```ts
   const diffSelectedRuns = async () => {
     const ids = Array.from(checkedRuns).sort((a, b) => a - b)
     if (ids.length !== 2) return
     setDiffLoading(true)
     setError('')
     try {
       setRunDiff(await api.compareRunDiff(ids[0], ids[1]))
     } catch (e: any) {
       setError(e.message)
     } finally {
       setDiffLoading(false)
     }
   }
   ```
5. Modify the Run History table:
   - Add checkbox column header:
     ```tsx
     <th className="py-1 pr-2 w-8"></th>
     ```
   - Add checkbox cell as first column in each row:
     ```tsx
     <td className="py-1 pr-2" onClick={e => e.stopPropagation()}>
       <input
         type="checkbox"
         checked={checkedRuns.has(r.run_id)}
         onChange={() => toggleRunCheck(r.run_id)}
         disabled={!checkedRuns.has(r.run_id) && checkedRuns.size >= 2}
         className="rounded"
       />
     </td>
     ```
6. Add "Diff Selected" button above the run history table, shown when exactly 2 are checked:
   ```tsx
   {checkedRuns.size === 2 && (
     <button
       onClick={diffSelectedRuns}
       disabled={diffLoading}
       className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 mb-2"
     >
       {diffLoading ? 'Comparing...' : 'Diff Selected'}
     </button>
   )}
   ```
7. Add Run Diff results panel after the Run History card, shown when `runDiff` is not null:

```tsx
{runDiff && (
  <div className="bg-white rounded-lg shadow p-4 mb-4">
    <div className="flex items-center justify-between mb-3">
      <h2 className="font-semibold text-sm text-gray-500 uppercase">
        Run Diff: {Array.from(checkedRuns).sort((a,b)=>a-b).join(' vs ')}
      </h2>
      <button onClick={() => setRunDiff(null)} className="text-gray-400 hover:text-gray-600 text-sm">&times; Close</button>
    </div>
    <div className="grid grid-cols-4 gap-3 mb-4">
      <div className="bg-red-50 rounded p-3 text-center">
        <div className="text-2xl font-bold text-red-600">{runDiff.new_errors?.length || 0}</div>
        <div className="text-xs text-gray-500">New Errors</div>
      </div>
      <div className="bg-green-50 rounded p-3 text-center">
        <div className="text-2xl font-bold text-green-600">{runDiff.resolved_errors?.length || 0}</div>
        <div className="text-xs text-gray-500">Resolved</div>
      </div>
      <div className="bg-yellow-50 rounded p-3 text-center">
        <div className="text-2xl font-bold text-yellow-600">{runDiff.changed_errors?.length || 0}</div>
        <div className="text-xs text-gray-500">Changed</div>
      </div>
      <div className="bg-gray-50 rounded p-3 text-center">
        <div className="text-2xl font-bold text-gray-600">{runDiff.unchanged_count || 0}</div>
        <div className="text-xs text-gray-500">Unchanged</div>
      </div>
    </div>

    {/* Detail tables for new/resolved/changed */}
    {runDiff.new_errors?.length > 0 && (
      <div className="mb-3">
        <h3 className="text-xs text-gray-500 uppercase mb-1">New Errors</h3>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-gray-500 border-b">
            <th className="py-1 pr-2">Segment</th><th className="py-1 pr-2">Field</th><th className="py-1 pr-2">Severity</th>
          </tr></thead>
          <tbody>
            {runDiff.new_errors.map((e: any, i: number) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-1 pr-2 font-mono text-xs">{e.segment}</td>
                <td className="py-1 pr-2 font-mono text-xs">{e.field}</td>
                <td className="py-1 pr-2"><StatusBadge status={e.severity} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}

    {runDiff.resolved_errors?.length > 0 && (
      <div className="mb-3">
        <h3 className="text-xs text-gray-500 uppercase mb-1">Resolved Errors</h3>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-gray-500 border-b">
            <th className="py-1 pr-2">Segment</th><th className="py-1 pr-2">Field</th><th className="py-1 pr-2">Severity</th>
          </tr></thead>
          <tbody>
            {runDiff.resolved_errors.map((e: any, i: number) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-1 pr-2 font-mono text-xs">{e.segment}</td>
                <td className="py-1 pr-2 font-mono text-xs">{e.field}</td>
                <td className="py-1 pr-2"><StatusBadge status={e.severity} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}

    {runDiff.changed_errors?.length > 0 && (
      <div className="mb-3">
        <h3 className="text-xs text-gray-500 uppercase mb-1">Changed Errors</h3>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-gray-500 border-b">
            <th className="py-1 pr-2">Segment</th><th className="py-1 pr-2">Field</th>
            <th className="py-1 pr-2">Old</th><th className="py-1 pr-2">New</th>
          </tr></thead>
          <tbody>
            {runDiff.changed_errors.map((e: any, i: number) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-1 pr-2 font-mono text-xs">{e.segment}</td>
                <td className="py-1 pr-2 font-mono text-xs">{e.field}</td>
                <td className="py-1 pr-2"><StatusBadge status={e.old_severity || e.severity_a} /></td>
                <td className="py-1 pr-2"><StatusBadge status={e.new_severity || e.severity_b} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
)}
```

**Test gate:**
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

**Repair loop:** If build fails:
- Set type errors: ensure `Set<number>` is used correctly
- `Array.from()` on Set: TypeScript may need explicit typing
- Fix and re-build. Do not proceed until green.

**Manual verification:**
1. Check two runs in history → "Diff Selected" button appears
2. Click Diff Selected → verify 4 metric cards display
3. Verify new/resolved/changed detail tables show when arrays are non-empty
4. Verify checking a 3rd run is blocked (checkbox disabled)
5. Uncheck a run → "Diff Selected" button disappears
6. Close diff results → panel hides

**Commit:** `feat(portal-ui): add run diff view with checkbox selection`

---

## Phase B Gate

```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Build passes. All Runs tab features work: reclassify, summary, run diff. **Proceed to Phase C.**

---

# PHASE C: Discoveries Tab

> **Prerequisite:** Phase B gate green.
> **Deliverables:** Full discoveries panel in the Discoveries tab.

---

## Task C1: Discoveries Panel

**Investigate:**
```bash
# Read portal/api/routes/compare.py — list_discoveries() and apply_discovery_endpoint()
# Response shape: [{ id, run_id, profile, segment, field, source_value, target_value, suggested_severity, applied, discovered_at }]
# Read portal/api/models.py — DiscoveryResponse fields
```

**Execute:**
1. Read `portal/ui/src/pages/Compare.tsx`
2. Add state:
   ```ts
   const [discoveries, setDiscoveries] = useState<any[]>([])
   const [discoveryFilter, setDiscoveryFilter] = useState<string>('all') // 'all' | 'pending' | 'applied'
   const [discoveryLoading, setDiscoveryLoading] = useState(false)
   const [applyingId, setApplyingId] = useState<number | null>(null)
   ```
3. Add discovery loader:
   ```ts
   const loadDiscoveries = async () => {
     if (!selectedProfile) return
     setDiscoveryLoading(true)
     try {
       const applied = discoveryFilter === 'all' ? undefined : discoveryFilter === 'applied'
       setDiscoveries(await api.compareDiscoveries(selectedProfile, applied))
     } catch (e: any) {
       setError(e.message)
     } finally {
       setDiscoveryLoading(false)
     }
   }
   ```
4. Add apply handler:
   ```ts
   const applyDiscovery = async (id: number) => {
     setApplyingId(id)
     setError('')
     try {
       await api.compareApplyDiscovery(id)
       loadDiscoveries()
     } catch (e: any) {
       setError(e.message)
     } finally {
       setApplyingId(null)
     }
   }
   ```
5. Add `useEffect` to load discoveries when switching to discoveries tab or when filter/profile changes:
   ```ts
   useEffect(() => {
     if (view === 'discoveries' && selectedProfile) {
       loadDiscoveries()
     }
   }, [view, selectedProfile, discoveryFilter])
   ```
6. Replace the placeholder `{view === 'discoveries' && (...)}` block from Task A2 with the full panel:

```tsx
{view === 'discoveries' && (
  <div className="bg-white rounded-lg shadow p-4">
    <h2 className="font-semibold text-sm text-gray-500 uppercase mb-3">Error Discoveries</h2>

    {/* Profile selector */}
    <div className="mb-3">
      <label className="block text-xs text-gray-500 mb-1">Profile</label>
      <select
        className="border rounded px-3 py-1.5 text-sm"
        value={selectedProfile}
        onChange={e => setSelectedProfile(e.target.value)}
      >
        <option value="">Select profile...</option>
        {profiles.map(p => (
          <option key={p.name} value={p.name}>{p.name}</option>
        ))}
      </select>
    </div>

    {!selectedProfile ? (
      <p className="text-sm text-gray-400">Select a profile to view discoveries.</p>
    ) : (
      <>
        {/* Filter buttons */}
        <div className="flex gap-1 mb-3">
          {['all', 'pending', 'applied'].map(f => (
            <button
              key={f}
              onClick={() => setDiscoveryFilter(f)}
              className={`px-2 py-0.5 rounded text-xs capitalize ${discoveryFilter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {f}
            </button>
          ))}
        </div>

        {discoveryLoading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : discoveries.length === 0 ? (
          <p className="text-sm text-gray-400">No discoveries found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-1 pr-2">Segment</th>
                <th className="py-1 pr-2">Field</th>
                <th className="py-1 pr-2">Source Value</th>
                <th className="py-1 pr-2">Target Value</th>
                <th className="py-1 pr-2">Severity</th>
                <th className="py-1 pr-2">Status</th>
                <th className="py-1 pr-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {discoveries.map(d => (
                <tr key={d.id} className="border-b border-gray-50">
                  <td className="py-1 pr-2 font-mono text-xs">{d.segment}</td>
                  <td className="py-1 pr-2 font-mono text-xs">{d.field}</td>
                  <td className="py-1 pr-2 text-xs">{d.source_value ?? '—'}</td>
                  <td className="py-1 pr-2 text-xs">{d.target_value ?? '—'}</td>
                  <td className="py-1 pr-2"><StatusBadge status={d.suggested_severity} /></td>
                  <td className="py-1 pr-2">
                    {d.applied
                      ? <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Applied</span>
                      : <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">Pending</span>
                    }
                  </td>
                  <td className="py-1 pr-2">
                    {!d.applied && (
                      <button
                        onClick={() => applyDiscovery(d.id)}
                        disabled={applyingId === d.id}
                        className="bg-green-600 text-white px-2 py-0.5 rounded text-xs hover:bg-green-700 disabled:opacity-50"
                      >
                        {applyingId === d.id ? '...' : 'Apply'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </>
    )}
  </div>
)}
```

**Test gate:**
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

**Repair loop:** If build fails:
- Missing `loadDiscoveries` in `useEffect` deps: React hooks lint warning — add to dependency array or restructure
- `useEffect` calling loadDiscoveries before it's defined: ensure function is declared before the useEffect
- Fix and re-build. Do not proceed until green.

**Manual verification:**
1. Switch to Discoveries tab → select a profile → verify table loads
2. Click Apply on a pending discovery → verify it refreshes and shows "Applied" badge
3. Toggle filter to Applied → verify only applied rows show
4. Toggle filter to Pending → verify the applied one is gone
5. Switch to a profile with no discoveries → verify "No discoveries found" message
6. Switch back to Runs tab → verify all existing functionality still works
7. Switch back to Discoveries → verify state persists (profile selection, filter)

**Commit:** `feat(portal-ui): add error discoveries tab with apply workflow`

---

## Phase C Gate

```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

---

# PHASE D: Completeness Check + Polish

> **Prerequisite:** Phase C gate green.
> **Deliverables:** Verified end-to-end integration, state cleanup, edge cases.

---

## Task D1: State Cleanup and Edge Cases

**Execute:**
1. Read `portal/ui/src/pages/Compare.tsx` — full file
2. Verify these state cleanup behaviors exist (add if missing):
   - When `selectedProfile` changes: clear `discoveries` array, reset `discoveryFilter` to `'all'`
   - When switching from `discoveries` to `runs` tab: clear `discoveries` (optional — may keep for fast switching)
   - When `selectRun()` is called: clear `summary` (`setSummary(null)`)
   - When `checkedRuns` is modified: clear `runDiff` (`setRunDiff(null)`)
3. Verify no runtime console errors by building and visually reviewing code for:
   - Unhandled null/undefined access (use `?.` and `|| []` patterns)
   - Missing keys in `.map()` calls
   - Event handler `e.stopPropagation()` on checkbox clicks (prevent row click)
4. Verify the `useEffect` for discoveries doesn't fire on mount when view is 'runs' (it should be guarded by `if (view === 'discoveries' && selectedProfile)`)

**Test gate:**
```bash
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..
```

**Commit:** `fix(portal-ui): add state cleanup for tab switching and edge cases`

---

## Task D2: Full End-to-End Verification

This is a manual verification task. Run through every feature added in Phases A-C.

**Start services:**
```bash
# Terminal 1: start FastAPI backend
cd portal && uvicorn api.main:app --reload --port 8000

# Terminal 2: start React dev server
cd portal/ui && npm run dev
```

**Checklist — execute each step and verify:**

```
[ ] 1. Open browser to http://localhost:5173
[ ] 2. Navigate to Compare page
[ ] 3. Verify Runs/Discoveries tab toggle appears
[ ] 4. Verify Runs tab is active by default
[ ] 5. Select a profile from the dropdown
[ ] 6. Enter source and target directories for a comparison
[ ] 7. Click Run Comparison → verify new run appears in history
[ ] 8. Select the new run → verify pairs load AND summary panel appears below pairs
[ ] 9. Verify summary has 4 quadrants: Severity (with colored bars), Segments (with bars), Fields (with bars), Top Errors (table)
[ ] 10. Click a mismatched pair → verify diffs table appears below summary
[ ] 11. Click Reclassify → verify new run appears with purple "re:N" badge
[ ] 12. Check two runs via checkboxes → verify "Diff Selected" button appears
[ ] 13. Click Diff Selected → verify 4 metric cards (New/Resolved/Changed/Unchanged)
[ ] 14. Verify detail tables appear below metrics for non-empty categories
[ ] 15. Close diff panel → verify it disappears
[ ] 16. Click Export CSV → verify CSV downloads
[ ] 17. Click Edit Rules → verify rules editor opens
[ ] 18. Switch to Discoveries tab
[ ] 19. Select a profile → verify discoveries table loads
[ ] 20. Verify filter buttons (All/Pending/Applied) work
[ ] 21. Click Apply on a pending discovery → verify it refreshes with Applied badge
[ ] 22. Switch back to Runs tab → verify all run data still visible
[ ] 23. Verify no console errors in browser devtools
```

**If any step fails:**
1. Read the browser console error or network error
2. Read the relevant section of Compare.tsx
3. Fix the issue
4. Re-run the failing step and all subsequent steps
5. Re-run build: `cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..`
6. Commit the fix: `fix(portal-ui): <description of what was fixed>`

---

## Task D3: Final Test Gate

```bash
# All Python tests green (backend unchanged)
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
python -m pytest portal/tests/ -v --tb=short 2>/dev/null || echo "No portal tests"

# UI build clean
cd portal/ui && npm run build 2>&1 | tail -5 && cd ../..

# CLI still works (not impacted, but verify no regressions)
python -m pycoreedi compare --list-profiles --config config/config.yaml
python -m pycoreedi compare --profile bevager_810 --source-dir outbound/bevager/control --target-dir outbound/bevager/test -v
```

**Commit (if any final fixes):** `fix(portal-ui): final polish for comparator UI integration`

---

# FINAL GATE

All phases complete. Verify the full implementation:

```bash
# 1. Python tests green
python -m pytest tests/ -v --tb=short

# 2. UI builds clean
cd portal/ui && npm run build && cd ../..

# 3. API methods count: should be 26 (21 original + 5 new)
grep -c "request<" portal/ui/src/api.ts

# 4. Compare.tsx features present (spot check)
grep -c "compareReclassify\|compareRunDiff\|compareRunSummary\|compareDiscoveries\|compareApplyDiscovery" portal/ui/src/pages/Compare.tsx

# 5. No leftover placeholder text
grep -c "coming in Phase" portal/ui/src/pages/Compare.tsx
# Should be 0
```

All gates pass. Implementation complete.

---

## Summary of Changes

| File | Lines Added | Features |
|------|-------------|----------|
| `portal/ui/src/api.ts` | ~20 | 5 new API method wrappers |
| `portal/ui/src/pages/Compare.tsx` | ~220 | Tab toggle, reclassify button + badge, summary panel with bars, run diff with checkboxes, discoveries panel with apply workflow |

| Backend File | Changes |
|--------------|---------|
| None | All endpoints already implemented |
