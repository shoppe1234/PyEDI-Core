# Hierarchical Rules Management — Orchestration Prompt

**Purpose:** Introduce a 3-tier rule hierarchy (Universal → Transaction-type → Partner) to the PyEDI compare engine and build a dedicated Rules management page in the portal. This replaces the current flat per-profile rules model with an inherited system where common rules are defined once and partner-specific overrides are layered on top.

**Design spec:** This document
**Coding standards:** `CLAUDE.md`
**Existing portal:** `portal/api/` (FastAPI backend), `portal/ui/` (React + Tailwind frontend)
**Rules dir:** `config/compare_rules/`
**Onboard wizard:** `instructions/onboard_wizard_orchestration_prompt.md` (reference for pattern)

---

## Architecture Overview

### Rule Hierarchy (3 tiers)

```
Tier 1: Universal      →  _universal.yaml           →  Applies to ALL profiles
Tier 2: Transaction     →  _global_{txn_type}.yaml   →  Applies to all profiles with that transaction_type
Tier 3: Partner         →  {profile_name}.yaml        →  Profile-specific overrides (existing files)
```

### Resolution Order (first match wins — most specific tier wins)

```
Input: (segment, field) for profile "bevager_810" (transaction_type=810)

1. Check partner rules   (bevager_810.yaml)        → match? → use it
2. Check txn-type rules  (_global_810.yaml)         → match? → use it
3. Check universal rules (_universal.yaml)          → match? → use it
4. Default: FieldRule(severity="hard")

Within each tier, wildcard resolution is unchanged:
  exact (segment, field) > (segment, *) > (*, field) > (*, *)
```

### Naming Convention

- `_universal.yaml` — leading underscore, always singular
- `_global_810.yaml`, `_global_850.yaml` — leading underscore + `_global_` prefix
- `bevager_810.yaml`, `810_invoice.yaml` — unchanged partner files (no underscore prefix)

Leading underscores prevent name collisions with profile names and sort tier files visually above partner files.

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and any files it imports before proposing changes.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Match existing patterns** — follow conventions in the codebase exactly.
8. **Backward compatibility** — existing `load_rules()` callers must still work. Missing tier files produce empty rules (no errors).
9. **Server is live** — backend on port 8000, frontend on 5173. Test with curl and verify UI throughout.
10. **Path resolution** — use `_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent` pattern (see `portal/api/routes/compare.py`).

---

## Pre-Flight

```bash
cd ~/VS/pycoreEdi

# Start backend (if not already running)
python -m uvicorn portal.api.app:create_app --factory --port 8000 &

# Start frontend (if not already running)
cd ~/VS/pycoreEdi/portal/ui && npm run dev &

# Verify baseline
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
```

If anything fails, **stop and fix before proceeding**.

---

# PHASE 1: Engine — Tiered Rule Resolution

> **Prerequisite:** Pre-flight green.
> **Deliverables:** New dataclasses, tiered loading, merge function, resolver with provenance.

---

## Task 1.1 — Add TieredRules and ResolvedFieldRule Models

**Investigate:**
```bash
cat pyedi_core/comparator/models.py
```

**Execute:**

Add two new dataclasses to `pyedi_core/comparator/models.py` (after the existing `CompareRules` class):

```python
@dataclass
class TieredRules:
    """Three-tier rule container: universal → transaction-type → partner."""

    universal: CompareRules = field(default_factory=CompareRules)
    transaction: CompareRules = field(default_factory=CompareRules)
    partner: CompareRules = field(default_factory=CompareRules)


@dataclass
class ResolvedFieldRule:
    """A FieldRule annotated with the tier it came from."""

    rule: FieldRule
    tier: str  # "universal" | "transaction" | "partner" | "default"
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.models import TieredRules, ResolvedFieldRule, CompareRules, FieldRule
t = TieredRules()
assert t.universal.classification == []
assert t.transaction.classification == []
assert t.partner.classification == []
r = ResolvedFieldRule(rule=FieldRule(segment='*', field='*'), tier='universal')
assert r.tier == 'universal'
print('Models verified')
"
```

**Commit:** `feat(comparator): add TieredRules and ResolvedFieldRule dataclasses`

---

## Task 1.2 — Add load_tiered_rules() Function

**Investigate:**
```bash
cat pyedi_core/comparator/rules.py
ls config/compare_rules/
```

**Execute:**

Add to `pyedi_core/comparator/rules.py`:

```python
import os
from pathlib import Path

from pyedi_core.comparator.models import TieredRules


def load_tiered_rules(
    rules_dir: str,
    transaction_type: str,
    partner_rules_path: str,
) -> TieredRules:
    """Load up to 3 tiers of rules from the rules directory.

    Tier 1: {rules_dir}/_universal.yaml
    Tier 2: {rules_dir}/_global_{transaction_type}.yaml
    Tier 3: partner_rules_path (the profile's existing rules file)

    Missing tier files produce empty CompareRules (no error).
    """
    universal = CompareRules()
    transaction = CompareRules()
    partner = CompareRules()

    universal_path = os.path.join(rules_dir, "_universal.yaml")
    if os.path.isfile(universal_path):
        universal = load_rules(universal_path)

    if transaction_type:
        txn_path = os.path.join(rules_dir, f"_global_{transaction_type}.yaml")
        if os.path.isfile(txn_path):
            transaction = load_rules(txn_path)

    if partner_rules_path and os.path.isfile(partner_rules_path):
        partner = load_rules(partner_rules_path)

    return TieredRules(universal=universal, transaction=transaction, partner=partner)
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.rules import load_tiered_rules
# With existing partner rules, no tier files yet
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
assert len(t.partner.classification) > 0, 'Partner rules should load'
assert len(t.universal.classification) == 0, 'No universal file yet'
assert len(t.transaction.classification) == 0, 'No txn-type file yet'
print(f'Tiered load verified: partner has {len(t.partner.classification)} rules, tiers empty as expected')
"
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

**Commit:** `feat(comparator): add load_tiered_rules() for 3-tier rule loading`

---

## Task 1.3 — Add merge_rules() Function

**Execute:**

Add to `pyedi_core/comparator/rules.py`:

```python
def merge_rules(tiered: TieredRules) -> CompareRules:
    """Flatten 3-tier rules into a single CompareRules.

    Resolution: partner overrides transaction overrides universal.
    For each (segment, field) key, the most specific tier wins.
    Ignore lists are unioned across all tiers (deduplicated by segment+field).
    """
    # Build merged classification dict: universal → overlay txn → overlay partner
    merged: dict[tuple[str, str], FieldRule] = {}

    for rule in tiered.universal.classification:
        merged[(rule.segment, rule.field)] = rule
    for rule in tiered.transaction.classification:
        merged[(rule.segment, rule.field)] = rule
    for rule in tiered.partner.classification:
        merged[(rule.segment, rule.field)] = rule

    # Union ignore lists, deduplicate by (segment, field)
    seen_ignores: set[tuple[str, str]] = set()
    merged_ignores: list[dict[str, str]] = []
    for ignore_list in [
        tiered.universal.ignore,
        tiered.transaction.ignore,
        tiered.partner.ignore,
    ]:
        for entry in ignore_list:
            key = (entry.get("segment", ""), entry.get("field", ""))
            if key not in seen_ignores:
                seen_ignores.add(key)
                merged_ignores.append(entry)

    return CompareRules(classification=list(merged.values()), ignore=merged_ignores)
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.models import CompareRules, FieldRule, TieredRules
from pyedi_core.comparator.rules import merge_rules

# Universal: InvoiceAmount=hard, Description=ignore
universal = CompareRules(classification=[
    FieldRule(segment='*', field='InvoiceAmount', severity='hard', numeric=True),
    FieldRule(segment='*', field='Description', severity='ignore', ignore_case=True),
    FieldRule(segment='*', field='*', severity='hard'),
])

# Transaction: Description=soft (overrides universal ignore)
transaction = CompareRules(classification=[
    FieldRule(segment='*', field='Description', severity='soft', ignore_case=True),
])

# Partner: InvoiceAmount=soft (overrides universal hard)
partner = CompareRules(classification=[
    FieldRule(segment='*', field='InvoiceAmount', severity='soft', numeric=True),
])

tiered = TieredRules(universal=universal, transaction=transaction, partner=partner)
merged = merge_rules(tiered)

lookup = {(r.segment, r.field): r for r in merged.classification}
assert lookup[('*', 'InvoiceAmount')].severity == 'soft', 'Partner should override universal'
assert lookup[('*', 'Description')].severity == 'soft', 'Transaction should override universal'
assert lookup[('*', '*')].severity == 'hard', 'Catch-all from universal preserved'
print('merge_rules verified: overrides work correctly')
"
```

**Commit:** `feat(comparator): add merge_rules() for tier flattening`

---

## Task 1.4 — Add get_resolved_field_rule() with Provenance

**Execute:**

Add to `pyedi_core/comparator/rules.py`:

```python
from pyedi_core.comparator.models import ResolvedFieldRule


def get_resolved_field_rule(
    tiered: TieredRules, segment: str, field: str
) -> ResolvedFieldRule:
    """Resolve rule for (segment, field) across tiers, annotating which tier it came from.

    Resolution order: partner → transaction → universal → default.
    Within each tier, uses the same wildcard chain as get_field_rule().
    """
    for tier_name, tier_rules in [
        ("partner", tiered.partner),
        ("transaction", tiered.transaction),
        ("universal", tiered.universal),
    ]:
        if not tier_rules.classification:
            continue
        lookup = {(r.segment, r.field): r for r in tier_rules.classification}

        # Same priority chain as get_field_rule()
        for key in [
            (segment, field),
            (segment, "*"),
            ("*", field),
            ("*", "*"),
        ]:
            if key in lookup:
                return ResolvedFieldRule(rule=lookup[key], tier=tier_name)

    # No rule in any tier — hardcoded default
    return ResolvedFieldRule(
        rule=FieldRule(segment=segment, field=field, severity="hard"),
        tier="default",
    )
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.models import CompareRules, FieldRule, TieredRules
from pyedi_core.comparator.rules import get_resolved_field_rule

universal = CompareRules(classification=[
    FieldRule(segment='*', field='InvoiceAmount', severity='hard', numeric=True),
    FieldRule(segment='*', field='*', severity='hard'),
])
partner = CompareRules(classification=[
    FieldRule(segment='*', field='InvoiceAmount', severity='soft', numeric=True),
])
tiered = TieredRules(universal=universal, partner=partner)

# Partner override
r1 = get_resolved_field_rule(tiered, '*', 'InvoiceAmount')
assert r1.tier == 'partner' and r1.rule.severity == 'soft', 'Partner should win'

# Universal fallback
r2 = get_resolved_field_rule(tiered, '*', 'Description')
assert r2.tier == 'universal' and r2.rule.severity == 'hard', 'Should fall back to universal catch-all'

# No rules at all
empty = TieredRules()
r3 = get_resolved_field_rule(empty, 'N1', 'N102')
assert r3.tier == 'default', 'Should be default when all tiers empty'

print('get_resolved_field_rule verified: provenance tracking correct')
"
```

**Commit:** `feat(comparator): add get_resolved_field_rule() with tier provenance`

---

## Task 1.5 — Update compare() and reclassify() to Use Tiered Loading

**Investigate:**
```bash
cat pyedi_core/comparator/__init__.py
```

**Execute:**

In `pyedi_core/comparator/__init__.py`:

1. Add imports:
```python
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules
```

2. In `compare()` function (around line 59), replace:
```python
rules = load_rules(profile.rules_file)
```
with:
```python
rules_dir = os.path.dirname(profile.rules_file)
tiered = load_tiered_rules(rules_dir, profile.transaction_type, profile.rules_file)
rules = merge_rules(tiered)
```

3. In `reclassify()` function, apply the same change — find the `load_rules(profile.rules_file)` call and replace it with the tiered version.

**Important:** Do NOT remove the `load_rules` import — it may still be used elsewhere. Only add the new imports.

**Test Gate:**
```bash
# Existing tests must still pass — no tier files exist yet, so behavior is identical
python -m pytest tests/ -v --tb=short 2>&1 | tail -10

# Direct invocation test
python -c "
from pyedi_core.comparator import compare, load_profile
profile = load_profile('config/config.yaml', 'bevager_810')
print(f'Profile loaded: {profile.name}, rules_file={profile.rules_file}')
# Don't run full compare (needs data files), just verify it doesn't crash on import
print('Import and profile load OK — tiered loading wired correctly')
"
```

**Commit:** `feat(comparator): wire tiered rule loading into compare() and reclassify()`

---

### Phase 1 Gate

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
echo "---"
python -c "
from pyedi_core.comparator.models import TieredRules, ResolvedFieldRule
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules, get_resolved_field_rule, load_rules
print('All new symbols importable')

# Integration: load existing profile through tiered system
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
merged = merge_rules(t)
assert len(merged.classification) > 0
print(f'Tiered merge produces {len(merged.classification)} rules (partner-only mode)')
print('PHASE 1 GATE: PASS')
"
```

---

# PHASE 2: Seed Universal Rules + Migration

> **Prerequisite:** Phase 1 gate green.
> **Deliverables:** `_universal.yaml` with shared rules, optional `_global_810.yaml`.

---

## Task 2.1 — Create _universal.yaml

**Investigate:**
```bash
# Find rules that repeat across multiple partner files
cat config/compare_rules/810_invoice.yaml
cat config/compare_rules/bevager_810.yaml
cat config/compare_rules/csv_generic.yaml
```

**Execute:**

Create `config/compare_rules/_universal.yaml`:

```yaml
# Universal rules — apply to ALL compare profiles.
# Partner and transaction-type rules override these.

classification: []

ignore:
  - segment: "ISA"
    field: "*"
    reason: "Envelope-level fields — not business data"
  - segment: "GS"
    field: "*"
    reason: "Functional group envelope — not business data"
  - segment: "SE"
    field: "SE01"
    reason: "Segment count varies by implementation"
  - segment: "GE"
    field: "*"
    reason: "Functional group trailer — not business data"
  - segment: "IEA"
    field: "*"
    reason: "Interchange trailer — not business data"
```

**Design note:** Universal classification starts empty — only ignore rules are universal initially. Users add universal classification rules through the UI. The ignore list captures envelope segments that are never business-relevant.

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.rules import load_rules
rules = load_rules('config/compare_rules/_universal.yaml')
assert len(rules.classification) == 0, 'No universal classification rules initially'
assert len(rules.ignore) >= 4, 'Should have envelope ignore rules'
print(f'Universal rules verified: {len(rules.ignore)} ignore rules')
"

# Verify tiered loading now picks up universal
python -c "
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
merged = merge_rules(t)
has_isa_ignore = any(
    e.get('segment') == 'ISA' and e.get('field') == '*'
    for e in merged.ignore
)
assert has_isa_ignore, 'ISA ignore should come from universal tier'
print('Tiered merge with universal: OK')
"
```

**Commit:** `feat(comparator): seed _universal.yaml with envelope ignore rules`

---

## Task 2.2 — (Optional) Create _global_810.yaml

If common 810-specific rules are identified across multiple 810 partner files, extract them into `config/compare_rules/_global_810.yaml`. Otherwise, create an empty skeleton:

```yaml
# Transaction-type rules for EDI 810 (Invoice).
# Apply to all 810 profiles. Partner rules override these.

classification: []
ignore: []
```

**Test Gate:**
```bash
python -c "
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
assert t.transaction.classification is not None, 'Transaction tier should load'
merged = merge_rules(t)
print(f'3-tier merge: {len(merged.classification)} classification, {len(merged.ignore)} ignore')
print('All 3 tiers active')
"
```

**Commit:** `feat(comparator): add _global_810.yaml transaction-type rules skeleton`

---

### Phase 2 Gate

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
python -c "
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
assert len(t.universal.ignore) >= 4
merged = merge_rules(t)
print(f'PHASE 2 GATE: PASS — 3-tier system active with {len(merged.classification)} rules, {len(merged.ignore)} ignores')
"
```

---

# PHASE 3: Backend API — Rules Tier CRUD

> **Prerequisite:** Phase 2 gate green.
> **Deliverables:** New `/api/rules/` route file with endpoints for tier management and effective-rules view.

---

## Task 3.1 — Create Rules Route File with Tier List Endpoint

**Investigate:**
```bash
cat portal/api/routes/compare.py | head -60
cat portal/api/app.py
```

**Execute:**

Create `portal/api/routes/rules.py` with:

1. `_PROJECT_ROOT` and `_RULES_DIR` resolution (same pattern as compare.py)
2. Pydantic response models:
   - `TierInfoResponse`: `tier: str, name: str, file: str, rule_count: int, ignore_count: int`
   - `TierListResponse`: `tiers: list[TierInfoResponse]`
3. `GET /api/rules/tiers` endpoint:
   - Scans `config/compare_rules/` for `_universal.yaml` and `_global_*.yaml` files
   - Also lists partner-level files from `config.yaml` compare profiles
   - Returns `TierListResponse` with tier type, file name, and rule counts

**Test Gate:**
```bash
curl -s http://localhost:8000/api/rules/tiers | python -m json.tool
# Should show universal, any _global_ files, and all partner files
```

**Commit:** `feat(rules-api): add GET /api/rules/tiers endpoint`

---

## Task 3.2 — Add Universal Rules CRUD

**Execute:**

Add to `portal/api/routes/rules.py`:

1. `GET /api/rules/universal` — reads `_universal.yaml`, returns classification + ignore as JSON
2. `PUT /api/rules/universal` — accepts `{classification: [...], ignore: [...]}`, writes to `_universal.yaml`
   - Creates file if it doesn't exist
   - Uses `yaml.dump(data, f, default_flow_style=False, sort_keys=False)`

**Test Gate:**
```bash
# Read universal rules
curl -s http://localhost:8000/api/rules/universal | python -m json.tool

# Update universal rules (add a test classification)
curl -s -X PUT http://localhost:8000/api/rules/universal \
  -H "Content-Type: application/json" \
  -d '{
    "classification": [
      {"segment": "*", "field": "TestField", "severity": "soft", "ignore_case": false, "numeric": false}
    ],
    "ignore": [
      {"segment": "ISA", "field": "*", "reason": "Envelope fields"}
    ]
  }' | python -m json.tool

# Verify file was updated
python -c "
import yaml
with open('config/compare_rules/_universal.yaml') as f:
    data = yaml.safe_load(f)
assert any(r['field'] == 'TestField' for r in data['classification'])
print('Universal update verified')
"

# CLEANUP: restore original universal file
python -c "
import yaml
data = {
    'classification': [],
    'ignore': [
        {'segment': 'ISA', 'field': '*', 'reason': 'Envelope-level fields — not business data'},
        {'segment': 'GS', 'field': '*', 'reason': 'Functional group envelope — not business data'},
        {'segment': 'SE', 'field': 'SE01', 'reason': 'Segment count varies by implementation'},
        {'segment': 'GE', 'field': '*', 'reason': 'Functional group trailer — not business data'},
        {'segment': 'IEA', 'field': '*', 'reason': 'Interchange trailer — not business data'},
    ]
}
with open('config/compare_rules/_universal.yaml', 'w') as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
print('Universal rules restored')
"
```

**Commit:** `feat(rules-api): add GET/PUT /api/rules/universal`

---

## Task 3.3 — Add Transaction-Type Rules CRUD

**Execute:**

Add to `portal/api/routes/rules.py`:

1. `GET /api/rules/transaction/{txn_type}` — reads `_global_{txn_type}.yaml`, returns 404 if file doesn't exist
2. `PUT /api/rules/transaction/{txn_type}` — writes `_global_{txn_type}.yaml` (creates if needed)
3. `DELETE /api/rules/transaction/{txn_type}` — removes the file, returns 404 if not found

**Test Gate:**
```bash
# Create transaction-type rules
curl -s -X PUT http://localhost:8000/api/rules/transaction/810 \
  -H "Content-Type: application/json" \
  -d '{
    "classification": [
      {"segment": "*", "field": "InvoiceAmount", "severity": "hard", "numeric": true, "ignore_case": false}
    ],
    "ignore": []
  }' | python -m json.tool

# Read them back
curl -s http://localhost:8000/api/rules/transaction/810 | python -m json.tool

# Verify file exists
python -c "
import os
assert os.path.isfile('config/compare_rules/_global_810.yaml')
print('Transaction rules file exists')
"

# Delete transaction rules (cleanup for tests)
curl -s -X DELETE http://localhost:8000/api/rules/transaction/810 -w '\n%{http_code}'
# Should print 200

# Verify 404 on read after delete
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/rules/transaction/810
# Should print 404
```

**Commit:** `feat(rules-api): add GET/PUT/DELETE /api/rules/transaction/{txn_type}`

---

## Task 3.4 — Add Effective Rules Endpoint

**Investigate:**
```bash
cat pyedi_core/comparator/__init__.py | head -40  # load_profile function
```

**Execute:**

Add to `portal/api/routes/rules.py`:

1. Pydantic models:
   - `EffectiveRuleResponse`: `segment, field, severity, ignore_case, numeric, conditional_qualifier, amount_variance, tier`
   - `EffectiveRulesResponse`: `rules: list[EffectiveRuleResponse], ignore: list[dict]`
2. `GET /api/rules/effective/{profile_name}` endpoint:
   - Loads profile from config.yaml via `load_profile()`
   - Calls `load_tiered_rules(rules_dir, profile.transaction_type, profile.rules_file)`
   - Collects all unique `(segment, field)` keys across all 3 tiers
   - For each key, calls `get_resolved_field_rule(tiered, segment, field)` to get the winning rule + tier
   - Also merges ignore lists across tiers
   - Returns `EffectiveRulesResponse`

**Test Gate:**
```bash
curl -s http://localhost:8000/api/rules/effective/bevager_810 | python -m json.tool

# Verify tier annotations
python -c "
import json, urllib.request
resp = urllib.request.urlopen('http://localhost:8000/api/rules/effective/bevager_810')
data = json.loads(resp.read())
rules = data['rules']
tiers_seen = set(r['tier'] for r in rules)
print(f'Effective rules: {len(rules)} rules, tiers: {tiers_seen}')
assert len(rules) > 0, 'Should have rules'
# At minimum, partner rules should be present
assert 'partner' in tiers_seen, 'Partner tier should appear'
print('Effective rules endpoint verified')
"
```

**Commit:** `feat(rules-api): add GET /api/rules/effective/{profile_name} with tier provenance`

---

## Task 3.5 — Wire Rules Router into App

**Execute:**

Add to `portal/api/app.py`:
```python
from .routes.rules import router as rules_router
application.include_router(rules_router)
```

**Test Gate:**
```bash
# Verify all endpoints registered
curl -s http://localhost:8000/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
rules_paths = [p for p in spec['paths'] if '/rules' in p]
print(f'Rules endpoints: {rules_paths}')
assert len(rules_paths) >= 4, 'Expected at least 4 rules endpoints'
"
```

**Commit:** `feat(rules-api): wire rules router into FastAPI app`

---

### Phase 3 Gate

```bash
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('Health OK')"
curl -s http://localhost:8000/api/rules/tiers | python -c "import json,sys; d=json.load(sys.stdin); print(f'Tiers: {len(d[\"tiers\"])} entries')"
curl -s http://localhost:8000/api/rules/universal | python -c "import json,sys; d=json.load(sys.stdin); print(f'Universal: {len(d.get(\"ignore\",[]))} ignores')"
curl -s http://localhost:8000/api/rules/effective/bevager_810 | python -c "import json,sys; d=json.load(sys.stdin); print(f'Effective: {len(d[\"rules\"])} rules')"
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
echo "PHASE 3 GATE: PASS"
```

---

# PHASE 4: Frontend — Rules Management Page

> **Prerequisite:** Phase 3 gate green.
> **Deliverables:** New "Rules" page with 4-tab layout, visual rule editing, effective view with tier badges.

**IMPORTANT:** Use the `/frontend-design` skill when building UI components. The Rules page must be visually polished:
- Tab navigation with active/inactive states
- Data grid with alternating row colors and hover highlights
- Severity dropdowns with color-coded options (red=hard, amber=soft, gray=ignore)
- Tier badges with distinct colors (blue=universal, yellow=transaction, green=partner, gray=default)
- Card-based layout with clear sections and typography hierarchy

---

## Task 4.1 — Add API Client Methods

**Investigate:**
```bash
cat portal/ui/src/api.ts
```

**Execute:**

Add to the `api` object in `portal/ui/src/api.ts`:

```typescript
// Rules tier API
ruleTiers: () =>
  request<{
    tiers: Array<{
      tier: string;
      name: string;
      file: string;
      rule_count: number;
      ignore_count: number;
    }>;
  }>('/rules/tiers'),

ruleUniversal: () =>
  request<{
    classification: Array<Record<string, any>>;
    ignore: Array<Record<string, any>>;
  }>('/rules/universal'),

ruleUpdateUniversal: (rules: { classification: any[]; ignore: any[] }) =>
  request<any>('/rules/universal', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rules),
  }),

ruleTransaction: (txnType: string) =>
  request<{
    classification: Array<Record<string, any>>;
    ignore: Array<Record<string, any>>;
  }>(`/rules/transaction/${encodeURIComponent(txnType)}`),

ruleUpdateTransaction: (txnType: string, rules: { classification: any[]; ignore: any[] }) =>
  request<any>(`/rules/transaction/${encodeURIComponent(txnType)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rules),
  }),

ruleDeleteTransaction: (txnType: string) =>
  request<any>(`/rules/transaction/${encodeURIComponent(txnType)}`, {
    method: 'DELETE',
  }),

ruleEffective: (profileName: string) =>
  request<{
    rules: Array<{
      segment: string;
      field: string;
      severity: string;
      ignore_case: boolean;
      numeric: boolean;
      conditional_qualifier: string | null;
      amount_variance: number | null;
      tier: string;
    }>;
    ignore: Array<Record<string, any>>;
  }>(`/rules/effective/${encodeURIComponent(profileName)}`),
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

**Commit:** `feat(rules-ui): add API client methods for rules tier endpoints`

---

## Task 4.2 — Create Rules Page with Overview Tab

**Investigate:**
```bash
cat portal/ui/src/pages/Compare.tsx | head -50   # for pattern reference
cat portal/ui/src/App.tsx                         # for nav pattern
```

**Execute:**

Use the `/frontend-design` skill to create `portal/ui/src/pages/Rules.tsx`.

**Page structure:**
- Horizontal tab bar at top: **Overview** | **Universal** | **Transaction** | **Effective View**
- Default tab: Overview

**Overview tab design:**
- 3 sections as cards, stacked vertically:

**Card 1: "Universal Rules"**
- Badge showing ignore count and classification count
- Description: "Apply to all profiles — envelope fields, common ignores"
- "Edit" button → switches to Universal tab

**Card 2: "Transaction-Type Rules"**
- Lists each `_global_{txn_type}.yaml` found, with rule counts
- "Add Transaction Type" button (text input + create)
- Each row: txn type label, rule count badge, "Edit" button → switches to Transaction tab with that type pre-selected

**Card 3: "Partner Rules"**
- Lists profiles grouped by transaction_type
- Each row: profile name, trading partner, rule count badge
- "Edit" link → navigates to Compare page rules editor OR opens inline
- Shows tier inheritance note: "Inherits from Universal + {txn_type} rules"

Load data via `api.ruleTiers()` on mount.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

**Commit:** `feat(rules-ui): create Rules page with Overview tab`

---

## Task 4.3 — Add Universal Rules Editor Tab

**Execute:**

Add the Universal tab content to `Rules.tsx`:

**Layout:**
- **Classification rules grid** (editable table):
  - Columns: Segment | Field | Severity (dropdown: hard/soft/ignore) | Numeric (checkbox) | Ignore Case (checkbox)
  - "Add Rule" button → appends empty row
  - "Remove" button per row (trash icon)
  - Alternating row colors, hover highlight

- **Ignore list** (below the grid):
  - Columns: Segment | Field | Reason
  - "Add Ignore" button
  - "Remove" per row

- **Save button** → calls `api.ruleUpdateUniversal({classification, ignore})`
  - Green success banner on save
  - Transforms grid state to API format before saving

**Reusable component:** Extract the rules grid into a `RulesGrid` sub-component (within the same file is fine) that accepts `rules[]`, `onChange`, and optional `readOnly` prop. This grid is reused in the Transaction tab and the Onboard wizard could adopt it later.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Manually verify:
1. Click "Universal" tab → see classification grid (empty initially) + ignore list (5 envelope rules)
2. Add a classification rule, change severity to "soft"
3. Click Save → verify `_universal.yaml` updated

**Commit:** `feat(rules-ui): add Universal rules editor tab with editable grid`

---

## Task 4.4 — Add Transaction Rules Editor Tab

**Execute:**

Add the Transaction tab content to `Rules.tsx`:

**Layout:**
- Dropdown at top: "Select Transaction Type" — populated from `api.ruleTiers()` (filter tier === "transaction")
  - Plus a "Create New" option that shows a text input for the transaction type code
- Below dropdown: the same `RulesGrid` component (reused from Task 4.3)
- "Delete Transaction Rules" button (red, with confirmation) → calls `api.ruleDeleteTransaction()`
- Save button → calls `api.ruleUpdateTransaction(txnType, rules)`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Manually verify:
1. Click "Transaction" tab
2. If no `_global_810.yaml` exists, use "Create New" to create one for type "810"
3. Add a rule, save
4. Verify `_global_810.yaml` was created/updated

**Commit:** `feat(rules-ui): add Transaction rules editor tab`

---

## Task 4.5 — Add Effective View Tab

**Execute:**

Add the Effective View tab content to `Rules.tsx`:

**Layout:**
- Profile dropdown at top — populated from `api.compareProfiles()`
- On profile select: calls `api.ruleEffective(profileName)`
- **Read-only rules table:**
  - Columns: Segment | Field | Severity | Numeric | Ignore Case | **Tier** (badge column)
  - Tier badges:
    - 🔵 Blue badge: "Universal"
    - 🟡 Yellow badge: "Transaction"
    - 🟢 Green badge: "Partner"
    - ⚪ Gray badge: "Default"
  - Rows are sorted: partner rules first, then transaction, then universal, then default
- **Ignore list** (read-only, below main table):
  - Shows merged ignores with tier indication

- **Summary bar** at top of table:
  - "X rules total: Y from partner, Z from transaction, W from universal"
  - Visual breakdown bar (proportional colored segments)

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Manually verify:
1. Click "Effective View" tab
2. Select "bevager_810" profile
3. See all rules with tier badges — most should show "Partner" (green)
4. If universal ignore rules exist, they should show with "Universal" (blue) badge

**Commit:** `feat(rules-ui): add Effective View tab with tier provenance badges`

---

## Task 4.6 — Register Rules Page in App Navigation

**Execute:**

Update `portal/ui/src/App.tsx`:

1. Import: `import RulesPage from './pages/Rules'`
2. Add `'rules'` to the `Page` type union
3. Add `{ key: 'rules', label: 'Rules' }` to the `NAV` array — position after `'compare'`
4. Add render: `{page === 'rules' && <RulesPage />}`

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Manually verify:
1. "Rules" appears in sidebar between Compare and Onboard
2. Clicking it shows the Rules page
3. All other tabs still work

**Commit:** `feat(rules-ui): register Rules page in App navigation`

---

### Phase 4 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('API: PASS')"
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
echo "PHASE 4 GATE: PASS"
```

---

# PHASE 5: Integration & Polish

> **Prerequisite:** Phase 4 gate green.
> **Deliverables:** Cross-page navigation, onboard integration, final verification.

---

## Task 5.1 — Add "Manage in Rules Page" Link to Compare Page

**Investigate:**
```bash
cat portal/ui/src/pages/Compare.tsx | grep -n "rules\|Rules" | head -20
```

**Execute:**

In `portal/ui/src/pages/Compare.tsx`, near the existing "Edit Rules" JSON textarea section:

1. Accept `onNavigate` prop (same pattern as Onboard if already threaded) or use a callback from App.tsx
2. Add a button/link: **"Open Rules Manager →"** that navigates to the Rules page
3. Style as a secondary/outline button to not compete with the existing Save Rules button

If `onNavigate` is not already available in Compare, thread it through from App.tsx:
- Update `ComparePage` (or `Compare` component) to accept `onNavigate?: (page: string) => void`
- Pass `setPage` from App.tsx

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
```

Manually verify:
1. Go to Compare page, select a profile
2. See "Open Rules Manager →" button near rules section
3. Clicking it navigates to Rules page

**Commit:** `feat(compare-ui): add navigation link to Rules page`

---

## Task 5.2 — Add Tier Inheritance Note to Onboard Wizard

**Investigate:**
```bash
cat portal/ui/src/pages/Onboard.tsx | grep -n "Step 3\|rules\|Rules" | head -20
```

**Execute:**

In `portal/ui/src/pages/Onboard.tsx`, within Step 3 (Configure Rules), add an informational note above the rules grid:

```
ℹ️ These are partner-specific rules. Universal and transaction-type rules (if configured)
   will also apply automatically. Manage rule tiers in the Rules page.
```

Style as a blue info banner (matching existing patterns in the codebase).

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
```

**Commit:** `feat(onboard-ui): add tier inheritance info note to Step 3`

---

## Task 5.3 — Final End-to-End Verification

```bash
# 1. All tests pass
cd ~/VS/pycoreEdi && python -m pytest tests/ -v --tb=short 2>&1 | tail -10

# 2. TypeScript compiles
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# 3. All API endpoints functional
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s http://localhost:8000/api/rules/tiers | python -m json.tool
curl -s http://localhost:8000/api/rules/universal | python -m json.tool
curl -s http://localhost:8000/api/rules/effective/bevager_810 | python -m json.tool
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool

# 4. Tiered resolution works correctly
python -c "
from pyedi_core.comparator.models import CompareRules, FieldRule, TieredRules
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules, get_resolved_field_rule

# Load real tiered rules
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
merged = merge_rules(t)
print(f'Merged: {len(merged.classification)} classification, {len(merged.ignore)} ignore')

# Verify universal ignores are present
has_isa = any(e.get('segment') == 'ISA' for e in merged.ignore)
print(f'ISA in merged ignore: {has_isa}')

# Verify partner rules are present
has_partner_rules = len(t.partner.classification) > 0
print(f'Partner rules loaded: {has_partner_rules}')

print('End-to-end rule resolution: OK')
"

# 5. Existing compare workflow unaffected
curl -s http://localhost:8000/api/compare/profiles/bevager_810/rules | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'Partner rules via existing endpoint: {len(d[\"classification\"])} rules — backward compatible')
"

echo "PHASE 5 GATE: PASS — Hierarchical rules system is production-ready"
```

**Commit:** `feat(rules): complete hierarchical rules management — 3-tier engine + Rules UI`

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `pyedi_core/comparator/models.py` | EDIT | Add TieredRules, ResolvedFieldRule dataclasses |
| `pyedi_core/comparator/rules.py` | EDIT | Add load_tiered_rules, merge_rules, get_resolved_field_rule |
| `pyedi_core/comparator/__init__.py` | EDIT | Wire tiered loading into compare() and reclassify() |
| `config/compare_rules/_universal.yaml` | CREATE | Seed universal ignore rules |
| `config/compare_rules/_global_810.yaml` | CREATE | Optional 810 transaction-type skeleton |
| `portal/api/routes/rules.py` | CREATE | Tier CRUD + effective-rules endpoints |
| `portal/api/app.py` | EDIT | Register rules router |
| `portal/ui/src/api.ts` | EDIT | Add 7 tier API methods |
| `portal/ui/src/pages/Rules.tsx` | CREATE | 4-tab Rules page (Overview, Universal, Transaction, Effective) |
| `portal/ui/src/App.tsx` | EDIT | Add Rules to nav |
| `portal/ui/src/pages/Compare.tsx` | EDIT | Add "Open Rules Manager" link |
| `portal/ui/src/pages/Onboard.tsx` | EDIT | Add tier inheritance info note |

## New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/rules/tiers` | List all tier files with rule counts |
| GET | `/api/rules/universal` | Read universal rules |
| PUT | `/api/rules/universal` | Update universal rules |
| GET | `/api/rules/transaction/{txn_type}` | Read transaction-type rules |
| PUT | `/api/rules/transaction/{txn_type}` | Update transaction-type rules |
| DELETE | `/api/rules/transaction/{txn_type}` | Delete transaction-type tier |
| GET | `/api/rules/effective/{profile_name}` | Merged rules with tier provenance |
