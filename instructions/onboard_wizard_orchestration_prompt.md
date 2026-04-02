# Trading Partner Onboarding Wizard — Orchestration Prompt

**Purpose:** Build a 3-step onboarding wizard in the PyEDI Portal that walks users through: (1) importing and compiling a DSL text file, (2) registering the trading partner in config.yaml, and (3) configuring compare rules via an interactive grid. The wizard lives on a new "Onboard" tab and must be visually polished and production-grade.

**Design spec:** `instructions/yamlCreationWizard.md`
**Coding standards:** `CLAUDE.md`
**Existing portal:** `portal/api/` (FastAPI backend), `portal/ui/` (React + Tailwind frontend)
**Config file:** `config/config.yaml`
**Compare rules dir:** `config/compare_rules/`

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and its imports before making any change.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Match existing patterns** — follow conventions in the codebase exactly. Read neighbor files before writing new ones.
8. **Use the frontend-design skill** — invoke `/frontend-design` for building the wizard UI components. The UI must be visually appealing, not generic — use distinctive design with clear visual hierarchy, smooth transitions between steps, and polished micro-interactions.
9. **Server is live** — the backend runs on port 8000, frontend on 5173. Test endpoints with curl and verify UI in the browser throughout.
10. **Path resolution** — all route files must resolve paths using `_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent` pattern (see `portal/api/routes/compare.py` for reference). Never use relative paths.

---

## Pre-Flight

Before starting any task, verify the development environment:

```bash
# Start backend (if not already running)
cd ~/VS/pycoreEdi
python -m uvicorn portal.api.app:create_app --factory --port 8000 &

# Start frontend (if not already running)
cd ~/VS/pycoreEdi/portal/ui
npm run dev &

# Verify API is healthy
curl -s http://localhost:8000/api/health

# Verify existing validate upload endpoint works
curl -s -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"dsl_path": "testingData/Batch1/bevager810FF.txt"}' | python -m json.tool | head -20

# Verify config endpoint works
curl -s http://localhost:8000/api/config | python -m json.tool | head -20

# Verify compare profiles endpoint works
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool

# Verify TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
```

If anything fails at baseline, **stop and fix before proceeding**.

---

# PHASE 1: Backend API (new endpoints)

> **Prerequisite:** Pre-flight green.
> **Deliverables:** Two new API endpoints for partner registration and rules template generation.

---

## Task 1.1 — Create Onboard Route File with `POST /api/onboard/register`

**Investigate:**
```bash
# Read existing route patterns
cat portal/api/routes/config.py
cat portal/api/routes/compare.py | head -50
# Read config.yaml structure
cat config/config.yaml
# Read existing compare rules for pattern
cat config/compare_rules/bevager_810.yaml
```

**Execute:**

Create `portal/api/routes/onboard.py` with:

1. `_PROJECT_ROOT` resolution (same pattern as compare.py)
2. `_CONFIG_PATH` resolved from `_PROJECT_ROOT`
3. Pydantic request model `RegisterPartnerRequest`:
   - `profile_name: str` — e.g., `bevager_810`
   - `trading_partner: str` — e.g., `Bevager`
   - `transaction_type: str` — e.g., `810`
   - `description: str` — free text
   - `source_dsl: str` — path to DSL file (relative to project root)
   - `compiled_output: str` — path to compiled YAML (from validate response)
   - `inbound_dir: str` — path to data files directory
   - `match_key: dict` — either `{"json_path": "header.InvoiceID"}` or `{"segment": "BIG", "field": "BIG02"}`
   - `segment_qualifiers: dict` — optional, default `{}`
4. Pydantic response model `RegisterPartnerResponse`:
   - `profile_name: str`
   - `rules_file: str`
   - `config_updated: bool`
   - `rules_created: bool`
5. `POST /api/onboard/register` endpoint that:
   a. Reads `config.yaml` via `yaml.safe_load`
   b. Checks `profile_name` doesn't already exist in `compare.profiles` — if it does, return 409 Conflict
   c. Adds entry to `csv_schema_registry` section
   d. Adds entry to `compare.profiles` section
   e. Writes updated `config.yaml` via `yaml.dump` (with `default_flow_style=False, sort_keys=False`)
   f. Creates skeleton rules file at `config/compare_rules/{profile_name}.yaml` with a default `*/*` hard catch-all rule and `ignore: []`
   g. Returns `RegisterPartnerResponse`

**Important patterns to follow:**
- Path resolution: use `_PROJECT_ROOT / "config" / "config.yaml"` — see `portal/api/routes/compare.py` line 44-45
- YAML write: use `yaml.dump(config, f, default_flow_style=False, sort_keys=False)` — see `portal/api/routes/config.py` line 58
- Error handling: use `HTTPException` with specific status codes — see existing routes

**Test Gate:**
```bash
# Test registration endpoint with curl
curl -s -X POST http://localhost:8000/api/onboard/register \
  -H "Content-Type: application/json" \
  -d '{
    "profile_name": "test_wizard_810",
    "trading_partner": "TestWizard",
    "transaction_type": "810",
    "description": "Test wizard registration",
    "source_dsl": "./testingData/Batch1/bevager810FF.txt",
    "compiled_output": "./schemas/compiled/bevager810FF_map.yaml",
    "inbound_dir": "./testingData/Batch1/testSample-FlatFile-Target",
    "match_key": {"json_path": "header.InvoiceID"},
    "segment_qualifiers": {}
  }' | python -m json.tool

# Verify config was updated
python -c "
import yaml
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
assert 'test_wizard_810' in cfg['csv_schema_registry'], 'Missing csv_schema_registry entry'
assert 'test_wizard_810' in cfg['compare']['profiles'], 'Missing compare profile entry'
profile = cfg['compare']['profiles']['test_wizard_810']
assert profile['trading_partner'] == 'TestWizard'
assert profile['match_key']['json_path'] == 'header.InvoiceID'
print('Config registration verified')
"

# Verify rules file was created
python -c "
import yaml
with open('config/compare_rules/test_wizard_810.yaml') as f:
    rules = yaml.safe_load(f)
assert 'classification' in rules
assert 'ignore' in rules
print('Rules skeleton verified')
"

# Verify duplicate registration returns 409
curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/onboard/register \
  -H "Content-Type: application/json" \
  -d '{
    "profile_name": "test_wizard_810",
    "trading_partner": "TestWizard",
    "transaction_type": "810",
    "description": "duplicate test",
    "source_dsl": "./testingData/Batch1/bevager810FF.txt",
    "compiled_output": "./schemas/compiled/bevager810FF_map.yaml",
    "inbound_dir": "./testingData/Batch1/testSample-FlatFile-Target",
    "match_key": {"json_path": "header.InvoiceID"},
    "segment_qualifiers": {}
  }'
# Should print: 409

# CLEANUP: Remove test entry from config and rules file
python -c "
import yaml, os
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
del cfg['csv_schema_registry']['test_wizard_810']
del cfg['compare']['profiles']['test_wizard_810']
with open('config/config.yaml', 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
os.remove('config/compare_rules/test_wizard_810.yaml')
print('Test cleanup done')
"
```

**Commit:** `feat(onboard-api): add POST /api/onboard/register for trading partner registration`

---

## Task 1.2 — Add `GET /api/onboard/rules-template` Endpoint

**Investigate:**
```bash
# Read the compiled schema YAML to understand column structure
cat schemas/compiled/bevager810FF_map.yaml
# Read the validator to understand the compiled YAML format
cat pyedi_core/validator.py | head -50
```

**Execute:**

Add to `portal/api/routes/onboard.py`:

1. Pydantic response model `RulesTemplateResponse`:
   - `classification: list[dict]` — auto-generated rules
   - `ignore: list` — empty list
2. `GET /api/onboard/rules-template` endpoint:
   - Query param: `compiled_yaml: str` — path to the compiled YAML schema file
   - Reads the compiled YAML, extracts `schema.columns`
   - For each column, generates a rule entry:
     - `segment: "*"`
     - `field: {column.name}`
     - `severity: "hard"` (default)
     - `ignore_case: false` (default, `true` for string fields named like `*Description*`)
     - `numeric: true` if column type is `float` or `integer`, else `false`
   - Appends a `*/*` default catch-all rule at the end
   - Returns `RulesTemplateResponse`

**Auto-generation logic:**
```
column.type == "float" or "integer" → numeric: true, severity: "hard"
column.name contains "Description"  → severity: "soft", ignore_case: true
all other strings                   → severity: "hard", ignore_case: false
catch-all */* at end                → severity: "hard", numeric: false
```

**Test Gate:**
```bash
# Test rules template generation
curl -s "http://localhost:8000/api/onboard/rules-template?compiled_yaml=schemas/compiled/bevager810FF_map.yaml" \
  | python -m json.tool

# Verify auto-generation logic
python -c "
import json, urllib.request
resp = urllib.request.urlopen('http://localhost:8000/api/onboard/rules-template?compiled_yaml=schemas/compiled/bevager810FF_map.yaml')
data = json.loads(resp.read())
rules = data['classification']

# Should have one rule per column + 1 catch-all
assert len(rules) >= 18, f'Expected at least 18 rules, got {len(rules)}'

# InvoiceAmount should be numeric
inv_rule = next(r for r in rules if r['field'] == 'InvoiceAmount')
assert inv_rule['numeric'] == True, 'InvoiceAmount should be numeric'
assert inv_rule['severity'] == 'hard'

# ProductDescription should be soft + ignore_case
desc_rule = next(r for r in rules if r['field'] == 'ProductDescription')
assert desc_rule['severity'] == 'soft', 'ProductDescription should be soft'
assert desc_rule['ignore_case'] == True

# Last rule should be catch-all
assert rules[-1]['field'] == '*', 'Last rule should be catch-all'
assert rules[-1]['segment'] == '*'

print(f'Rules template verified: {len(rules)} rules, auto-generation correct')
"
```

**Commit:** `feat(onboard-api): add GET /api/onboard/rules-template for auto-generated rules`

---

## Task 1.3 — Wire Onboard Router into App

**Investigate:**
```bash
cat portal/api/app.py
```

**Execute:**

Add to `portal/api/app.py`:
```python
from .routes.onboard import router as onboard_router
application.include_router(onboard_router)
```

**Test Gate:**
```bash
# Verify both endpoints are accessible
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/onboard/rules-template?compiled_yaml=schemas/compiled/bevager810FF_map.yaml
# Should print: 200

# Verify OpenAPI docs show new endpoints
curl -s http://localhost:8000/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
paths = [p for p in spec['paths'] if '/onboard' in p]
print(f'Onboard endpoints: {paths}')
assert len(paths) >= 2, 'Expected at least 2 onboard endpoints'
"
```

**Commit:** `feat(onboard-api): wire onboard router into FastAPI app`

---

### Phase 1 Gate

```bash
# All backend endpoints functional
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('Health OK')"

curl -s "http://localhost:8000/api/onboard/rules-template?compiled_yaml=schemas/compiled/bevager810FF_map.yaml" \
  | python -c "import json,sys; d=json.load(sys.stdin); assert len(d['classification'])>=18; print(f'Rules template OK: {len(d[\"classification\"])} rules')"

echo "PHASE 1 GATE: PASS"
```

---

# PHASE 2: Frontend — Onboard Wizard UI

> **Prerequisite:** Phase 1 gate green.
> **Deliverables:** New "Onboard" tab with 3-step wizard, visually polished with the frontend-design skill.

**IMPORTANT:** Use the `/frontend-design` skill when building the wizard components. The wizard must be visually distinctive and polished — not generic. Use:
- A clean horizontal stepper with step numbers, labels, and visual progress indicator
- Card-based layout with clear sections
- Smooth visual transitions between steps (opacity/transform)
- Color-coded status indicators (success green, warning amber, error red)
- Proper form validation with inline error messages
- Consistent typography hierarchy
- Subtle shadows and rounded corners matching the existing portal aesthetic

---

## Task 2.1 — Add API Client Methods

**Investigate:**
```bash
cat portal/ui/src/api.ts
```

**Execute:**

Add to the `api` object in `portal/ui/src/api.ts`:

```typescript
// Onboard wizard
onboardRegister: (data: {
  profile_name: string;
  trading_partner: string;
  transaction_type: string;
  description: string;
  source_dsl: string;
  compiled_output: string;
  inbound_dir: string;
  match_key: Record<string, string>;
  segment_qualifiers: Record<string, string | null>;
}) =>
  request<{
    profile_name: string;
    rules_file: string;
    config_updated: boolean;
    rules_created: boolean;
  }>('/onboard/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }),

onboardRulesTemplate: (compiledYaml: string) =>
  request<{
    classification: Array<{
      segment: string;
      field: string;
      severity: string;
      ignore_case: boolean;
      numeric: boolean;
    }>;
    ignore: any[];
  }>(`/onboard/rules-template?compiled_yaml=${encodeURIComponent(compiledYaml)}`),
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

**Commit:** `feat(onboard-ui): add API client methods for onboard endpoints`

---

## Task 2.2 — Create Onboard Page with Stepper and Step 1 (Compile DSL)

**Investigate:**
```bash
# Read existing Validate page for upload pattern reference
cat portal/ui/src/pages/Validate.tsx
# Read App.tsx for nav registration pattern
cat portal/ui/src/App.tsx
```

**Execute:**

Use the `/frontend-design` skill to create `portal/ui/src/pages/Onboard.tsx`.

**Design requirements for the page:**
- Horizontal stepper at top showing 3 steps: "Import & Compile" → "Register Partner" → "Configure Rules"
- Each step shows: step number in a circle, label text, and a connecting line
- Active step is highlighted (blue/indigo), completed steps show a checkmark, future steps are grayed
- Below the stepper, render the active step's content in a card

**Step 1 content ("Import & Compile DSL"):**
- Two input modes with a toggle: "Upload File" vs "Server Path"
  - Upload mode: file picker for DSL file + optional sample file (reuse pattern from Validate.tsx)
  - Path mode: text input for DSL path + optional sample path
- "Compile" button — calls `api.validateUpload()` or `api.validate()`
- On success, display results inline:
  - Summary card: transaction type, column count, compiled path
  - Columns table: field name, DSL type, compiled type, type preserved (checkmark/x)
  - Type warnings (if any) in amber alert box
- "Next: Register Partner" button — enabled only after successful compilation
- Carries forward to Step 2: `columns[]`, `compiled_yaml_path`, `transaction_type`, `dsl_path`

**Wizard state shape (managed in OnboardPage):**
```typescript
interface WizardState {
  // Step 1 outputs
  columns: Array<{ name: string; compiled_type: string; dsl_type: string }>;
  compiledYamlPath: string;
  transactionType: string;
  dslPath: string;
  // Step 2 outputs
  profileName: string;
  rulesFile: string;
  // Step 3
  complete: boolean;
}
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Then manually verify in browser:
1. Open http://localhost:5173, click "Onboard" tab
2. Stepper shows 3 steps, Step 1 is active
3. Upload `testingData/Batch1/bevager810FF.txt` (use path mode)
4. Click Compile — see 18 columns, types, transaction type
5. "Next" button becomes enabled

**Commit:** `feat(onboard-ui): create Onboard page with stepper and Step 1 (compile DSL)`

---

## Task 2.3 — Add Step 2 (Register Partner)

**Execute:**

Add Step 2 content to the Onboard page (can be inline or a separate component within the file).

**Step 2 content ("Register Partner"):**
- Form card with fields:
  - **Profile Name** — text input, auto-suggested from DSL filename (e.g., `bevager810FF` → `bevager_810`). Validate: lowercase, alphanumeric + underscore only.
  - **Trading Partner** — text input (e.g., "Bevager")
  - **Transaction Type** — text input, pre-filled from Step 1's `transactionType`
  - **Description** — text input (e.g., "Bevager 810 Invoice flat file comparison")
  - **Inbound Directory** — text input with path placeholder
  - **Match Key Type** — radio toggle: "JSON Path (CSV/flat)" vs "X12 Segment/Field"
    - JSON Path mode: dropdown of field names from Step 1's columns (e.g., `header.InvoiceID`)
    - X12 mode: two text inputs for segment (e.g., `BIG`) and field (e.g., `BIG02`)
- "Register" button — calls `api.onboardRegister()`
- On success: green success banner, show created profile name and rules file path
- On 409 conflict: red error showing "Profile already exists"
- "Next: Configure Rules" button — enabled after successful registration
- "Back" button to return to Step 1

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Then manually verify:
1. Complete Step 1 with bevager DSL
2. Step 2 form shows pre-filled transaction type
3. Fill in profile name, trading partner, inbound dir
4. Select match key from dropdown
5. Click Register — see success
6. Verify config.yaml was updated (check via `curl http://localhost:8000/api/config`)

**CLEANUP after testing:** Remove test entries from config.yaml and delete test rules file.

**Commit:** `feat(onboard-ui): add Step 2 (register partner) to onboard wizard`

---

## Task 2.4 — Add Step 3 (Configure Rules)

**Execute:**

Add Step 3 content to the Onboard page.

**Step 3 content ("Configure Rules"):**
- On enter: auto-load rules template via `api.onboardRulesTemplate(compiledYamlPath)`
- Optional: "Clone from existing profile" dropdown at top — lists profiles from `api.compareProfiles()`, on select loads that profile's rules via `api.compareRules(name)`
- **Rules grid** — editable table:
  - Columns: Field Name (read-only) | DSL Type (read-only label) | Severity (dropdown: hard/soft/ignore) | Numeric (checkbox) | Ignore Case (checkbox)
  - One row per field from the template
  - Last row is the `*/*` catch-all (always present, editable severity)
  - Alternating row colors for readability
  - Hover highlight on rows
- "Save Rules" button — transforms grid state into `{classification: [...], ignore: []}` and calls `api.compareUpdateRules(profileName, rules)`
- On success:
  - Green success banner: "Trading partner onboarded successfully"
  - Summary card showing: profile name, trading partner, transaction type, rules file path, column count
  - "Go to Compare" button — navigates to Compare tab (emit an event or use a callback passed from App.tsx)
  - "Onboard Another" button — resets wizard to Step 1
- "Back" button to return to Step 2

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Then manually verify:
1. Complete Steps 1-2
2. Step 3 shows auto-generated rules grid with 18+ rows
3. InvoiceAmount row has numeric checked
4. ProductDescription row has severity=soft, ignore_case checked
5. Change a severity dropdown — verify it updates
6. Click Save Rules
7. Verify rules file was written: `cat config/compare_rules/{profile_name}.yaml`

**Commit:** `feat(onboard-ui): add Step 3 (configure rules) to onboard wizard`

---

## Task 2.5 — Register Onboard Page in App Navigation

**Investigate:**
```bash
cat portal/ui/src/App.tsx
```

**Execute:**

Update `portal/ui/src/App.tsx`:
1. Import `OnboardPage` from `./pages/Onboard`
2. Add `'onboard'` to the `Page` type union
3. Add `{ key: 'onboard', label: 'Onboard' }` to the `NAV` array (position it after Config or before Dashboard — use judgment for logical flow)
4. Add `{page === 'onboard' && <OnboardPage />}` to the render section
5. **Optional:** If Step 3's "Go to Compare" button needs navigation, pass `setPage` as a prop to OnboardPage

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit
echo "TypeScript check: PASS"
```

Manually verify:
1. "Onboard" appears in the sidebar nav
2. Clicking it shows the wizard
3. All other tabs still work

**Commit:** `feat(onboard-ui): register Onboard page in App navigation`

---

### Phase 2 Gate

```bash
# TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# Backend still healthy
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('API: PASS')"

echo "PHASE 2 GATE: PASS"
```

---

# PHASE 3: End-to-End Verification

> **Prerequisite:** Phase 2 gate green.
> **Deliverables:** Full walkthrough proof, cleanup, final commit.

---

## Task 3.1 — Create Modified DSL for True New-Partner Test

The bevager DSL already exists in the system. To prove the wizard works end-to-end with a genuinely new partner, create a modified copy of the bevager DSL with 2 extra fields.

**Execute:**
```bash
# Copy the DSL and add 2 new fields
cp testingData/Batch1/bevager810FF.txt testingData/Batch1/acmeFoods810FF.txt
```

Edit `testingData/Batch1/acmeFoods810FF.txt`:
1. Change the package to `com.gfs.customer.ca.tp.acmefoods.outbound.n810`
2. Change the flatFileSchema name to `acmeFoods810FF`
3. Add two new fields after `ExtendedPrice`:
   - `ShipDate String`
   - `FreightCharge Decimal`

The resulting DSL should have 20 fields total (18 original + 2 new).

**Test Gate:**
```bash
# Verify the modified DSL compiles
python -m pycoreedi validate --dsl testingData/Batch1/acmeFoods810FF.txt --output-dir schemas/compiled
python -c "
import yaml
with open('schemas/compiled/acmeFoods810FF_map.yaml') as f:
    schema = yaml.safe_load(f)
cols = schema['schema']['columns']
assert len(cols) == 20, f'Expected 20 columns, got {len(cols)}'
col_names = [c['name'] for c in cols]
assert 'ShipDate' in col_names, 'Missing ShipDate'
assert 'FreightCharge' in col_names, 'Missing FreightCharge'
print(f'Modified DSL verified: {len(cols)} columns including ShipDate and FreightCharge')
"
```

**Commit:** `test: create acmeFoods810FF DSL for wizard e2e testing`

---

## Task 3.2 — Full Wizard Walkthrough with New DSL

**Execute a complete onboarding of the acmeFoods partner through the wizard UI:**

1. Open http://localhost:5173, click "Onboard"
2. **Step 1:** Enter DSL path `testingData/Batch1/acmeFoods810FF.txt`, click Compile
   - Verify: **20 columns** displayed (not 18), transaction type shown, no errors
   - Verify: ShipDate shows as `string`, FreightCharge shows as `float`
3. **Step 2:** Fill in:
   - Profile name: `acme_foods_810`
   - Trading partner: `AcmeFoods`
   - Transaction type: `810` (pre-filled)
   - Description: `Acme Foods 810 Invoice flat file comparison`
   - Inbound dir: `./testingData/Batch1/testSample-FlatFile-Target`
   - Match key: `header.InvoiceID` (from dropdown)
   - Click Register
   - Verify: success banner, no errors
4. **Step 3:**
   - Verify rules grid auto-populated with **20+ rows** (includes ShipDate and FreightCharge)
   - Verify FreightCharge row has numeric=true (auto-detected from Decimal type)
   - Verify ShipDate row has numeric=false (string type)
   - Change ProductDescription to severity=soft, ignore_case=true
   - Click Save Rules
   - Verify: success banner

**Verify backend state:**
```bash
# Config has new entries
python -c "
import yaml
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
assert 'acme_foods_810' in cfg['csv_schema_registry'], 'Missing csv_schema_registry'
assert 'acme_foods_810' in cfg['compare']['profiles'], 'Missing compare profile'
profile = cfg['compare']['profiles']['acme_foods_810']
assert profile['trading_partner'] == 'AcmeFoods'
assert profile['match_key']['json_path'] == 'header.InvoiceID'
print('Config: OK')
"

# Rules file exists and has 20+ rules (18 original + 2 new fields + catch-all)
python -c "
from pyedi_core.comparator.rules import load_rules, get_field_rule
rules = load_rules('config/compare_rules/acme_foods_810.yaml')
assert len(rules.classification) >= 20, f'Expected >=20 rules, got {len(rules.classification)}'

# New fields should be present
freight_rule = get_field_rule(rules, '*', 'FreightCharge')
assert freight_rule.numeric == True, 'FreightCharge should be numeric'

shipdate_rule = get_field_rule(rules, '*', 'ShipDate')
assert shipdate_rule.numeric == False, 'ShipDate should not be numeric'

print(f'Rules: OK ({len(rules.classification)} rules, new fields verified)')
"

# New profile appears in compare profiles API
curl -s http://localhost:8000/api/compare/profiles | python -c "
import json, sys
profiles = json.load(sys.stdin)
names = [p['name'] for p in profiles]
assert 'acme_foods_810' in names, f'Profile not in API: {names}'
print('Compare profiles API: OK')
"

# pyedi CLI still works
python -m pycoreedi compare --list-profiles --config config/config.yaml 2>&1 | grep acme_foods_810
```

---

## Task 3.3 — Cleanup Test Data

```bash
# Remove the e2e test partner
python -c "
import yaml, os
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
if 'acme_foods_810' in cfg.get('csv_schema_registry', {}):
    del cfg['csv_schema_registry']['acme_foods_810']
if 'acme_foods_810' in cfg.get('compare', {}).get('profiles', {}):
    del cfg['compare']['profiles']['acme_foods_810']
with open('config/config.yaml', 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
rules_file = 'config/compare_rules/acme_foods_810.yaml'
if os.path.exists(rules_file):
    os.remove(rules_file)
# Clean up test DSL and compiled artifacts
dsl_file = 'testingData/Batch1/acmeFoods810FF.txt'
if os.path.exists(dsl_file):
    os.remove(dsl_file)
for f_name in ['schemas/compiled/acmeFoods810FF_map.yaml', 'schemas/compiled/acmeFoods810FF_map.meta.json']:
    if os.path.exists(f_name):
        os.remove(f_name)
print('E2E test cleanup done')
"
```

---

## Task 3.4 — Final TypeScript + Backend Verification

```bash
# TypeScript
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# All existing endpoints still work
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool
curl -s http://localhost:8000/api/config/registry | python -m json.tool
curl -s "http://localhost:8000/api/manifest?limit=5" | python -m json.tool

# Existing tests still pass
cd ~/VS/pycoreEdi && python -m pytest tests/ -v --tb=short 2>&1 | tail -20

echo "PHASE 3 GATE: PASS — Wizard is production-ready"
```

**Commit:** `feat(onboard): complete trading partner onboarding wizard — 3-step UI + API`

---

## File Summary

| File | Action | Purpose |
|---|---|---|
| `portal/api/routes/onboard.py` | CREATE | Backend: registration + rules template endpoints |
| `portal/api/app.py` | EDIT | Wire onboard router |
| `portal/ui/src/api.ts` | EDIT | Add onboardRegister + onboardRulesTemplate methods |
| `portal/ui/src/pages/Onboard.tsx` | CREATE | 3-step wizard page (use /frontend-design skill) |
| `portal/ui/src/App.tsx` | EDIT | Add Onboard to nav and routing |
| `config/config.yaml` | WRITTEN BY WIZARD | Registration adds entries here |
| `config/compare_rules/{name}.yaml` | WRITTEN BY WIZARD | Registration creates skeleton, Step 3 saves full rules |
