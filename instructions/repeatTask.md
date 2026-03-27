# Repeatable Compare / Retest Workflow

## Problem Statement

After errors are reported and fixed, developers and QA need to quickly retest comparisons — often with the same control data but different sample data, and sometimes swapping both. The current framework supports one-off runs but lacks first-class support for repeatable retests.

---

## Current Framework Capabilities

| Capability | How it works today | Gap |
|---|---|---|
| **Run a comparison** | CLI: `python -m pycoreedi compare --profile X --source-dir A --target-dir B` / UI: fill form + click "Run Comparison" | Must re-enter paths every time |
| **Reclassify a run** | CLI: `--reclassify-run {ID}` / UI: "Reclassify" button | Re-evaluates diffs against *current rules* on the *same data* — no new sample data |
| **Diff two runs** | CLI: `--diff-runs A B` / UI: checkbox + "Diff Selected" | Shows new/resolved/changed errors between runs — good for regression, but no lineage |
| **Export CSV** | CLI: `--export-csv` / UI: "Export CSV" link | Snapshot only, not re-runnable |
| **Profiles** | YAML config with match_key, qualifiers, rules_file | Reusable across runs, but paths are not saved |

---

## Proposed Enhancements

### 1. Comparison Presets (Saved Configurations)

**What:** Named presets that store profile + source dir + target dir + optional overrides as a reusable config.

**Schema (config.yaml or SQLite):**
```yaml
compare_presets:
  bevager_daily:
    profile: "810_invoice"
    source_dir: "/data/control/bevager"
    target_dir: "/data/samples/bevager/latest"
    description: "BevAger 810 daily retest"
  bevager_regression:
    profile: "810_invoice"
    source_dir: "/data/control/bevager"
    target_dir: "/data/regression/bevager"
    description: "BevAger 810 regression suite"
```

**UI changes:**
- Dropdown to select a saved preset (auto-fills profile, source, target)
- "Save as Preset" button next to the run form
- Edit/delete presets from a management panel

**CLI changes:**
```bash
python -m pycoreedi compare --preset bevager_daily
python -m pycoreedi compare --list-presets
python -m pycoreedi compare --save-preset bevager_daily --profile 810_invoice --source-dir ... --target-dir ...
```

**Questions to resolve:**
- Store presets in `config.yaml` (static, version-controlled) or SQLite (dynamic, UI-managed)?
- Allow preset to override `target_dir` at runtime? (e.g., `--preset X --target-dir /new/path`)

---

### 2. "Re-run" Button with Lineage Tracking

**What:** A one-click re-run from a previous run, pre-filling the same profile and source dir but allowing the user to swap the target dir. The new run records `retest_of` linking back to the original.

**Schema addition (compare_runs table):**
```sql
ALTER TABLE compare_runs ADD COLUMN retest_of INTEGER REFERENCES compare_runs(id);
```

This is distinct from `reclassified_from` (which re-evaluates the same data with new rules). `retest_of` means "new data, same test scenario."

**UI changes:**
- "Re-run" button on each run row (next to the existing checkbox)
- Clicking it opens the run form pre-filled with the original profile + source dir
- Target dir defaults to the original but is editable (swap in new sample data)
- After the run completes, a badge shows `retest of #42` (similar to the existing `re:42` badge for reclassifications)

**CLI changes:**
```bash
python -m pycoreedi compare --retest-run 42 --target-dir /new/samples
python -m pycoreedi compare --retest-run 42  # uses same target dir
```

---

### 3. Swap Source / Target Support

**What:** Allow swapping which directory is "control" vs "sample" for bidirectional testing.

**UI change:** A swap icon button between the source/target fields that swaps the two values.

**CLI:**
```bash
python -m pycoreedi compare --preset bevager_daily --swap
```

---

### 4. Quick Retest from Run History

**What:** Right-click or action menu on a run row with options:
- **Re-run (same data)** — exact same profile + source + target
- **Re-run (new target)** — same profile + source, prompt for new target
- **Re-run (swap)** — flip source and target
- **Reclassify** — existing feature (same data, updated rules)

---

## Implementation Task List

### Phase 1 — Presets (foundation for repeatability)

- [ ] **1.1** Add `compare_presets` table to SQLite schema (name, profile, source_dir, target_dir, description, created_at, updated_at)
- [ ] **1.2** Add CRUD functions in `pyedi_core/comparator/store.py` for presets
- [ ] **1.3** Add API endpoints: `GET/POST/PUT/DELETE /api/compare/presets`
- [ ] **1.4** Add CLI flags: `--preset`, `--list-presets`, `--save-preset`
- [ ] **1.5** Add preset dropdown + "Save as Preset" button to Compare UI
- [ ] **1.6** Add preset management panel (edit/delete) to Compare UI

### Phase 2 — Retest Lineage

- [ ] **2.1** Add `retest_of` column to `compare_runs` table
- [ ] **2.2** Update `insert_run()` in store.py to accept `retest_of`
- [ ] **2.3** Pass `retest_of` through API `POST /api/compare/run` request model
- [ ] **2.4** Add "Re-run" button to run history rows in Compare UI
- [ ] **2.5** Display `retest of #N` badge on runs that have lineage
- [ ] **2.6** Add CLI `--retest-run` flag
- [ ] **2.7** Include lineage chain in run detail / summary views

### Phase 3 — Swap & Quick Actions

- [ ] **3.1** Add swap button between source/target dir fields in Compare UI
- [ ] **3.2** Add `--swap` CLI flag
- [ ] **3.3** Add action menu (re-run / re-run new target / swap / reclassify) on run history rows

### Phase 4 — Polish

- [ ] **4.1** Filter run history by preset name
- [ ] **4.2** Show retest lineage tree (run #42 -> #45 -> #48)
- [ ] **4.3** Add "last used" timestamp to presets for quick-access sorting

---

## Decision Points

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Preset storage | config.yaml vs SQLite | **SQLite** — UI-manageable, no file writes to config |
| 2 | Preset override at runtime | Allow partial overrides | **Yes** — e.g., `--preset X --target-dir /new` swaps just the target |
| 3 | Lineage depth | Flat (one level) vs chain | **Chain** — `retest_of` is a foreign key, supports arbitrary depth |
| 4 | Auto-save last run as preset | Implicit vs explicit | **Explicit** — user clicks "Save as Preset" to avoid clutter |
