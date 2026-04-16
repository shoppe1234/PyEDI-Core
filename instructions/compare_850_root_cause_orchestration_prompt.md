# Compare 850 Root Cause — Orchestration Prompt

**Purpose:** Implement the three fixes described in `docs/compare-850-root-cause.md` so that run #89 (profile `sean850`, raw X12 `.txt` source/target dirs) produces `total_pairs: 1` with a detectable N1 diff instead of `total_pairs: 0`.

**Source of truth:** `docs/compare-850-root-cause.md`
**Coding standards:** `CLAUDE.md`, `pycoreEdi/CLAUDE.md`

---

## Rules of Engagement

1. **Sequential** — complete each task fully (including its test gate) before starting the next.
2. **Read before writing** — read the target file before any edit.
3. **Minimal diffs** — only change what the task requires. No drive-by cleanup, no added comments.
4. **Match existing patterns** — follow current conventions in `pyedi_core/comparator/`.
5. **Type hints required** — every new function signature must include type hints.
6. **Explicit exceptions** — no bare `except`.
7. **One commit per task** after its test gate passes.
8. **Stop on red** — if a test gate fails, diagnose root cause before proceeding.

---

## Pre-Flight

```bash
cd ~/VS/pycoreEdi

# Confirm source/target exist and contain raw X12 .txt
ls "C:/Users/SeanHoppe/Downloads/pycoreEDI/ca"
ls "C:/Users/SeanHoppe/Downloads/pycoreEDI/na"

# Confirm profile + rules file
grep -n "sean850" config/config.yaml
cat config/compare_rules/sean850.yaml

# Baseline tests
python -m pytest pyedi_core/comparator -x -q
```

If baseline tests are red, stop and fix before starting Task 1.

---

## Task 1 — Add raw X12 support to `build_match_index`

**File:** `pyedi_core/comparator/matcher.py`

### Scope
- Add a helper `_parse_x12_to_doc(file_path: str) -> dict` that:
  - Reads raw X12 text.
  - Detects element separator from `ISA` segment (`content[3]`) and segment terminator (`content[105]`).
  - Splits into segments, names fields positionally: `{segment_id}{NN:02d}` (e.g. `BEG01`, `BEG03`).
  - Returns:
    ```python
    {
        "document": {"segments": [{"segment": "BEG", "fields": [{"name": "BEG03", "content": "..."}]}]},
        "_transaction_type": "<ST01 value>",
        "_is_unmapped": True,
    }
    ```
- Extend `build_match_index` (currently at `matcher.py:131`) so the extension filter at line 139 accepts `.json`, `.txt`, `.edi`, `.x12`.
- Route `.txt/.edi/.x12` through `_parse_x12_to_doc`; keep existing `.json` path unchanged.
- Handle errors with specific exceptions only (`OSError`, `IndexError`, `ValueError`). Log and skip on failure; never swallow silently.

### Test gate
```bash
python -m pytest pyedi_core/comparator -x -q
python - <<'PY'
from pyedi_core.comparator.matcher import build_match_index
from pyedi_core.comparator.models import MatchKeyConfig
idx = build_match_index(
    r"C:/Users/SeanHoppe/Downloads/pycoreEDI/ca",
    MatchKeyConfig(segment="BEG", field="BEG03"),
)
assert idx, "expected at least one match entry"
print("ca index keys:", list(idx)[:5])
PY
```

Commit: `feat(comparator): scan raw X12 files in build_match_index`

---

## Task 2 — Populate `segment_qualifiers` for `sean850`

**File:** `config/config.yaml` (block starting around line 220)

Replace `segment_qualifiers: {}` with:

```yaml
    segment_qualifiers:
      N1: N101
      REF: REF01
      DTM: DTM01
      PER: PER01
      PO1: null
      N3: null
      N4: null
```

### Test gate
```bash
python - <<'PY'
import yaml
with open("config/config.yaml") as f: cfg = yaml.safe_load(f)
prof = cfg["compare"]["profiles"]["sean850"]
assert prof["segment_qualifiers"].get("N1") == "N101"
assert "PO1" in prof["segment_qualifiers"]
print("OK")
PY
```

Commit: `fix(compare): populate sean850 segment_qualifiers for X12 compare path`

---

## Task 3 — Fix field names in `sean850.yaml`

**File:** `config/compare_rules/sean850.yaml`

Apply the mapping table from `docs/compare-850-root-cause.md`:

| Current | Replace with |
|---|---|
| `BEG.po_number` | `BEG.BEG03` |
| `BEG.po_date` | `BEG.BEG05` |
| `ISA.sender_id` | `ISA.ISA06` |
| `ISA.receiver_id` | `ISA.ISA08` |
| `PO1.line_number` | `PO1.PO101` |
| `PO1.quantity` | `PO1.PO102` |
| `PO1.unit_price` | `PO1.PO104` |
| `PO1.product_id` | `PO1.PO107` |
| `TDS.total_amount` | **delete entire entry** (TDS not in 850) |

Keep the final wildcard entry (`segment: '*' / field: '*'`) unchanged. Keep `ignore: []`.

### Test gate
```bash
python - <<'PY'
import yaml
with open("config/compare_rules/sean850.yaml") as f: r = yaml.safe_load(f)
fields = {(c["segment"], c["field"]) for c in r["classification"]}
assert ("BEG", "BEG03") in fields
assert ("PO1", "PO107") in fields
assert not any(s == "TDS" for s, _ in fields), "TDS must be removed"
print("OK")
PY
```

Commit: `fix(compare): use raw X12 field names in sean850 rules`

---

## Task 4 — Post-development re-test (run #90)

Backend + UI:

```bash
# Ensure API running on :18041 and UI on :15174 (2-port dev setup per project memory)
```

Steps:
1. Browser → `http://localhost:15174/#compare`
2. Source: `C:\Users\SeanHoppe\Downloads\pycoreEDI\ca`
3. Target: `C:\Users\SeanHoppe\Downloads\pycoreEDI\na`
4. Profile: `sean850`
5. Click **Run Comparison**.

### Acceptance (from `docs/compare-850-root-cause.md:136`)
- New run created (id > 89).
- `total_pairs == 1` (up from 0).
- At least one diff recorded against the `N1` segment (`3BREWERS-CENTROPOLIS` vs `3BREWERS`).
- No unhandled exceptions in API logs.

Verify via SQLite:
```bash
sqlite3 data/compare.db "SELECT id,total_pairs,mismatched FROM comparison_runs ORDER BY id DESC LIMIT 1;"
sqlite3 data/compare.db "SELECT segment,field,source_value,target_value FROM comparison_diffs WHERE run_id=(SELECT MAX(id) FROM comparison_runs);"
```

If `total_pairs` is still 0, stop — do not patch symptoms. Re-read each fix against its file and identify which layer silently no-op'd.

---

## Post_development_test (summary)

| Check | Expected |
|---|---|
| `build_match_index` on `ca/` | returns ≥1 entry keyed by BEG03 |
| `sean850.segment_qualifiers` | non-empty dict, `N1 → N101` |
| `sean850.yaml` | uses BEG03/BEG05/PO101/etc; no TDS entry |
| New run via UI | `total_pairs=1`, N1 diff present |

---

## Out of Scope

- Rewriting the pipeline's `read()` stage.
- Adding ediSchema validation (future — noted in `docs/compare-850-root-cause.md:94`).
- Touching other profiles (`costco850`, `bevager810new`, `856sean`).
- UI/portal changes — fix is backend + config only.
