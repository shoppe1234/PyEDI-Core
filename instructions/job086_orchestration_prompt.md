# JOB-086 — Orchestration Prompt: INC-184 (EmptyState co-render) + INC-186 (skeleton-forever)

> **Scope:** Two rendering bugs in `portal/ui/src/pages/Compare.tsx`. No other files need changes.
> **Execute tasks sequentially. Read the file before each edit. Type-check after all edits.**

---

## Pre-Flight

```bash
cd portal/ui && npx tsc --noEmit
```
Note the current error count (baseline). All tasks must leave it at zero or lower.

---

## TASK-1 — INC-184: Empty filtered-pairs message

**File:** `portal/ui/src/pages/Compare.tsx`

**Problem:** When `pairs.length > 0` but client-side text filters (sourceFileFilter, targetFileFilter, matchValueFilter) produce an empty `filteredPairs`, the `<table>` branch renders — showing the header row with filter inputs — but `<tbody>` is empty. Users see table chrome with no rows: a co-render of content state and empty state.

**Root cause:** The ternary at line 570 only gates on `pairs.length === 0`, not on `filteredPairs.length === 0`.

**Fix:** Inside `<tbody>` (line 616), add a zero-results guard before `filteredPairs.map(...)`:

```tsx
<tbody>
  {filteredPairs.length === 0 ? (
    <tr>
      <td colSpan={5} className="py-3 text-center text-sm text-gray-400">
        No pairs match the current filter.
      </td>
    </tr>
  ) : (
    filteredPairs.map(p => (
      // ... existing row JSX unchanged ...
    ))
  )}
</tbody>
```

**Verify:** After the edit, confirm `filteredPairs.map(p => (` is now inside the `else` branch, not at the top level of `<tbody>`.

---

## TASK-2 — INC-186: Split loading flags

**File:** `portal/ui/src/pages/Compare.tsx`

**Problem:** A single `loading` state flag is shared by:
1. `selectRun` — fetches pairs + summary
2. `filterPairs` — re-fetches pairs on status filter
3. `selectPair` — fetches diffs for a clicked pair

When `selectPair` runs, it sets `loading=true`, which hides the entire pairs panel (line 570: `{loading ? <p>Loading...</p> : ...}`) — users lose the pair list while diffs load. This is the co-render/hide regression.

**Fix — Step A: Rename `loading` → `pairsLoading`**

Find every occurrence of `loading` and `setLoading` and rename to `pairsLoading` / `setPairsLoading`. Scope: the `useState` declaration and all references in `selectRun`, `filterPairs`, and the pairs-panel JSX at line 570.

Do NOT rename the `loading` reference inside `selectPair` — that function will use a new flag (Step B).

**Fix — Step B: Add `diffsLoading` state**

After the (now renamed) `pairsLoading` useState declaration, add:
```ts
const [diffsLoading, setDiffsLoading] = useState(false)
```

**Fix — Step C: Update `selectPair`**

Replace `setLoading(true)` / `setLoading(false)` inside `selectPair` with `setDiffsLoading(true)` / `setDiffsLoading(false)`.

**Fix — Step D: Update diffs-panel JSX**

Find the diffs-panel section (guarded by `selectedPair &&`). Any "Loading..." spinner or conditional that currently checks `loading` for diffs display must now check `diffsLoading`. If there is no explicit loading guard on the diffs panel, add one:
```tsx
{selectedPair && (
  <div className="bg-white rounded-lg shadow p-4 mb-4">
    <h2 className="font-semibold text-sm text-gray-500 uppercase mb-2">
      Diffs — Pair #{selectedPair.id}
    </h2>
    {diffsLoading ? (
      <p className="text-sm text-gray-400">Loading diffs...</p>
    ) : diffs.length === 0 ? (
      <p className="text-sm text-gray-400">No diffs.</p>
    ) : (
      // existing diffs table JSX
    )}
  </div>
)}
```

**Verify:** After Step A–D, search the file for any remaining bare `loading` or `setLoading` references (not `pairsLoading`/`diffsLoading`) — there should be none.

---

## TASK-3 — INC-186: Parallelize `selectRun` fetches

**File:** `portal/ui/src/pages/Compare.tsx`

**Problem:** In `selectRun` (line 134–136), the two API calls are sequential:
```ts
setPairs(await api.comparePairs(run.run_id))
setSummary(await api.compareRunSummary(run.run_id))
```
If `compareRunSummary` hangs (no resolve, no reject), the `finally` block never runs and `pairsLoading` stays `true` forever — the "Loading..." message never clears.

**Fix:** Replace the sequential awaits with `Promise.all`:

```ts
const [fetchedPairs, fetchedSummary] = await Promise.all([
  api.comparePairs(run.run_id),
  api.compareRunSummary(run.run_id),
])
setPairs(fetchedPairs)
setSummary(fetchedSummary)
```

The `catch` and `finally` blocks are unchanged. `Promise.all` rejects on first error and settles (resolves or rejects) when both calls finish, so `finally { setPairsLoading(false) }` is guaranteed to run.

**Verify:** The try block inside `selectRun` should now contain exactly one `await` expression (`Promise.all`), followed by two `set*` calls.

---

## TASK-4 — TypeScript check

```bash
cd portal/ui && npx tsc --noEmit
```

Must produce **zero errors**. Fix any type errors before proceeding (do not skip).

Common issues to check:
- `filteredPairs` typed correctly (same type as `pairs`)
- `diffsLoading` declared with explicit `boolean` type if inference fails
- `Promise.all` return tuple destructuring matches the API return types

---

## TASK-5 — Manual smoke test (if dev server is running)

1. Open Compare page, select a run → pairs table appears, "Loading..." clears.
2. Type a filter value that matches nothing → "No pairs match the current filter." appears inside the table, filter inputs remain visible.
3. Clear the filter → full pairs list reappears.
4. Click a MISMATCH pair → diffs panel shows "Loading diffs..." briefly; **pairs table stays visible and does not collapse to "Loading..."**.
5. Diffs load → diffs panel populates.

If dev server is not running, skip TASK-5 and note it.

---

## Files Modified

| File | Tasks |
|------|-------|
| `portal/ui/src/pages/Compare.tsx` | 1, 2, 3 |
