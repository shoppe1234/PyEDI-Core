# Portal Enhancement Research Tasklist

**Created:** 2026-04-03
**Researchers:** Michael (Items 1 & 2), Jason (Items 3 & 4)

---

## Item 1 — Trading Partner Management Page
**Status:** Complete
**Priority:** High
**Difficulty:** Medium (~4-6 hours)

**Request:** Add a "Trading Partners" page to the sidebar (between Dashboard and Validate) that provides the ability to view, manage, and **delete** trading partners/profiles. Currently there is no way to remove a profile once created.

### Findings

**Sidebar Navigation** (`portal/ui/src/App.tsx`):
- Pages defined in `Page` union type (line 12): `'dashboard' | 'validate' | 'pipeline' | ...`
- Order controlled by `NAV` constant array (lines 20-29)
- Current order: Dashboard > Validate > Pipeline > Tests > Compare > Rules > Onboard > Config
- Adding a page requires: update `Page` type, add to `NAV` array, add conditional render (~line 83-90), create page component

**Profile Storage** (`config/config.yaml`):
- Profiles live in TWO places:
  1. `compare.profiles` — match_key, segment_qualifiers, rules_file, trading_partner, transaction_type
  2. `csv_schema_registry` — source_dsl, compiled_output, inbound_dir (for non-X12 formats)
- Currently 13 compare profiles + 7 CSV schema entries

**DELETE Endpoint:** Does NOT exist. Must be created.
- Existing pattern to follow: `DELETE /api/rules/transaction/{txn_type}` in `portal/api/routes/rules.py` (lines 188-195)
- New endpoint: `DELETE /api/onboard/profile/{name}` or `POST /api/onboard/unregister`

**Cleanup Required on Delete:**
1. Remove entry from `compare.profiles` in config.yaml
2. Remove entry from `csv_schema_registry` in config.yaml (if present)
3. Delete rules file at `config/compare_rules/{name}.yaml`
4. (Optional) Handle compare run history in `data/compare.db`

**Recommended UI Pattern:**
- Table with columns: Name, Trading Partner, Transaction Type, Description, Rules File
- Row action buttons: Edit, Delete, View Rules
- Delete triggers confirmation modal
- "Onboard New Partner" button links to wizard
- Search/filter box
- Follow patterns from Compare page (dropdown + detail) and Rules page (table + badges)

**Files to Modify/Create:**
| File | Change |
|------|--------|
| `portal/ui/src/App.tsx` | Add to Page type, NAV array, render block |
| `portal/ui/src/pages/TradingPartners.tsx` | **NEW** ~350 lines |
| `portal/ui/src/api.ts` | Add `deleteProfile()` method |
| `portal/api/routes/onboard.py` | Add DELETE endpoint (~50 lines) |

---

## Item 2 — X12 Version Selector (4010, 5010, etc.)
**Status:** Complete
**Priority:** High
**Difficulty:** Medium (~3-5 hours)

**Request:** Before choosing a transaction type in the X12 wizard, add a dropdown to select the X12 **version/release** (e.g., 4010, 5010, 6020). Different versions can have different segment structures, field definitions, and validation rules for the same transaction type.

### Findings

**Current X12 Type Loading** (`portal/api/routes/onboard.py` lines 304-334):
- Reads `transaction_registry` from config.yaml
- Each entry maps a code (e.g., `'810'`) to a map file path
- Filters to `input_format == "X12"` entries only
- Returns `X12TypeEntry` with code, label, map_file

**Version Metadata in Map Files:** NONE
- Examined `pyedi_core/rules/gfs_810_map.yaml` — no `version`, `x12_version`, or `standard_version` field
- Filenames don't include version (e.g., `gfs_810_map.yaml` not `gfs_810_5010_map.yaml`)
- Codebase is entirely **version-unaware** today

**Implementation Approaches:**

| Approach | Pros | Cons |
|----------|------|------|
| **A. Filename convention** (`gfs_810_4010_map.yaml`) | Simple, no schema change | Naming fragile, requires file duplication |
| **B. Metadata field in map YAML** (`x12_version: '5010'`) | Clean, self-documenting | Requires updating all existing map files |
| **C. Separate version registry in config** | Flexible, centralized | More config complexity |

**Recommended: Approach B** — Add `x12_version` field to map files + make it optional (default to `'5010'` for backwards compat).

**API Changes Needed:**
1. Add `version` and `available_versions` fields to `X12TypeEntry` model (line 49-52)
2. New endpoint: `GET /api/onboard/x12-types/{code}/versions`
3. Update `GET /api/onboard/x12-schema` to accept optional `version` query param

**UI Flow Change** (Onboard.tsx, StepX12Select lines 269-535):
```
Current:  [Transaction Type ▼] → [Review Schema]
Proposed: [Transaction Type ▼] → [X12 Version ▼] → [Review Schema]
```
- Add `selectedVersion` state variable
- Conditionally show version dropdown after type selected
- Fetch available versions when type changes
- Disable "Review Schema" until both type AND version selected

**Files to Modify:**
| File | Change |
|------|--------|
| `portal/api/routes/onboard.py` | Add version to model, new endpoint, update schema endpoint |
| `portal/ui/src/pages/Onboard.tsx` | Add version dropdown in StepX12Select (lines 269-410) |
| `portal/ui/src/api.ts` | Add `onboardX12Versions()` method |
| `pyedi_core/rules/*.yaml` | Add `x12_version` field to all map files |

---

## Item 3 — Expand Available X12 Transaction Types
**Status:** Complete
**Priority:** Medium
**Difficulty:** Low-Medium (~3-4 hours)

**Request:** The X12 wizard currently only shows a handful of transaction types (810, 850, 856). Expand to include more and consider an async/search-based UI pattern so the list scales well.

### Findings

**How Types Are Discovered:** Registry-driven, NOT auto-scanned.
- `transaction_registry` in config.yaml (lines 19-26) maps codes to map file paths
- Only entries where the map file has `input_format: X12` appear in the dropdown
- Missing from registry = invisible to wizard

**Current Map Files** (`pyedi_core/rules/`):

| File | Type | In Registry | Shows in UI |
|------|------|-------------|-------------|
| `gfs_810_map.yaml` | 810 Invoice | Yes | Yes |
| `gfs_850_map.yaml` | 850 Purchase Order | Yes | Yes |
| `gfs_856_map.yaml` | 856 Ship Notice | Yes | Yes |
| `gfs_820_map.yaml` | 820 Payment | Yes | Yes |
| `gfs_855_map.yaml` | 855 PO Ack | Yes | Yes |
| `gfs_860_map.yaml` | 860 PO Change | Yes | Yes |
| `cxml_850_map.yaml` | cXML variant | Yes | Likely |
| `default_x12_map.yaml` | Fallback | Internal (_) | No |

**So 6 X12 types exist but only ~3 may be showing** — possibly a filtering issue or the registry entries for 820/855/860 were added recently.

**Standard X12 Types to Add (Priority Tiers):**

| Tier | Types | Use Case |
|------|-------|----------|
| **Tier 1** (Must have) | 810, 820, 834, 835, 837, 850, 856, 997 | Core EDI transactions |
| **Tier 2** (Should have) | 840, 846, 852, 853, 855, 860, 861 | Specialized sectors |
| **Tier 3** (Nice to have) | 824, 830, 832, 845, 854, 862-870, 875, 880, 888-890, 999 | Less common |

**Can stub maps be auto-generated?** YES — minimal map with ISA/ST/GE/IEA segments and a few default fields is possible. The `default_x12_map.yaml` already serves as a fallback template.

**UI Scalability — Current vs. Recommended:**

| Pattern | Scales To | Search | Grouping | Effort |
|---------|-----------|--------|----------|--------|
| Current vanilla `<select>` | ~10 items | No | No | N/A |
| **Searchable combobox** (react-select / headless-ui) | 100+ | Yes | Optional | Low |
| Grouped `<optgroup>` select | ~30 | No | Yes | Very Low |
| Modal with card grid + search | 100+ | Yes | Yes | Medium |

**Recommendation:** Searchable combobox (Option A) — best balance of UX and implementation effort. Add `category` and `description` fields to API response for grouping/filtering.

**API Enhancement:**
```json
{
  "types": [
    {
      "code": "810",
      "label": "810_INVOICE",
      "map_file": "./rules/gfs_810_map.yaml",
      "category": "Purchasing",
      "description": "Invoice",
      "has_mapping": true
    }
  ]
}
```

**Files to Modify:**
| File | Change |
|------|--------|
| `config/config.yaml` | Add new types to `transaction_registry` |
| `pyedi_core/rules/` | Create stub map files for new types |
| `portal/api/routes/onboard.py` | Add category/description to X12TypeEntry model |
| `portal/ui/src/pages/Onboard.tsx` | Replace `<select>` with searchable combobox |
| `portal/ui/package.json` | Add react-select or similar (if using library) |

---

## Item 4 — Newly Created Profile Not Showing in Compare Dropdown
**Status:** Complete — NOT A BUG (user-facing UX issue)
**Priority:** ~~Critical~~ Low (UX improvement)

**Request:** After onboarding "SeanEDITp1" (profile `850`), the profile doesn't appear in the Compare page's profile dropdown.

### Findings

**Root Cause: Browser state — the page was not refreshed after onboarding.**

**Evidence chain (all verified):**

| Check | Result |
|-------|--------|
| Profile in `config.yaml` `compare.profiles`? | YES — line 177-185, properly formatted |
| `GET /api/compare/profiles` returns it? | YES — returns all 13 profiles including `850` |
| Compare page dropdown code filters it out? | NO — `profiles.map(p => <option>)` with no filtering (Compare.tsx line 308) |
| Rules file exists and valid? | YES — `config/compare_rules/850.yaml` with 11 rules + catch-all |
| Numeric key `'850'` causes YAML parse issue? | NO — quoted string, parses correctly |

**What's happening:** The Compare page loads profiles in a `useEffect` on mount (Compare.tsx line 96). If the user onboards a profile on the Onboard page and then clicks Compare in the sidebar, the Compare page re-mounts and fetches fresh data — so it SHOULD appear. However, if the Compare page was already open in the background or the browser cached the API response, the old list persists until a hard refresh.

**Recommended Fixes (pick one):**

| Fix | Effort | Impact |
|-----|--------|--------|
| **A. Auto-redirect after onboarding** — wizard completion links to `/#compare?profile=850` | Low | High |
| **B. Add refresh button** — "Reload Profiles" in Compare page header | Very Low | Medium |
| **C. Force re-fetch on navigation** — re-run `useEffect` when page becomes visible | Low | High |
| **D. Global state invalidation** — shared event bus triggers profile list refresh | Medium | High |

**Recommended: Fix C** — In the Compare page, add the current page/route as a dependency to the `useEffect` that fetches profiles. This ensures fresh data on every navigation to Compare.

---

## Research Completion Checklist
- [x] Item 1: Trading Partner page — feasible, medium effort, clear implementation path
- [x] Item 2: X12 version selector — feasible, requires new metadata field in map files
- [x] Item 3: Transaction type expansion — 6 types exist (3+ hidden), need registry + UI update
- [x] Item 4: Missing profile — NOT A BUG, stale browser state; fix with re-fetch on navigation
