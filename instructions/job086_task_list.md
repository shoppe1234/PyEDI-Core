# JOB-086 Task List — INC-184 + INC-186 (Compare.tsx)

## Incidents
- **INC-184** EmptyState co-render: when client-side filters produce zero results from a non-empty `pairs` array, the table renders with headers/inputs visible but an empty `<tbody>` — content skeleton and empty state coexist.
- **INC-186** Skeleton-forever: `loading` is a single shared flag used for both pair-list loading (`selectRun`/`filterPairs`) and diff loading (`selectPair`). Two problems: (a) sequential awaits in `selectRun` mean a hung `compareRunSummary` call keeps `loading=true` forever; (b) clicking a pair to view diffs shows "Loading..." and hides the pairs table.

## File
`portal/ui/src/pages/Compare.tsx`

---

## Tasks

- [ ] **TASK-1 — INC-184: Empty filtered-pairs message**
  - In the `<tbody>` at line 616, when `filteredPairs.length === 0` (but `pairs.length > 0`), render a single `<tr>` with a "No pairs match the current filter." message spanning all 5 columns, instead of an empty tbody.

- [ ] **TASK-2 — INC-186: Split loading flags**
  - Rename `loading` / `setLoading` → `pairsLoading` / `setPairsLoading` (pairs-list concern).
  - Add a new `diffsLoading` / `setDiffsLoading` state (diffs concern).
  - Update `selectRun` and `filterPairs` to use `pairsLoading`.
  - Update `selectPair` to use `diffsLoading`.
  - Update all JSX that gates on `loading` to use the correct flag: pairs panel uses `pairsLoading`; diffs panel uses `diffsLoading`.

- [ ] **TASK-3 — INC-186: Parallelize selectRun fetches**
  - In `selectRun`, replace the sequential `await` chain with `Promise.all`:
    ```ts
    const [fetchedPairs, fetchedSummary] = await Promise.all([
      api.comparePairs(run.run_id),
      api.compareRunSummary(run.run_id),
    ])
    setPairs(fetchedPairs)
    setSummary(fetchedSummary)
    ```
  - This ensures `finally { setPairsLoading(false) }` runs as soon as either call resolves or rejects, preventing an indefinite stuck state.

- [ ] **TASK-4 — TypeScript check**
  - Run `cd portal/ui && npx tsc --noEmit` — zero errors required.

- [ ] **TASK-5 — Manual smoke test**
  - Select a compare run → pairs table loads → verify "Loading..." disappears.
  - Apply a filter that matches nothing → verify "No pairs match the current filter." row appears (not blank tbody).
  - Click a MISMATCH pair → diffs panel loads with `diffsLoading` spinner; pairs table remains visible and un-hidden.
