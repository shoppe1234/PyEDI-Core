# Orchestration: X12 204 Compare Support + Silent-Failure Fix

You are a precise Python engineer working in `C:\Users\SeanHoppe\VS\pycoreEdi`. Follow `CLAUDE.md` strictly (minimal diffs, type hints, specific exceptions, match existing patterns, no unsolicited refactors).

## Context

**Symptom:** Compare run #109, profile `204a`, source `C:\Users\SeanHoppe\Downloads\pycoreEDI\204\00\ca` and target `...\na` each contain `DUPR-204-00.edi`. Result: `total_pairs=0, matched=0, mismatched=0, unmatched=0` — silent.

**Root-cause hypothesis:**
- `204` not registered in `config/config.yaml` `transaction_registry` (lines 20–34).
- Parser falls to `_default_x12` (raw-segment passthrough) → match_key `B2.B201` unresolvable.
- Matcher in `pyedi_core/comparator/matcher.py:200–228` silently skips parse failures → `total_pairs=0` with no diagnostic surfaced to portal or DB.

**Scope chosen (user-approved): B + D, B first.**
- **B** = Author proper `rules/x12_204_map.yaml` covering 4010 + 5010, register it.
- **D** = Loud-fail (soft): persist parse/setup errors to `compare_runs.run_notes`, return run with 0 pairs so the portal surfaces "0 transactions parsed — registry missing tx_type X" instead of silent zeros.

**Decisions already made (do NOT re-ask):**
- 204 version: 4010 baseline, account for 5010 differences.
- D behavior: soft-fail — persist error to `run_notes`, return run; do NOT raise.
- Order: complete all B tasks first, checkpoint, then D.

## Task list (execute in order)

### Phase B — 204 Map + Registration
1. **B1** — Read `pyedi_core/rules/default_x12_map.yaml` and `pyedi_core/rules/gfs_850_map.yaml` to match the exact map schema shape (keys: `transaction_type`, `input_format`, `x12_version`, `schema`, `mapping.{header,lines,summary}` with `source: 'SEG.NN'`).
2. **B2** — Read `pyedi_core/handlers/x12_handler.py` and `pyedi_core/pipeline.py` (around lines 564 and 582) to confirm exactly which map keys the handler consumes and how transaction_type lookup works. Also read `pyedi_core/comparator/engine.py:200–246` and `pyedi_core/comparator/matcher.py:200–258` to confirm whether the comparator reads the **raw X12 segment tree** or the **mapped output** when resolving `match_key.segment/field`. This determines the map's required shape.
3. 🛑 **CHECKPOINT 1** — Stop. Report: map schema confirmed, what the comparator reads (raw tree vs mapped), any shape surprises. Wait for user confirm before B3.
4. **B3** — Author `rules/x12_204_map.yaml` (note: create under `pyedi_core/rules/` if that is where other maps live, matching whatever directory `transaction_registry` paths resolve from). Cover 204 Motor Carrier Load Tender segments: `ST, B2, B2A, L11, G62, MS3, N1 loop (N1/N2/N3/N4/G61), S5, OID, LAD/AT8, NTE, L3, SE`. Include both 4010 and 5010 field positions where they differ (comment inline only if a field position is version-specific — per CLAUDE.md rule default-no-comments, but this qualifies as non-obvious WHY).
5. **B4** — Register in `config/config.yaml` `transaction_registry` (alphabetical/numerical position near existing entries): add `'204': ./rules/x12_204_map.yaml` (adjust prefix to match what's there).
6. **B5** — Launch portal (existing commands), trigger compare with profile `204a`, src `C:\Users\SeanHoppe\Downloads\pycoreEDI\204\00\ca`, tgt `...\na`. Verify new run has `total_pairs >= 1` and at least one pair is `MATCH` or `MISMATCH` (not just `unmatched`).
7. 🛑 **CHECKPOINT 2** — Stop. Report: new run id, total_pairs, matched/mismatched/unmatched, any diff rows. Wait for user confirm before Phase D.

### Phase D — Soft-Fail Visibility
8. **D1** — Read `pyedi_core/comparator/matcher.py` around `pair_transactions()` (lines 200–258) and `pyedi_core/comparator/__init__.py:142` where `total_pairs=len(pairs)` is set. Identify the exact silent-skip site.
9. **D2** — Grep `pyedi_core/handlers/` and `pyedi_core/pipeline.py` for the specific exception classes raised on parse failure (e.g., `X12ParseError`, `ValidationError`, `KeyError` from registry miss). CLAUDE.md rule #8: no bare `except`. Pick specific classes.
10. **D3** — Modify matcher to:
    - Catch specific parse exceptions per-file; log via existing logger with file path + tx_type + registry hit/miss.
    - Accumulate error strings into a list.
    - After loop, if index empty: compose a setup-error message ("0 transactions parsed from <dir>; transaction_type '<tt>' registered=<bool>; per-file errors: ...").
    - Persist to `compare_runs.run_notes` via the existing store path in `store.py`.
    - Return the run with `total_pairs=0` (do NOT raise). Match existing run-persistence pattern.
11. 🛑 **CHECKPOINT 3** — Stop. Report the diff for matcher.py + store.py (if touched). Wait for user confirm before D4.
12. **D4** — Verify two cases via portal:
    - (a) Point compare at a dir with no `.edi` files → run row has `total_pairs=0` and `run_notes` contains the setup error.
    - (b) Re-run 204a compare (valid dirs) → unchanged behavior from B5 (no regression).
13. 🛑 **CHECKPOINT 4 (FINAL)** — Stop. Report: both verification cases, list of files changed, suggested commit message. Wait for user before committing.

## Operating rules (CLAUDE.md derived)

- **Read before write.** Always read target file and its imports before editing.
- **Minimal diffs.** Only change what the task requires. No refactors, renames, cleanup.
- **One task per response.** Do not batch unrelated modifications.
- **Checkpoints are mandatory stops.** Do not proceed past 🛑 until user confirms. This prevents compounding errors across phases.
- **Match existing patterns.** Map schema, rule file format, store API, logger usage — follow what 810/850 do.
- **Specific exceptions only.** No bare `except`. If unsure of class, grep the raise sites (D2).
- **Type hints required** on any new/modified function signatures.
- **Terse communication.** No preamble, no trailing summaries. Lead with action/result.
- **When stuck, stop and ask.** Do not guess schema fields or exception types.
- **No speculative fixes.** If B5 fails for a reason other than the hypothesis, stop and report — do not layer on more changes.

## Success criteria

- `config/config.yaml` has `'204': ./rules/x12_204_map.yaml` in `transaction_registry`.
- `rules/x12_204_map.yaml` (or `pyedi_core/rules/...`) exists, matches existing map shape, covers 4010 + 5010.
- Compare run with profile `204a` produces `total_pairs >= 1`.
- Matcher persists setup/parse errors to `compare_runs.run_notes` when zero transactions parse.
- No regression in existing 810/850/855 runs.
- No bare `except`, no unrelated refactors, no new dependencies.

## Out of scope

- Option A (stopgap registry-only) and Option C (rewriting `_default_x12` handler) — explicitly rejected.
- UI/portal changes beyond verifying the run rows — the portal already surfaces `run_notes`.
- Other transaction types (214, 990, 210, 997). Those come later if user asks.
