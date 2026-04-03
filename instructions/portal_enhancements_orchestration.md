# Portal Enhancement Orchestration Prompt

**Created:** 2026-04-03  
**Research:** instructions/research_tasklist.md  
**Scope:** 4 items across 3 phases — Trading Partner Management + Stale Data Fix, X12 Version Selector, Transaction Type Expansion

---

## Execution Rules

- Read every file listed before modifying it.
- Match existing patterns exactly (Tailwind utility classes, `request<T>()` wrapper in api.ts, FastAPI router pattern in routes/).
- One phase at a time. Run the portal (`cd portal && python -m api.server`) and verify each phase works before starting the next.
- Do not install component libraries. Build the searchable combobox with vanilla React + Tailwind (the project has zero UI dependencies beyond React 19 and react-dom).
- All new Python functions require type hints. All new TypeScript functions require typed parameters and return types.
- When adding to config.yaml, preserve existing formatting and quoting conventions (single-quoted strings for values).

---

## Phase 0 — Global Profile Event Bus

**Goal:** Create a lightweight `CustomEvent`-based notification system so any page can react to profile changes (creation, deletion, update) without prop drilling or full-page refresh.

**Why:** Items 1 and 4 both need fresh profile data after mutations. A shared event bus solves both and scales to future pages.

### Steps

**0.1 — Create event helper** (`portal/ui/src/profileEvents.ts` — NEW, ~25 lines)

```typescript
// Event names
export const PROFILE_CHANGED = 'pyedi:profile-changed'

interface ProfileChangedDetail {
  action: 'created' | 'deleted' | 'updated'
  profileName: string
}

export function emitProfileChanged(detail: ProfileChangedDetail): void {
  window.dispatchEvent(new CustomEvent(PROFILE_CHANGED, { detail }))
}

export function useProfileChanged(callback: (detail: ProfileChangedDetail) => void): void {
  // useEffect that adds/removes the listener; deps: [callback]
}
```

- `emitProfileChanged()` — call after any profile mutation (onboard complete, delete, update).
- `useProfileChanged()` — hook that subscribes a component to the event; auto-cleans up on unmount.

**0.2 — Wire into Compare.tsx** (Fix for Item 4 — stale profile dropdown)

File: `portal/ui/src/pages/Compare.tsx`

Current code (lines 95-98):
```typescript
useEffect(() => {
  api.compareProfiles().then(setProfiles).catch(e => setError(e.message))
  loadRuns()
}, [])
```

Changes:
1. Import `useProfileChanged` from `../profileEvents`.
2. Extract the profile-fetch into a named function `loadProfiles()`.
3. Call `loadProfiles()` in the existing `useEffect([], ...)`.
4. Add `useProfileChanged(() => loadProfiles())` so the list refreshes when any page emits a profile change.

**0.3 — Wire into Onboard.tsx** (auto-redirect after wizard completion)

File: `portal/ui/src/pages/Onboard.tsx`

In the `saveRules()` function (lines 1135-1151), after `setWizard(prev => ({ ...prev, complete: true }))`:
1. Import and call `emitProfileChanged({ action: 'created', profileName: wizard.profileName })`.
2. In the success banner (lines 1163-1195), change the "Go to Compare" button to auto-navigate after 2 seconds with a countdown, OR make the button more prominent. Prefer the button approach (no auto-redirect timers — let the user control navigation).

### Verify Phase 0
- Onboard a test profile via the wizard → click "Go to Compare" → confirm the new profile appears in the dropdown without a page refresh.

---

## Phase 1 — Trading Partner Management Page + Delete API

**Goal:** Add a "Partners" page between Dashboard and Validate that lists all profiles with the ability to delete them. Combines research Items 1 and 4.

### Steps

**1.1 — Add DELETE endpoint** (`portal/api/routes/onboard.py`)

Follow the pattern from `portal/api/routes/rules.py` lines 188-195:

```python
@router.delete("/profile/{name}")
def delete_profile(name: str) -> dict[str, str]:
```

Logic:
1. Load `config/config.yaml` via the existing YAML helper used elsewhere in this file.
2. Remove `name` from `compare.profiles` (dict key lookup). 404 if not found.
3. Remove `name` from `csv_schema_registry` if present (non-X12 profiles live here too).
4. Delete the rules file at `config/compare_rules/{name}.yaml` if it exists (use `os.remove`, no error if missing).
5. Do NOT purge `data/compare.db` — orphan history is harmless and preserves audit trail.
6. Re-serialize and write config.yaml.
7. Return `{"status": "deleted", "profile": name}`.

**1.2 — Add `deleteProfile()` to api.ts** (`portal/ui/src/api.ts`)

Follow the existing pattern at lines 224-227:

```typescript
profileDelete: (name: string) =>
  request<{ status: string; profile: string }>(`/onboard/profile/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  }),
```

**1.3 — Update App.tsx** (`portal/ui/src/App.tsx`)

Three changes:

1. **Line 12** — Add `'partners'` to the `Page` union type:
   ```typescript
   type Page = 'dashboard' | 'partners' | 'validate' | 'pipeline' | ...
   ```

2. **Lines 20-29** — Add to `NAV` array between Dashboard and Validate:
   ```typescript
   { key: 'partners', label: 'Partners' },
   ```

3. **Lines 83-90** — Add conditional render block:
   ```typescript
   {page === 'partners' && <TradingPartners onNavigate={setPage} />}
   ```

4. Import `TradingPartners` from `./pages/TradingPartners`.

**1.4 — Create TradingPartners page** (`portal/ui/src/pages/TradingPartners.tsx` — NEW, ~300-350 lines)

**Data source:** `GET /api/compare/profiles` (already exists, returns all profiles with name, trading_partner, transaction_type, description, rules_file).

**Layout — follow the table pattern from Rules.tsx:**

| Column | Source Field | Notes |
|--------|-------------|-------|
| Name | `name` | Bold, primary identifier |
| Trading Partner | `trading_partner` | Gray if empty |
| Transaction Type | `transaction_type` | Badge styled (indigo for X12, emerald for CSV, amber for XML) |
| Description | `description` | Truncate if long |
| Rules File | `rules_file` | Mono font, link to Rules page |
| Actions | — | View Rules, Delete buttons |

**Features:**
- **Search/filter box** at top — filters by name, trading_partner, or transaction_type (client-side, same pattern as other pages).
- **"Onboard New Partner" button** — calls `onNavigate('onboard')`.
- **Delete button** — opens a confirmation dialog (use `window.confirm()` to stay consistent with the zero-dependency approach). On confirm:
  1. Call `api.profileDelete(name)`.
  2. On success, call `emitProfileChanged({ action: 'deleted', profileName: name })`.
  3. Remove from local state.
- **Row click → View Rules** — calls `onNavigate('rules')` (or a future deep-link).

**Styling tokens** (match existing pages):
- Card wrapper: `bg-white rounded-xl shadow-sm border border-gray-100 p-5`
- Table header: `text-xs uppercase text-gray-500 tracking-wider`
- Badge: `px-2 py-0.5 rounded-full text-xs font-medium` + color variants
- Delete button: `text-red-600 hover:text-red-800 text-sm`
- Primary button: `bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700`

**1.5 — Subscribe to profile events**

In TradingPartners.tsx, use `useProfileChanged()` to refresh the profile list when a profile is created or deleted from another page.

### Verify Phase 1
1. Navigate to Partners page → confirm all 16 profiles are listed.
2. Search for "810" → confirm filtering works.
3. Delete a test profile → confirm it disappears from the table AND from the Compare dropdown.
4. Onboard a new profile → navigate to Partners → confirm it appears without refresh.

---

## Phase 2 — X12 Version Selector

**Goal:** Add an `x12_version` metadata field to map files and a version dropdown to the X12 onboarding wizard (between type selection and schema review).

### Steps

**2.1 — Add `x12_version` field to all map files** (`pyedi_core/rules/`)

Add `x12_version: '5010'` as a top-level field to each X12 map file, right after `input_format`:

Files to update:
- `pyedi_core/rules/gfs_810_map.yaml` — add after line 3 (`input_format: 'X12'`)
- `pyedi_core/rules/gfs_850_map.yaml` — same position
- `pyedi_core/rules/gfs_856_map.yaml` — same position
- `pyedi_core/rules/default_x12_map.yaml` — same position
- `pyedi_core/rules/cxml_850_map.yaml` — skip (input_format is not X12, it's cXML)

Example result:
```yaml
transaction_type: '810_INVOICE'
input_format: 'X12'
x12_version: '5010'
schema:
  delimiter: '*'
```

**2.2 — Update X12TypeEntry model and endpoints** (`portal/api/routes/onboard.py`)

1. **Expand model** (line 49-52):
   ```python
   class X12TypeEntry(BaseModel):
       code: str
       label: str
       map_file: str
       version: str = '5010'
       available_versions: list[str] = ['5010']
   ```

2. **Update `GET /api/onboard/x12-types`** (lines 304-334):
   When reading each map file, also parse the `x12_version` field. Populate `version` with the value found (or `'5010'` as default). For `available_versions`, scan all map files that share the same transaction type code and collect distinct versions.

3. **Add endpoint** `GET /api/onboard/x12-types/{code}/versions`:
   ```python
   @router.get("/x12-types/{code}/versions")
   def get_x12_versions(code: str) -> dict[str, list[str]]:
   ```
   Returns `{"versions": ["4010", "5010"]}` by scanning map files for matching transaction_type.

4. **Update `GET /api/onboard/x12-schema`** to accept an optional `version` query param. When provided, prefer the map file matching that version. Fall back to default if no version-specific map exists.

**2.3 — Update api.ts** (`portal/ui/src/api.ts`)

Add:
```typescript
onboardX12Versions: (code: string) =>
  request<{ versions: string[] }>(`/onboard/x12-types/${encodeURIComponent(code)}/versions`),
```

Update `onboardX12Schema` to accept an optional `version` parameter and pass it as a query string.

**2.4 — Update StepX12Select UI** (`portal/ui/src/pages/Onboard.tsx`, lines 269-410)

Insert a version dropdown between transaction type selection and the "Load Schema" action:

1. Add state: `const [selectedVersion, setSelectedVersion] = useState<string>('')`
2. Add state: `const [availableVersions, setAvailableVersions] = useState<string[]>([])`
3. When a transaction type is selected, fetch versions via `api.onboardX12Versions(code)`.
4. Auto-select version if only one is available.
5. Show version dropdown only when `availableVersions.length > 1` (this keeps the UI clean until multi-version data exists).
6. Pass `selectedVersion` to `loadSchema()` → `api.onboardX12Schema()`.
7. Disable "Load Schema" / "Review" button until both type AND version are selected.

**Flow:**
```
Current:  [Transaction Type ▼] → [Load Schema]
New:      [Transaction Type ▼] → [Version ▼ (if multiple)] → [Load Schema]
```

### Verify Phase 2
1. Open Onboard → X12 → select "810" → version dropdown should auto-select "5010" (only version available) and may be hidden since there's only one option.
2. Schema loads correctly with version parameter.
3. If you manually add a second map file (e.g., `gfs_810_4010_map.yaml` with `x12_version: '4010'`), the dropdown should show both versions.

---

## Phase 3 — Expand Available X12 Transaction Types

**Goal:** Add Tier 1 standard X12 types to the registry with a `has_mapping` flag, and replace the vanilla `<select>` with a searchable combobox.

### Steps

**3.1 — Add `has_mapping` flag and metadata to X12TypeEntry** (`portal/api/routes/onboard.py`)

Update model:
```python
class X12TypeEntry(BaseModel):
    code: str
    label: str
    map_file: str
    version: str = '5010'
    available_versions: list[str] = ['5010']
    category: str = 'Other'
    description: str = ''
    has_mapping: bool = True
```

**3.2 — Expand transaction_registry in config.yaml** (`config/config.yaml`, lines 19-26)

Add Tier 1 types. For types without map files, point to `_default_x12` and set a convention that the endpoint can detect:

```yaml
transaction_registry:
  '810': ./rules/gfs_810_map.yaml
  '820': ./rules/gfs_820_map.yaml      # if exists, else _default_x12
  '834': ./rules/default_x12_map.yaml
  '835': ./rules/default_x12_map.yaml
  '837': ./rules/default_x12_map.yaml
  '850': ./rules/gfs_850_map.yaml
  '855': ./rules/gfs_855_map.yaml      # if exists
  '856': ./rules/gfs_856_map.yaml
  '860': ./rules/gfs_860_map.yaml      # if exists
  '997': ./rules/default_x12_map.yaml
  'cxml_850': ./rules/cxml_850_map.yaml
  '_default_x12': ./rules/default_x12_map.yaml
  '_rules_dir': ./rules
```

**Important:** Check which of `gfs_820_map.yaml`, `gfs_855_map.yaml`, `gfs_860_map.yaml` actually exist in `pyedi_core/rules/`. The research says 820/855/860 are in the registry but verify the map files exist. If they don't, point to `default_x12_map.yaml`.

**3.3 — Update the x12-types endpoint to compute `has_mapping` and metadata**

In `GET /api/onboard/x12-types` (lines 304-334):
1. Set `has_mapping = False` when the map_file resolves to `default_x12_map.yaml`.
2. Populate `category` and `description` from a static lookup dict:

```python
X12_META: dict[str, tuple[str, str]] = {
    '810': ('Purchasing', 'Invoice'),
    '820': ('Financial', 'Payment Order/Remittance Advice'),
    '834': ('Insurance', 'Benefit Enrollment and Maintenance'),
    '835': ('Insurance', 'Health Care Claim Payment/Advice'),
    '837': ('Insurance', 'Health Care Claim'),
    '850': ('Purchasing', 'Purchase Order'),
    '855': ('Purchasing', 'Purchase Order Acknowledgment'),
    '856': ('Shipping', 'Ship Notice/Manifest'),
    '860': ('Purchasing', 'Purchase Order Change Request'),
    '997': ('Acknowledgment', 'Functional Acknowledgment'),
}
```

**3.4 — Update api.ts types**

Update the TypeScript interface to include the new fields:
```typescript
interface X12TypeEntry {
  code: string
  label: string
  map_file: string
  version: string
  available_versions: string[]
  category: string
  description: string
  has_mapping: boolean
}
```

**3.5 — Build searchable combobox in StepX12Select** (`portal/ui/src/pages/Onboard.tsx`)

Replace the vanilla `<select>` (around lines 269-410) with a custom searchable combobox built in vanilla React + Tailwind. No external dependencies.

**Component behavior:**
- Text input that filters the dropdown as you type.
- Dropdown shows matching types grouped by `category`.
- Each option shows: `code` (bold) + `description` + `has_mapping` badge.
- Types with `has_mapping: false` show a warning badge ("Stub — basic mapping only") but are still selectable.
- Selecting a type closes the dropdown and populates the input.
- Keyboard navigation: arrow keys, Enter to select, Escape to close.
- Click outside closes dropdown.

**Implementation pattern:**
```typescript
const [query, setQuery] = useState('')
const [open, setOpen] = useState(false)
const filtered = types.filter(t =>
  t.code.includes(query) || t.description.toLowerCase().includes(query.toLowerCase())
)
const grouped = Object.groupBy(filtered, t => t.category)
```

Use `useRef` for the container and a click-outside listener. Use `onKeyDown` for keyboard nav.

**Visual layout:**
```
┌─────────────────────────────────┐
│ 🔍 Search transaction types...  │
├─────────────────────────────────┤
│ Purchasing                      │
│   810 — Invoice            ✓    │
│   850 — Purchase Order     ✓    │
│   855 — PO Acknowledgment  ✓    │
│   860 — PO Change Request  ✓    │
│ Financial                       │
│   820 — Payment Order      ✓    │
│ Insurance                       │
│   834 — Benefit Enrollment ⚠    │
│   835 — Claim Payment      ⚠    │
│   837 — Health Care Claim  ⚠    │
│ Shipping                        │
│   856 — Ship Notice        ✓    │
│ Acknowledgment                  │
│   997 — Functional Ack     ⚠    │
└─────────────────────────────────┘
  ✓ = has_mapping    ⚠ = stub
```

**3.6 — Show warning when stub type is selected**

If the user selects a type with `has_mapping: false`, display an amber banner below the combobox:

```
⚠ This transaction type uses a basic default mapping. The generated schema will include
  only envelope segments (ISA/GS/ST/SE/GE/IEA). You can customize the mapping after onboarding.
```

### Verify Phase 3
1. Open Onboard → X12 → type dropdown shows all Tier 1 types grouped by category.
2. Search for "835" → only insurance types shown.
3. Select "835" (stub) → warning banner appears.
4. Select "810" (full mapping) → no warning, schema loads normally.
5. Complete a full onboarding with a stub type → profile is created successfully with basic rules.

---

## File Change Summary

| File | Phase | Change |
|------|-------|--------|
| `portal/ui/src/profileEvents.ts` | 0 | **NEW** — event bus (~25 lines) |
| `portal/ui/src/pages/Compare.tsx` | 0 | Add `useProfileChanged` hook to refresh profiles |
| `portal/ui/src/pages/Onboard.tsx` | 0, 2, 3 | Emit profile event on complete; version dropdown; searchable combobox |
| `portal/ui/src/App.tsx` | 1 | Add `partners` to Page type, NAV, render block |
| `portal/ui/src/pages/TradingPartners.tsx` | 1 | **NEW** — partner management page (~300-350 lines) |
| `portal/ui/src/api.ts` | 1, 2, 3 | Add `profileDelete`, `onboardX12Versions`, update types |
| `portal/api/routes/onboard.py` | 1, 2, 3 | Add DELETE endpoint, version endpoint, expand model |
| `pyedi_core/rules/gfs_810_map.yaml` | 2 | Add `x12_version: '5010'` |
| `pyedi_core/rules/gfs_850_map.yaml` | 2 | Add `x12_version: '5010'` |
| `pyedi_core/rules/gfs_856_map.yaml` | 2 | Add `x12_version: '5010'` |
| `pyedi_core/rules/default_x12_map.yaml` | 2 | Add `x12_version: '5010'` |
| `config/config.yaml` | 3 | Expand `transaction_registry` with Tier 1 types |

---

## Estimated Touch Points
- **New files:** 2
- **Modified files:** 10
- **New API endpoints:** 2 (DELETE profile, GET versions)
- **Modified API endpoints:** 2 (GET x12-types, GET x12-schema)
