# Partner Rules CRUD + Clickable Profile Links — Orchestration Prompt

**Purpose:** Extend the Rules page with a new "Partner" tab that provides full CRUD (add/edit/delete individual rules and ignore entries) for partner-level rules. Currently the Rules page only *reports* partner rules in the Overview tab — this prompt adds the ability to *manage* them inline. Additionally, profile names in the Overview's Partner Rules card become clickable links that navigate directly to the Partner editor for that profile.

**Design spec:** This document
**Coding standards:** `CLAUDE.md`
**Existing portal:** `portal/api/` (FastAPI backend), `portal/ui/` (React + Tailwind frontend)
**Rules dir:** `config/compare_rules/`
**Prior prompt:** `instructions/updatePortalForRules.md` (built the current 4-tab Rules page)

---

## Current State

### What exists
- **Rules page** (`portal/ui/src/pages/Rules.tsx`, 828 lines) with 4 tabs:
  - **Overview** — dashboard with 3 cards (Universal, Transaction, Partner). Partner card is **read-only**: profile name, rule count, ignore count, inheritance note. No edit buttons, no links.
  - **Universal** — full inline editing via `RulesGrid` + Save button ✅
  - **Transaction** — full CRUD: create/edit/delete transaction types + rules ✅
  - **Effective View** — read-only merged view with tier badges ✅
- **RulesGrid** component (lines 90–279) — reusable, supports add/edit/remove for classification rules and ignore entries, accepts `readOnly` prop
- **API endpoints already exist:**
  - `GET /api/compare/profiles/{name}/rules` — returns `{classification: [...], ignore: [...]}`
  - `PUT /api/compare/profiles/{name}/rules` — writes partner rules YAML file (creates if missing)
- **API client methods already exist** in `portal/ui/src/api.ts`:
  - `api.compareRules(profileName)` (line 81)
  - `api.compareUpdateRules(profileName, rules)` (lines 82–87)
- **Profiles already loaded** on mount in Rules page: `api.compareProfiles().then(setProfiles)` (line 320)
- **Navigation** is state-based (`page` state in `App.tsx`), not URL-routed. `onNavigate` callback pattern used by Compare and Onboard pages.

### What's missing
1. No "Partner" tab — users cannot edit partner rules from the Rules page
2. Profile names in the Overview Partner card are plain text — not clickable
3. `RulesPage` does not accept `onNavigate` prop — cannot link out to Compare if needed

---

## Architecture

### No backend changes required

All API endpoints and client methods for partner rules already exist. This is a **frontend-only** change touching two files:

```
portal/ui/src/pages/Rules.tsx   ← all 6 tasks
portal/ui/src/App.tsx           ← Task 6 (thread onNavigate to RulesPage)
```

### Tab layout after change

```
Overview | Universal | Transaction | Partner (NEW) | Effective View
```

### Partner tab design

Mirrors the existing Transaction tab pattern:
- Profile selector dropdown (reuses `profiles` state already loaded on mount)
- Editable `RulesGrid` for classification rules and ignore entries
- Save button → `api.compareUpdateRules(selectedPartner, { classification, ignore })`
- Success banner, error handling, tier count refresh

### Overview Partner card changes

- Profile name becomes a blue clickable `<button>` styled as a link
- Clicking sets `selectedPartner` and switches to the Partner tab
- "Edit" button added to each row (matches Transaction card pattern)

---

## Rules of Engagement

1. **Sequential within phases** — complete each task fully (including its test gate) before starting the next.
2. **Phase gates are hard stops** — do not start a phase until the prior phase gate passes.
3. **Read before writing** — always read the target file and any files it imports before proposing changes.
4. **Minimal diffs** — change only what the task requires. No drive-by fixes, no extra comments.
5. **One commit per task** — after each task passes its test gate, commit with a descriptive message.
6. **Stop on red** — if any test gate fails, diagnose and fix before proceeding.
7. **Match existing patterns** — follow conventions in the codebase exactly. Look at how Universal and Transaction tabs work and replicate the pattern for Partner.
8. **Server is live** — backend on port 8000, frontend on 5173. Test with curl and verify UI throughout.
9. **No backend changes** — all API endpoints exist. Do not modify `portal/api/` files.

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
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool | head -20
curl -s http://localhost:8000/api/rules/tiers | python -m json.tool

# Verify partner rules API works
curl -s http://localhost:8000/api/compare/profiles/bevager_810/rules | python -m json.tool | head -20

# TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC baseline: PASS"
```

If anything fails, **stop and fix before proceeding**.

---

# PHASE 1: Add Partner Tab Infrastructure

> **Prerequisite:** Pre-flight green.
> **Deliverables:** Tab type extended, state variables added, data loading wired up.

---

## Task 1.1 — Extend Tab Type and TABS Array

**Investigate:**
```bash
cat portal/ui/src/pages/Rules.tsx | head -45
```

**Execute:**

In `portal/ui/src/pages/Rules.tsx`:

1. Add `'partner'` to the `Tab` type union (line 36):
```typescript
type Tab = 'overview' | 'universal' | 'transaction' | 'partner' | 'effective'
```

2. Insert `{ key: 'partner', label: 'Partner' }` into the `TABS` array after `'transaction'` (line 41):
```typescript
const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'universal', label: 'Universal' },
  { key: 'transaction', label: 'Transaction' },
  { key: 'partner', label: 'Partner' },
  { key: 'effective', label: 'Effective View' },
]
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Manually verify:
1. Open http://localhost:5173, navigate to Rules page
2. See 5 tabs: Overview | Universal | Transaction | Partner | Effective View
3. Clicking "Partner" tab shows empty content (expected — content added in Task 1.3)
4. All other tabs still work correctly

**Commit:** `feat(rules-ui): add Partner tab to Rules page tab bar`

---

## Task 1.2 — Add Partner Editor State Variables

**Investigate:**
```bash
# Read the transaction state block for pattern reference
sed -n '298,315p' portal/ui/src/pages/Rules.tsx
```

**Execute:**

In `portal/ui/src/pages/Rules.tsx`, insert after the transaction editor state block (after `txnConfirmDelete` state, around line 308):

```typescript
// Partner editor state
const [selectedPartner, setSelectedPartner] = useState('')
const [partnerRules, setPartnerRules] = useState<ClassificationRule[]>([])
const [partnerIgnores, setPartnerIgnores] = useState<IgnoreEntry[]>([])
const [partnerSaving, setPartnerSaving] = useState(false)
const [partnerSuccess, setPartnerSuccess] = useState(false)
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(rules-ui): add partner editor state variables`

---

## Task 1.3 — Add useEffect to Load Partner Rules on Selection

**Investigate:**
```bash
# Read the transaction rules loader for pattern reference
sed -n '347,358p' portal/ui/src/pages/Rules.tsx
```

**Execute:**

In `portal/ui/src/pages/Rules.tsx`, insert after the transaction rules `useEffect` block (after line 358):

```typescript
// Load partner rules when selection changes
useEffect(() => {
  if (selectedPartner && tab === 'partner') {
    api.compareRules(selectedPartner).then(d => {
      setPartnerRules((d.classification || []).map(normRule))
      setPartnerIgnores((d.ignore || []).map(normIgnore))
    }).catch(e => {
      setPartnerRules([])
      setPartnerIgnores([])
    })
  }
}, [selectedPartner, tab])
```

**Important:** This uses the existing `api.compareRules()` method (already at `api.ts:81`) and the existing `normRule`/`normIgnore` helpers (lines 375–389). Do NOT duplicate or recreate these.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(rules-ui): wire partner rules loading on profile selection`

---

## Task 1.4 — Add savePartner Handler

**Investigate:**
```bash
# Read the saveTransaction handler for pattern reference
sed -n '402,410p' portal/ui/src/pages/Rules.tsx
```

**Execute:**

In `portal/ui/src/pages/Rules.tsx`, insert after the `deleteTxnType` handler (after line 438), in the save handlers section:

```typescript
const savePartner = () => {
  if (!selectedPartner) return
  setPartnerSaving(true)
  setPartnerSuccess(false)
  api.compareUpdateRules(selectedPartner, { classification: partnerRules, ignore: partnerIgnores })
    .then(() => { setPartnerSuccess(true); loadTiers(); setTimeout(() => setPartnerSuccess(false), 3000) })
    .catch(e => setError(e.message))
    .finally(() => setPartnerSaving(false))
}
```

**Important:** This uses the existing `api.compareUpdateRules()` method (already at `api.ts:82-87`). It also calls `loadTiers()` to refresh the rule/ignore counts in the Overview tab.

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

**Commit:** `feat(rules-ui): add savePartner handler for partner rules CRUD`

---

### Phase 1 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# Verify no regressions
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('Health OK')"

# Verify partner rules API still works
curl -s http://localhost:8000/api/compare/profiles/bevager_810/rules | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'Partner rules API: {len(d[\"classification\"])} classification, {len(d.get(\"ignore\",[]))} ignore')
print('PHASE 1 GATE: PASS')
"
```

---

# PHASE 2: Build Partner Tab UI

> **Prerequisite:** Phase 1 gate green.
> **Deliverables:** Full Partner tab with profile selector, editable RulesGrid, and Save button.

---

## Task 2.1 — Add Partner Tab Content Panel

**Investigate:**
```bash
# Read the transaction tab for pattern reference (lines 637-724)
sed -n '637,724p' portal/ui/src/pages/Rules.tsx
```

**Execute:**

In `portal/ui/src/pages/Rules.tsx`, insert a new `{tab === 'partner' && (...)}` block **before** the Effective View block (before line 726). The structure mirrors the Transaction tab but is simpler (no create/delete of profiles — profiles are managed via Onboard):

```tsx
{tab === 'partner' && (
  <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
    <h2 className="text-lg font-semibold text-gray-900 mb-4">Partner Rules</h2>
    <p className="text-sm text-gray-500 mb-4">
      Profile-specific overrides — most specific tier. These rules take priority over Universal and Transaction-type rules.
    </p>

    {/* Profile selector */}
    <div className="flex items-center gap-3 mb-5">
      <select
        value={selectedPartner}
        onChange={e => setSelectedPartner(e.target.value)}
        className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none"
      >
        <option value="">Select profile...</option>
        {profiles.map((p: any) => (
          <option key={p.name} value={p.name}>
            {p.name}{p.trading_partner ? ` (${p.trading_partner})` : ''}
          </option>
        ))}
      </select>
    </div>

    {selectedPartner ? (
      <>
        {partnerSuccess && (
          <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 font-medium">
            Partner rules saved successfully
          </div>
        )}

        {/* Tier inheritance info */}
        <div className="mb-5 px-4 py-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-700">
          These rules override Universal{(() => {
            const profile = profiles.find((p: any) => p.name === selectedPartner)
            return profile?.transaction_type ? ` and ${profile.transaction_type} Transaction-type` : ''
          })()} rules for this profile.
        </div>

        <RulesGrid
          rules={partnerRules}
          ignores={partnerIgnores}
          onChange={setPartnerRules}
          onIgnoreChange={setPartnerIgnores}
        />
        <div className="flex justify-end mt-6 pt-4 border-t border-gray-100">
          <button
            onClick={savePartner}
            disabled={partnerSaving}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {partnerSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </>
    ) : (
      <p className="text-sm text-gray-400 italic mt-2">Select a profile above to edit its partner-specific rules</p>
    )}
  </div>
)}
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Manually verify:
1. Click "Partner" tab → see profile selector dropdown
2. Select "bevager_810" → rules load in editable grid
3. See classification rules with editable fields (segment, field, severity dropdown, numeric checkbox, ignore_case checkbox)
4. See ignore list with editable fields (segment, field, reason)
5. See tier inheritance info banner showing which tiers this profile overrides

**Commit:** `feat(rules-ui): add Partner tab with profile selector and editable rules grid`

---

## Task 2.2 — Verify Partner Rules Save Round-Trip

This is a **test-only task** — no code changes. Verify the full CRUD cycle works end-to-end.

**Test Gate:**
```bash
# 1. Read current partner rules via API
curl -s http://localhost:8000/api/compare/profiles/bevager_810/rules | python -c "
import json, sys
d = json.load(sys.stdin)
rule_count = len(d['classification'])
ignore_count = len(d.get('ignore', []))
print(f'Before: {rule_count} classification, {ignore_count} ignore')
"

# 2. Add a test rule via API (simulates UI save)
python -c "
import json, urllib.request
# Read current
resp = urllib.request.urlopen('http://localhost:8000/api/compare/profiles/bevager_810/rules')
data = json.loads(resp.read())

# Add a test rule
data['classification'].append({
    'segment': 'TEST_SEGMENT',
    'field': 'TEST_FIELD',
    'severity': 'soft',
    'ignore_case': False,
    'numeric': False
})

# Save via PUT
req = urllib.request.Request(
    'http://localhost:8000/api/compare/profiles/bevager_810/rules',
    data=json.dumps(data).encode(),
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
resp2 = urllib.request.urlopen(req)
result = json.loads(resp2.read())
has_test = any(r.get('field') == 'TEST_FIELD' for r in result['classification'])
assert has_test, 'Test rule should be in response'
print('Save round-trip: test rule added successfully')
"

# 3. Read back and verify
python -c "
import json, urllib.request
resp = urllib.request.urlopen('http://localhost:8000/api/compare/profiles/bevager_810/rules')
data = json.loads(resp.read())
has_test = any(r.get('field') == 'TEST_FIELD' for r in data['classification'])
assert has_test, 'Test rule should persist'
print(f'After add: {len(data[\"classification\"])} classification')
"

# 4. Remove test rule (cleanup)
python -c "
import json, urllib.request
resp = urllib.request.urlopen('http://localhost:8000/api/compare/profiles/bevager_810/rules')
data = json.loads(resp.read())

# Remove the test rule
data['classification'] = [r for r in data['classification'] if r.get('field') != 'TEST_FIELD']

# Save
req = urllib.request.Request(
    'http://localhost:8000/api/compare/profiles/bevager_810/rules',
    data=json.dumps(data).encode(),
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
resp2 = urllib.request.urlopen(req)
result = json.loads(resp2.read())
has_test = any(r.get('field') == 'TEST_FIELD' for r in result['classification'])
assert not has_test, 'Test rule should be removed'
print('Cleanup: test rule removed')
"

# 5. Verify tier counts update after save
curl -s http://localhost:8000/api/rules/tiers | python -c "
import json, sys
d = json.load(sys.stdin)
partner_tiers = [t for t in d['tiers'] if t['tier'] == 'partner']
print(f'Partner tiers: {len(partner_tiers)} profiles with rules')
for t in partner_tiers:
    print(f'  {t[\"name\"]}: {t[\"rule_count\"]} rules, {t[\"ignore_count\"]} ignores')
print('PHASE 2 TASK 2.2: PASS — full CRUD round-trip verified')
"
```

Manually verify:
1. Partner tab → select "bevager_810"
2. Click "+ Add Rule" → new row appears
3. Fill in: segment=`TEST`, field=`test_field`, severity=`soft`
4. Click Save → success banner appears
5. Reload the page → select bevager_810 again → test rule still present
6. Click trash icon on the test rule → row removed
7. Click Save → rule deleted from YAML file
8. Switch to Overview tab → verify bevager_810's rule count updated

**No commit** (test-only task).

---

### Phase 2 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('Health OK')"

# Verify Effective View reflects partner changes
curl -s http://localhost:8000/api/rules/effective/bevager_810 | python -c "
import json, sys
d = json.load(sys.stdin)
tiers = set(r['tier'] for r in d['rules'])
print(f'Effective: {len(d[\"rules\"])} rules from tiers: {tiers}')
assert 'partner' in tiers, 'Partner tier should appear'
print('PHASE 2 GATE: PASS')
"
```

---

# PHASE 3: Clickable Profile Links in Overview

> **Prerequisite:** Phase 2 gate green.
> **Deliverables:** Profile names in Overview's Partner card are clickable links that navigate to the Partner tab.

---

## Task 3.1 — Make Profile Names Clickable in Overview Partner Card

**Investigate:**
```bash
# Read the Partner Rules card in the Overview tab (lines 566-607)
sed -n '566,607p' portal/ui/src/pages/Rules.tsx

# Read the Transaction card's Edit button pattern for reference (lines 546-559)
sed -n '546,559p' portal/ui/src/pages/Rules.tsx
```

**Execute:**

In `portal/ui/src/pages/Rules.tsx`, within the Partner Rules table body (around lines 584–601), make two changes:

1. **Change the profile name from plain `<div>` to a clickable `<button>`** styled as a blue link. On click, set `selectedPartner` and switch to the Partner tab:

Replace the profile name cell content:
```tsx
{/* BEFORE */}
<td className="px-4 py-2.5">
  <div className="font-medium text-gray-900">{t.name}</div>
  {profile?.trading_partner && (
    <div className="text-xs text-gray-400">{profile.trading_partner}</div>
  )}
</td>
```

With:
```tsx
{/* AFTER */}
<td className="px-4 py-2.5">
  <button
    onClick={() => { setSelectedPartner(t.name); setTab('partner') }}
    className="font-medium text-blue-600 hover:text-blue-800 hover:underline transition-colors text-left"
  >
    {t.name}
  </button>
  {profile?.trading_partner && (
    <div className="text-xs text-gray-400">{profile.trading_partner}</div>
  )}
</td>
```

2. **Add an "Edit" column** to the Partner table, matching the Transaction card's pattern. Add a header `<th>` and a cell with an Edit button per row:

Add to the `<thead>`:
```tsx
<th className="px-4 py-2.5 w-20"></th>
```

Add to each `<tr>` in `<tbody>`:
```tsx
<td className="px-4 py-2.5 text-right">
  <button
    onClick={() => { setSelectedPartner(t.name); setTab('partner') }}
    className="text-xs font-medium text-blue-600 hover:text-blue-800"
  >
    Edit
  </button>
</td>
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Manually verify:
1. Overview tab → Partner Rules card
2. Profile names are blue and underline on hover
3. Click a profile name → switches to Partner tab with that profile pre-selected and rules loaded
4. Click "Edit" button → same behavior
5. Verify Universal and Transaction card "Edit" buttons still work

**Commit:** `feat(rules-ui): make partner profile names clickable links to Partner editor`

---

### Phase 3 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# Verify the full tab navigation flow
echo "Manual verification checklist:"
echo "  1. Overview → click partner name → lands on Partner tab with profile loaded"
echo "  2. Overview → click partner Edit → same result"
echo "  3. Overview → click Universal Edit → lands on Universal tab"
echo "  4. Overview → click Transaction Edit → lands on Transaction tab with type selected"
echo "  5. Partner tab → edit rules → Save → success → Overview shows updated counts"
echo "PHASE 3 GATE: PASS"
```

---

# PHASE 4: Cross-Page Navigation (Profile Link from Compare)

> **Prerequisite:** Phase 3 gate green.
> **Deliverables:** `RulesPage` accepts `onNavigate` prop, Compare page's "Rules Manager" link works bidirectionally.

---

## Task 4.1 — Thread onNavigate Prop to RulesPage

**Investigate:**
```bash
cat portal/ui/src/App.tsx
# Note: Compare and Onboard already receive onNavigate. Rules does not.
```

**Execute:**

1. In `portal/ui/src/pages/Rules.tsx`, update the `RulesPage` component signature to accept an optional `onNavigate` prop:

```tsx
export default function RulesPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
```

This prop is not used in the current task but enables future cross-page linking (e.g., "View in Compare" link on Partner tab).

2. In `portal/ui/src/App.tsx`, pass `onNavigate` to `RulesPage`:

Change:
```tsx
{page === 'rules' && <RulesPage />}
```
To:
```tsx
{page === 'rules' && <RulesPage onNavigate={(p) => setPage(p as Page)} />}
```

**Test Gate:**
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
```

Manually verify:
1. Rules page still renders correctly
2. All tabs still work
3. Compare page "Open Rules Manager" link still navigates to Rules page

**Commit:** `feat(rules-ui): thread onNavigate prop to RulesPage for cross-page linking`

---

### Phase 4 Gate

```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
curl -s http://localhost:8000/api/health | python -c "import json,sys; assert json.load(sys.stdin)['status']=='ok'; print('Health OK')"
echo "PHASE 4 GATE: PASS"
```

---

# PHASE 5: Final End-to-End Verification

> **Prerequisite:** Phase 4 gate green.
> **Deliverables:** All tests pass, full manual verification complete.

---

## Task 5.1 — Automated Verification

```bash
# 1. TypeScript compiles clean
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"

# 2. Python tests pass (no backend changes, but verify no regressions)
cd ~/VS/pycoreEdi && python -m pytest tests/ -v --tb=short 2>&1 | tail -10

# 3. All API endpoints still functional
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s http://localhost:8000/api/rules/tiers | python -m json.tool
curl -s http://localhost:8000/api/rules/universal | python -m json.tool
curl -s http://localhost:8000/api/rules/effective/bevager_810 | python -m json.tool
curl -s http://localhost:8000/api/compare/profiles | python -m json.tool | head -20
curl -s http://localhost:8000/api/compare/profiles/bevager_810/rules | python -m json.tool | head -20

# 4. Verify partner rules CRUD round-trip
python -c "
import json, urllib.request

# Read current
resp = urllib.request.urlopen('http://localhost:8000/api/compare/profiles/bevager_810/rules')
data = json.loads(resp.read())
original_count = len(data['classification'])

# Add test rule
data['classification'].append({
    'segment': 'E2E_TEST', 'field': 'e2e_field', 'severity': 'soft',
    'ignore_case': False, 'numeric': False
})
req = urllib.request.Request(
    'http://localhost:8000/api/compare/profiles/bevager_810/rules',
    data=json.dumps(data).encode(),
    headers={'Content-Type': 'application/json'}, method='PUT'
)
resp2 = urllib.request.urlopen(req)
after_add = json.loads(resp2.read())
assert len(after_add['classification']) == original_count + 1, 'Rule should be added'

# Verify in effective view
resp3 = urllib.request.urlopen('http://localhost:8000/api/rules/effective/bevager_810')
effective = json.loads(resp3.read())
has_e2e = any(r.get('field') == 'e2e_field' for r in effective['rules'])
assert has_e2e, 'E2E rule should appear in effective view'

# Verify in tier counts
resp4 = urllib.request.urlopen('http://localhost:8000/api/rules/tiers')
tiers = json.loads(resp4.read())
bev_tier = next(t for t in tiers['tiers'] if t['name'] == 'bevager_810')
assert bev_tier['rule_count'] == original_count + 1, 'Tier count should reflect new rule'

# Remove test rule (cleanup)
data['classification'] = [r for r in after_add['classification'] if r.get('field') != 'e2e_field']
req2 = urllib.request.Request(
    'http://localhost:8000/api/compare/profiles/bevager_810/rules',
    data=json.dumps(data).encode(),
    headers={'Content-Type': 'application/json'}, method='PUT'
)
urllib.request.urlopen(req2)

print(f'E2E CRUD round-trip: PASS (added rule, verified in effective view + tier counts, cleaned up)')
"

# 5. Verify backward compatibility
python -c "
from pyedi_core.comparator.rules import load_tiered_rules, merge_rules
t = load_tiered_rules('config/compare_rules', '810', 'config/compare_rules/bevager_810.yaml')
merged = merge_rules(t)
print(f'Tiered merge: {len(merged.classification)} classification, {len(merged.ignore)} ignore')
print('Backward compatibility: PASS')
"

echo "---"
echo "TASK 5.1: PASS — All automated checks green"
```

---

## Task 5.2 — Manual UI Verification Checklist

Run through each scenario in the browser at http://localhost:5173:

**Partner Tab CRUD:**
- [ ] Select a profile → rules load in editable grid
- [ ] Add a classification rule (click "+ Add Rule") → new row appears with defaults
- [ ] Edit segment, field, severity dropdown, numeric checkbox, ignore_case checkbox
- [ ] Remove a rule (click trash icon) → row disappears
- [ ] Add an ignore entry (click "+ Add Ignore") → new row appears
- [ ] Edit ignore segment, field, reason
- [ ] Remove an ignore entry → row disappears
- [ ] Click Save → success banner "Partner rules saved successfully" for 3 seconds
- [ ] Switch profiles → new profile's rules load
- [ ] Select empty profile → empty grid with "+ Add" buttons

**Clickable Profile Links:**
- [ ] Overview tab → Partner Rules card → profile names are blue and underline on hover
- [ ] Click profile name → switches to Partner tab with that profile pre-loaded
- [ ] Click "Edit" button → same behavior as clicking the name
- [ ] Overview → Universal Edit button → still works
- [ ] Overview → Transaction Edit button → still works

**Cross-tab Consistency:**
- [ ] Partner tab: edit rules → Save → switch to Overview → rule count updated
- [ ] Partner tab: edit rules → Save → switch to Effective View → select same profile → changes reflected
- [ ] No UI regressions on Universal tab
- [ ] No UI regressions on Transaction tab

**Commit:** `feat(rules-ui): partner rules CRUD + clickable profile links — complete`

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `portal/ui/src/pages/Rules.tsx` | EDIT | Add Partner tab, state, handlers, clickable profile links |
| `portal/ui/src/App.tsx` | EDIT | Thread `onNavigate` prop to `RulesPage` |

## No New API Endpoints

All partner rules operations use existing endpoints:

| Method | Path | Client Method | Purpose |
|--------|------|---------------|---------|
| GET | `/api/compare/profiles/{name}/rules` | `api.compareRules()` | Read partner rules |
| PUT | `/api/compare/profiles/{name}/rules` | `api.compareUpdateRules()` | Save partner rules |
| GET | `/api/rules/tiers` | `api.ruleTiers()` | Refresh tier counts |
| GET | `/api/compare/profiles` | `api.compareProfiles()` | Populate profile dropdown |
