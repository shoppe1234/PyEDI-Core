# Root-Level Utility Scripts — Summary & Recommendations

**Date:** 2026-03-17

---

## Scripts Overview

| Script | Purpose | Status | Recommendation |
|--------|---------|--------|----------------|
| `edi_processor.py` | Standalone X12 parser | Superseded | **Remove** |
| `generate_expected.py` | Test fixture generator | Active | **Keep & improve** |
| `generate_marginedge.py` | Single-file fixture generator | Redundant | **Remove** |
| `hello_script.py` | AI tooling smoke test | Stale artifact | **Remove** |
| `verify_environment.py` | Dependency checker | Marginally useful | **Keep / consolidate** |
| `verify_structure.py` | Project structure checker | Marginally useful | **Keep / consolidate** |

---

## Detailed Analysis

### 1. `edi_processor.py` — REMOVE

**What it does:** Parses raw X12 EDI content using `badx12`, normalizes it into sequential JSON (segments/fields), and extracts 810 invoice summaries. Handles both "wrapped" and "unwrapped" EDI formats.

**Why remove:** Fully superseded by `pyedi_core/drivers/x12_handler.py` and the pipeline system. Contains a `collections.Iterable` monkey-patch (same as x12_handler). Broad `except Exception` swallows errors silently. No consumers remain.

**Dependencies:** `json`, `collections`, `collections.abc`, `badx12.Parser`

---

### 2. `generate_expected.py` — KEEP & IMPROVE

**What it does:** Reads test cases from `tests/user_supplied/metadata.yaml`, runs each input through `pyedi_core.Pipeline` in dry-run mode, and writes JSON payloads as expected output files for regression testing.

**Why keep:** Actively needed whenever pipeline logic or schemas change. Core to the testing workflow.

**Issues to fix:**
- Uses relative paths (`'./config/config.yaml'`) — breaks if run from non-root directory
- Ad-hoc fallback on line 23 for "UnivT701 edge cases" is poorly documented
- No CLI arguments, no logging
- **Recommendation:** Fold into the `pyedi test` CLI subcommand (e.g., `pyedi test --generate-expected`)

**Dependencies:** `json`, `shutil`, `os`, `yaml`, `pathlib.Path`, `pyedi_core.Pipeline`

---

### 3. `generate_marginedge.py` — REMOVE

**What it does:** Single-purpose script that generates expected output for one specific file: `NA_810_MARGINEDGE_20260129.txt`. Runs it through the pipeline in dry-run mode.

**Why remove:** Direct subset of `generate_expected.py`. The MarginEdge test case is already in `metadata.yaml`. Hardcoded target file, no parameterization, exact same copy-run-cleanup pattern.

**Dependencies:** `json`, `pathlib.Path`, `pyedi_core.Pipeline`, `shutil`, `os`

---

### 4. `hello_script.py` — REMOVE

**What it does:** Prints `Hello from MiniMax M2.5!`. One line.

**Why remove:** Leftover from an AI coding assistant test. Zero project value.

**Dependencies:** None

---

### 5. `verify_environment.py` — KEEP / CONSOLIDATE

**What it does:** Checks that all required Python packages are importable (`badx12`, `pandas`, `pyyaml`, `pydantic`, `structlog`, `fastapi`, `uvicorn`) and prints their versions. Exits with code 1 if any are missing.

**Why keep:** Useful for onboarding and CI smoke tests, especially since `badx12` is not yet in `pyproject.toml`.

**Issues:**
- Package list is manually maintained — can drift from `pyproject.toml`
- Includes `fastapi`/`uvicorn` (Phase 3, not yet implemented)
- **Recommendation:** Consolidate with `verify_structure.py` into a single `verify.py` or fold into `pyedi test --verify-env`

**Dependencies:** `sys`, `importlib` (stdlib only, by design)

---

### 6. `verify_structure.py` — KEEP / CONSOLIDATE

**What it does:** Checks that all required directories and files exist (e.g., `pyedi_core/`, `config/config.yaml`, all driver and core module files). Exits with code 1 if anything is missing.

**Why keep:** Useful during initial setup and onboarding. Less valuable as the project matures.

**Issues:**
- Hardcoded file list will go stale as project evolves
- Uses relative paths — must run from project root
- **Recommendation:** Consolidate with `verify_environment.py` into a single verification command

**Dependencies:** `os`, `sys` (stdlib only)

---

## Consolidation Plan

```
REMOVE (3 files):
  - edi_processor.py        → superseded by pyedi_core pipeline
  - generate_marginedge.py  → redundant with generate_expected.py
  - hello_script.py         → throwaway artifact

CONSOLIDATE (2 files → 1):
  - verify_environment.py ─┐
  - verify_structure.py   ─┴→ pyedi test --verify  (or standalone verify.py)

ABSORB INTO TEST HARNESS (1 file):
  - generate_expected.py   → pyedi test --generate-expected
```

Net result: 6 root scripts → 0-1 root scripts (functionality moves into `pyedi` CLI)
