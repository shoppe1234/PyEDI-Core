# Standards-Driven Onboard Orchestration Prompt

**Created:** 2026-04-03  
**Scope:** Replace hardcoded X12 type/version lists with dynamic discovery from certPortal `.ediSchema` standard files. 5 phases + testing phase.  
**Source of truth:** `standards/x12/{version}/schemas/Message*.ediSchema` files copied from certPortal.  
**Constraint:** Nothing may reference `com.extol.ebi.edi.standard` — strip that prefix everywhere; use `x12/{version}` identifiers only.

---

## Execution Rules

- Read every file listed before modifying it.
- Match existing patterns exactly (Tailwind utility classes, `request<T>()` wrapper in api.ts, FastAPI router pattern in routes/).
- One phase at a time. Run the portal (`cd portal && python -m api.server`) and verify each phase works before starting the next.
- All new Python functions require type hints. All new TypeScript functions require typed parameters and return types.
- When adding to config.yaml, preserve existing formatting and quoting conventions (single-quoted strings for values).
- Do not install new Python or JS dependencies — the `.ediSchema` parser must be pure Python.
- The `.ediSchema` DSL is a proprietary format. The parser does NOT need to handle every edge case — focus on extracting the data the onboard wizard needs (message code, name, version, segments, segment groups, cardinality).

---

## Phase 0 — Copy Standards into pycoreEdi

**Goal:** Copy the X12 standards directories from certPortal into pycoreEdi with clean naming.

### Steps

**0.1 — Copy and rename directories**

Source: `C:\Users\SeanHoppe\VS\certPortal\standards\`

Copy only X12 directories. Strip the `com.extol.ebi.edi.standard.` prefix and the `.schemas_3.1.0.*` suffix.

Target structure inside `pycoreEdi/`:
```
standards/
  x12/
    v003040/
      schemas/
        Message100.ediSchema
        Message104.ediSchema
        ...
    v003050/
      schemas/
        ...
    v004010/
      schemas/
        Message810.ediSchema
        Message850.ediSchema
        ...  (294 files)
    v004030/
      schemas/
        ...
    v005010/
      schemas/
        ...  (318 files)
```

Copy only the `schemas/` subdirectory from each source — skip `META-INF/` and `about.html`.

**0.2 — Add `standards/` to `.gitignore`**

Add this line to the project `.gitignore`:
```
standards/
```

These files are large (19,000+ lines each for major transactions) and come from an external source. They should not be committed.

**0.3 — Add `standards_dir` to config.yaml**

Add a top-level key to `config/config.yaml`:
```yaml
standards_dir: './standards'
```

This tells the API where to find the standards. Use relative path from project root.

### Verify Phase 0
- Confirm `standards/x12/v004010/schemas/Message810.ediSchema` exists and line 1 does NOT contain `com.extol.ebi.edi.standard` (note: the file content inside will still have the package declaration — that's fine, we never expose the package line to the UI).
- Confirm 5 version directories exist under `standards/x12/`.
- Confirm `standards/` is in `.gitignore`.

---

## Phase 1 — Build the `.ediSchema` Parser

**Goal:** Create a Python module that parses `.ediSchema` files and extracts structured data the onboard wizard needs.

### File: `pyedi_core/standards_parser.py` (NEW, ~200-250 lines)

### 1.1 — Understand the DSL grammar

Each `.ediSchema` file follows this structure:

```
package com.extol.ebi.edi.^standard.x12.v004010;

def standard {
    def message 810 {
        name = "Invoice"
        functionalGroup = functionalGroups.IN
        version = "004010"
        standardsClass = "X"
        industryGroup = "X"

        def area 1 {
            010 segment ST [1..1]
            020 segment BIG [1..1]
            030 segment NTE [0..100]
            040 segmentGroup N1 [0..200]

            def segmentGroup N1 {
                name = "N1"
                070 segment N1 [0..1]
                080 segment N2 [0..2]
            }
        }

        def area 2 { ... }
        def area 3 { ... }
    }

    def segment BIG {
        name = "Beginning Segment for Invoice"
        01 simpleElement 373 [1..1]
        02 simpleElement 76 [1..1]
        ...
    }

    def simpleElement 373 {
        name = "Date"
        type = types.DT
        minLength = 8
        maxLength = 8
    }
}
```

Key points:
- **Message definition** contains `name`, `version`, `functionalGroup`, and area blocks.
- **Areas** contain segment references with cardinality `[min..max]` and segment group definitions.
- **Segment definitions** list their elements (simpleElement or compositeElement) with position numbers.
- **Simple element definitions** have `name`, `type`, `minLength`, `maxLength`, and optional `identifierValues`.
- Line numbers before segment references vary: 3-digit (v004010) or 4-digit (v005010/EDIFACT).
- Cardinality can be `[1..1]`, `[0..100]`, `[0..999999]`, `[]` (unbounded), or `[1..*]`.

### 1.2 — Data models

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class SegmentRef:
    """A segment or segment group reference within an area."""
    name: str
    ref_type: str  # "segment" or "segmentGroup"
    min_occurs: int
    max_occurs: int  # -1 for unbounded
    children: List['SegmentRef'] = field(default_factory=list)  # nested refs for groups

@dataclass
class ElementDef:
    """An element within a segment definition."""
    position: int  # 1-based position (01, 02, ...)
    element_id: str  # e.g., "373", "C040"
    element_type: str  # "simpleElement" or "compositeElement"
    min_occurs: int
    max_occurs: int
    name: str = ''  # resolved from element definition if available
    data_type: str = ''  # e.g., "ID", "AN", "DT", "N2"

@dataclass
class SegmentDef:
    """A segment definition with its elements."""
    code: str  # e.g., "BIG", "ST"
    name: str  # e.g., "Beginning Segment for Invoice"
    elements: List[ElementDef] = field(default_factory=list)

@dataclass
class MessageSchema:
    """Parsed representation of a single .ediSchema message."""
    code: str  # e.g., "810", "850"
    name: str  # e.g., "Invoice", "Purchase Order"
    version: str  # e.g., "004010", "005010"
    functional_group: str  # e.g., "IN", "PO"
    standard_type: str  # "x12" or "edifact"
    areas: List[List[SegmentRef]] = field(default_factory=list)
    segment_defs: Dict[str, SegmentDef] = field(default_factory=dict)
```

### 1.3 — Parser functions

```python
def parse_edi_schema(file_path: Path) -> MessageSchema:
    """Parse a .ediSchema file and return a MessageSchema."""
```

Implementation approach — use **line-by-line parsing with a state machine**, not regex on the full file. The files are 900 to 22,000+ lines. Strategy:

1. Read all lines into a list.
2. Track nesting depth via brace counting (`{` increments, `}` decrements).
3. Use a state enum: `TOP`, `MESSAGE`, `AREA`, `SEGMENT_GROUP`, `SEGMENT_DEF`, `ELEMENT_DEF`.
4. Extract metadata with simple string matching:
   - `name = "..."` → `name`
   - `version = "..."` → `version`
   - `functionalGroup = functionalGroups.XX` → `functional_group`
5. Parse segment references with a regex:
   - Pattern: `\d+\s+(segment|segmentGroup)\s+(\w+)\s+\[(\d+)\.\.(\d+|\*)\]`
   - Also handle `[]` (empty cardinality → unbounded).
6. Parse segment definitions (`def segment XXX { ... }`) to extract element lists.
7. Parse simple element definitions to get `name` and `type`.
8. Do NOT parse composite element internals — not needed for the wizard.

```python
def scan_standards_dir(standards_dir: Path) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """Scan standards directory and return catalog of available types and versions.
    
    Returns:
        {
            "x12": {
                "4010": [
                    {"code": "810", "name": "Invoice", "file": "Message810.ediSchema"},
                    {"code": "850", "name": "Purchase Order", "file": "Message850.ediSchema"},
                    ...
                ],
                "5010": [...],
            }
        }
    """
```

This function should:
1. Glob for `standards/x12/v*/schemas/Message*.ediSchema`.
2. For each file, do a **lightweight parse** — only read the first ~20 lines to extract `def message XXX` and `name = "..."`. Do NOT parse the full 19,000-line file for a catalog scan.
3. Extract the version from the directory name (e.g., `v004010` → `4010`).
4. Return grouped by standard_type → version → list of transactions.

```python
def get_message_segments(file_path: Path) -> List[str]:
    """Quick extraction of top-level segment codes from a message schema.
    
    Returns a flat list like ["ST", "BIG", "NTE", "N1", "N2", "N3", "N4", ...].
    Used by the wizard to show which segments exist in this transaction.
    """
```

### 1.4 — Performance consideration

The catalog scan (`scan_standards_dir`) will read ~318 files per version × 5 versions = ~1,590 files. Since it only reads the first ~20 lines of each, this should be fast (<1 second). But add an in-memory cache:

```python
_CATALOG_CACHE: Optional[Dict] = None
_CATALOG_CACHE_TIME: float = 0

def get_catalog(standards_dir: Path, max_age: float = 300.0) -> Dict:
    """Return cached catalog, refreshing if older than max_age seconds."""
```

### Verify Phase 1
- Write a quick test: `python -c "from pyedi_core.standards_parser import parse_edi_schema, scan_standards_dir; from pathlib import Path; ..."`
- Verify `parse_edi_schema("standards/x12/v004010/schemas/Message810.ediSchema")` returns a `MessageSchema` with `code='810'`, `name='Invoice'`, `version='004010'`, and areas containing segment refs like `ST`, `BIG`, `NTE`, `N1`.
- Verify `scan_standards_dir(Path("standards"))` returns a dict with `"x12"` key containing 5 versions and 100+ transactions per version.
- Verify the 997 schema (a small ~900-line file) parses correctly as a smoke test.

---

## Phase 2 — New API Endpoints for Standards Discovery

**Goal:** Add API endpoints that serve the standards catalog and individual schema details dynamically.

### File: `portal/api/routes/onboard.py` (MODIFY)

### 2.1 — Add imports and config reader

At the top of `onboard.py`, add:
```python
from pyedi_core.standards_parser import scan_standards_dir, parse_edi_schema, MessageSchema
```

Add a helper to resolve the standards directory:
```python
def _get_standards_dir() -> Path:
    """Resolve standards directory from config or default."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        rel = config.get("standards_dir", "./standards")
    else:
        rel = "./standards"
    return _PROJECT_ROOT / rel
```

### 2.2 — New endpoint: `GET /api/onboard/standards`

```python
class StandardVersion(BaseModel):
    version: str  # e.g., "4010"
    transaction_count: int

class StandardType(BaseModel):
    standard: str  # "x12"
    versions: List[StandardVersion]

class StandardsCatalogResponse(BaseModel):
    standards: List[StandardType]

@router.get("/standards", response_model=StandardsCatalogResponse)
def standards_catalog() -> StandardsCatalogResponse:
    """Return available EDI standards and their versions from the standards directory."""
```

Returns:
```json
{
  "standards": [
    {
      "standard": "x12",
      "versions": [
        {"version": "3040", "transaction_count": 187},
        {"version": "3050", "transaction_count": 225},
        {"version": "4010", "transaction_count": 294},
        {"version": "4030", "transaction_count": 309},
        {"version": "5010", "transaction_count": 318}
      ]
    }
  ]
}
```

### 2.3 — New endpoint: `GET /api/onboard/standards/{standard}/{version}/transactions`

```python
class StandardTransaction(BaseModel):
    code: str  # "810"
    name: str  # "Invoice"
    file: str  # "Message810.ediSchema"
    has_mapping: bool  # True if a custom mapping YAML exists in transaction_registry

class TransactionsResponse(BaseModel):
    standard: str
    version: str
    transactions: List[StandardTransaction]

@router.get("/standards/{standard}/{version}/transactions", response_model=TransactionsResponse)
def standards_transactions(standard: str, version: str) -> TransactionsResponse:
    """Return all transaction types for a given standard and version."""
```

Logic:
1. Call `scan_standards_dir()` to get the catalog.
2. Filter to the requested standard and version.
3. For each transaction, check if it exists in `transaction_registry` in config.yaml and has a non-default mapping file → set `has_mapping`.
4. Sort transactions by code (numeric sort for X12).
5. Return 404 if standard or version not found.

### 2.4 — New endpoint: `GET /api/onboard/standards/{standard}/{version}/{code}/schema`

```python
class StandardSegmentRef(BaseModel):
    name: str
    ref_type: str  # "segment" or "segmentGroup"
    min_occurs: int
    max_occurs: int
    children: List['StandardSegmentRef'] = []

class StandardElementDef(BaseModel):
    position: int
    name: str
    data_type: str
    min_occurs: int
    max_occurs: int

class StandardSegmentDef(BaseModel):
    code: str
    name: str
    elements: List[StandardElementDef]

class StandardSchemaResponse(BaseModel):
    code: str
    name: str
    version: str
    standard: str
    functional_group: str
    areas: List[List[StandardSegmentRef]]
    segment_defs: Dict[str, StandardSegmentDef]
    has_mapping: bool
    match_key_default: Dict[str, str]

@router.get("/standards/{standard}/{version}/{code}/schema", response_model=StandardSchemaResponse)
def standards_schema(standard: str, version: str, code: str) -> StandardSchemaResponse:
    """Parse and return the full schema for a specific transaction type."""
```

Logic:
1. Locate the `.ediSchema` file: `standards/{standard}/v{version_padded}/schemas/Message{code}.ediSchema`
   - Version padding: "4010" → "v004010", "5010" → "v005010"
2. Call `parse_edi_schema()` on it.
3. Convert the `MessageSchema` dataclass to the response model.
4. Look up `match_key_default` from `_X12_MATCH_KEY_DEFAULTS` dict (existing code).
5. Check `has_mapping` from `transaction_registry`.
6. Return 404 if file not found.

### 2.5 — Update existing `GET /api/onboard/x12-types` endpoint

Modify the existing `x12_types()` function so it **also** merges in data from the standards directory. The standards become the primary source; the `transaction_registry` just indicates which have custom mappings.

Updated logic:
1. Scan the standards directory for all X12 transactions across all versions.
2. For each transaction, check the `transaction_registry` to see if a custom mapping exists.
3. Return the merged list with `has_mapping`, `available_versions`, `category`, and `description` populated.
4. Keep backward compatibility — existing consumers of this endpoint should still work.

### 2.6 — Update existing `GET /api/onboard/x12-types/{code}/versions`

Change this endpoint to read versions from the standards directory instead of scanning mapping YAML files:

```python
@router.get("/x12-types/{code}/versions")
def get_x12_versions(code: str) -> Dict[str, List[str]]:
    """Return available X12 versions for a transaction type from standards."""
    standards_dir = _get_standards_dir()
    catalog = scan_standards_dir(standards_dir)
    x12 = catalog.get("x12", {})
    versions = [v for v, txns in x12.items() if any(t["code"] == code for t in txns)]
    if not versions:
        raise HTTPException(status_code=404, detail=f"No versions found for '{code}'")
    return {"versions": sorted(versions)}
```

### Verify Phase 2
- `curl http://localhost:18041/api/onboard/standards` → returns x12 with 5 versions.
- `curl http://localhost:18041/api/onboard/standards/x12/4010/transactions` → returns 294 transactions.
- `curl http://localhost:18041/api/onboard/standards/x12/4010/810/schema` → returns full 810 schema with segments, areas, and element definitions.
- `curl http://localhost:18041/api/onboard/x12-types` → still works, now includes all transactions from standards.
- `curl http://localhost:18041/api/onboard/x12-types/810/versions` → returns `["3040", "3050", "4010", "4030", "5010"]`.

---

## Phase 3 — Update the Frontend API Client

**Goal:** Add TypeScript functions and types for the new standards endpoints.

### File: `portal/ui/src/api.ts` (MODIFY)

### 3.1 — Add new types

Read the current `api.ts` first. Add these types near the existing onboard types:

```typescript
interface StandardVersion {
  version: string
  transaction_count: number
}

interface StandardType {
  standard: string
  versions: StandardVersion[]
}

interface StandardTransaction {
  code: string
  name: string
  file: string
  has_mapping: boolean
}

interface StandardSegmentRef {
  name: string
  ref_type: string
  min_occurs: number
  max_occurs: number
  children: StandardSegmentRef[]
}

interface StandardElementDef {
  position: number
  name: string
  data_type: string
  min_occurs: number
  max_occurs: number
}

interface StandardSegmentDef {
  code: string
  name: string
  elements: StandardElementDef[]
}

interface StandardSchemaResponse {
  code: string
  name: string
  version: string
  standard: string
  functional_group: string
  areas: StandardSegmentRef[][]
  segment_defs: Record<string, StandardSegmentDef>
  has_mapping: boolean
  match_key_default: Record<string, string>
}
```

### 3.2 — Add new API methods

Add to the `api` object:

```typescript
standardsCatalog: () =>
  request<{ standards: StandardType[] }>('/onboard/standards'),

standardsTransactions: (standard: string, version: string) =>
  request<{ standard: string; version: string; transactions: StandardTransaction[] }>(
    `/onboard/standards/${encodeURIComponent(standard)}/${encodeURIComponent(version)}/transactions`
  ),

standardsSchema: (standard: string, version: string, code: string) =>
  request<StandardSchemaResponse>(
    `/onboard/standards/${encodeURIComponent(standard)}/${encodeURIComponent(version)}/${encodeURIComponent(code)}/schema`
  ),
```

### Verify Phase 3
- No runtime test yet — this is just types and fetch wrappers. Verify no TypeScript compilation errors: `cd portal/ui && npx tsc --noEmit`.

---

## Phase 4 — Update the Onboard Wizard UI

**Goal:** Replace hardcoded version/type selection in the X12 wizard with dynamic discovery from standards endpoints. The user can now select any X12 version and any transaction type from the standards.

### File: `portal/ui/src/pages/Onboard.tsx` (MODIFY)

Read the entire Onboard.tsx before making changes. The X12 selection logic lives in the `StepX12Select` component (approximately lines 270-699).

### 4.1 — Add new state variables to StepX12Select

Add these state variables alongside the existing ones:

```typescript
const [standardVersions, setStandardVersions] = useState<StandardVersion[]>([])
const [standardTransactions, setStandardTransactions] = useState<StandardTransaction[]>([])
const [selectedStandard] = useState<string>('x12')  // hardcoded for now, EDIFACT later
const [selectedVersion, setSelectedVersion] = useState<string>('')
const [loadingVersions, setLoadingVersions] = useState(false)
const [loadingTransactions, setLoadingTransactions] = useState(false)
```

### 4.2 — Fetch versions on mount

Replace the existing `useEffect` that calls `api.onboardX12Types()` with:

```typescript
useEffect(() => {
  setLoadingVersions(true)
  api.standardsCatalog()
    .then(res => {
      const x12 = res.standards.find(s => s.standard === 'x12')
      if (x12) {
        setStandardVersions(x12.versions)
        // Auto-select highest version (5010)
        const highest = x12.versions.sort((a, b) => b.version.localeCompare(a.version))[0]
        if (highest) setSelectedVersion(highest.version)
      }
    })
    .catch(e => console.error('Failed to load standards:', e))
    .finally(() => setLoadingVersions(false))
}, [])
```

### 4.3 — Fetch transactions when version changes

```typescript
useEffect(() => {
  if (!selectedVersion) return
  setLoadingTransactions(true)
  setStandardTransactions([])
  setSelectedCode('')
  api.standardsTransactions(selectedStandard, selectedVersion)
    .then(res => setStandardTransactions(res.transactions))
    .catch(e => console.error('Failed to load transactions:', e))
    .finally(() => setLoadingTransactions(false))
}, [selectedStandard, selectedVersion])
```

### 4.4 — Add version selector UI

Insert a version dropdown BEFORE the transaction type combobox. Style it to match the existing combobox pattern:

```tsx
{/* Version Selector */}
<div className="mb-4">
  <label className="block text-sm font-medium text-gray-700 mb-1">X12 Version</label>
  <select
    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
    value={selectedVersion}
    onChange={e => setSelectedVersion(e.target.value)}
    disabled={loadingVersions}
  >
    {standardVersions.map(v => (
      <option key={v.version} value={v.version}>
        {v.version} ({v.transaction_count} transaction types)
      </option>
    ))}
  </select>
</div>
```

### 4.5 — Update the transaction type combobox data source

The existing combobox filters `x12Types` (fetched from `api.onboardX12Types()`). Replace this data source with `standardTransactions`:

1. The combobox dropdown items should use `standardTransactions` instead of `x12Types`.
2. Each item shows: `code` (bold), `name`, and a badge if `has_mapping` is true.
3. Items without `has_mapping` get a subtle "(standard only)" label — they can still be selected.
4. Keep the existing search/filter logic — it should work on `code` and `name`.
5. Keep the existing keyboard navigation.
6. Grouping: since the standards don't have a `category` field, group by first digit of code (1xx, 2xx, ..., 8xx, 9xx) or just show a flat sorted list. Flat sorted list is cleaner for 200+ items.

### 4.6 — Update schema loading

When the user clicks to load/review the schema:

1. **If `has_mapping` is true** (custom mapping YAML exists): Use the existing `api.onboardX12Schema()` call — this gives the richer field-level mapping data.
2. **If `has_mapping` is false** (standard only): Call `api.standardsSchema(selectedStandard, selectedVersion, selectedCode)` to get the segment structure from the `.ediSchema` file.
3. Convert the `StandardSchemaResponse` into the `X12Schema` interface that the rest of the wizard expects. The conversion:
   - `transaction_type` = `code`
   - `input_format` = `"X12"`
   - `segments` = flat list of all unique segment codes from all areas
   - `fields` = derive from segment definitions: for each segment, list its elements as `{name: "SEG" + position.padStart(2, '0'), source: segment.code + "." + position, section: area_index === 0 ? "header" : area_index === 1 ? "lines" : "summary"}`
   - `match_key_default` = from the response

### 4.7 — Show standard schema info banner

When a standard-only type is selected (no custom mapping), show an info banner:

```
ℹ This transaction type is loaded from the X12 {version} standard definition.
  Segment structure is shown below. A custom field mapping can be uploaded after onboarding.
```

Style: blue info banner matching existing banner patterns in the wizard.

### 4.8 — Keep "Upload New Mapping" mode working

The existing `mode: 'existing' | 'upload'` toggle should still work. When the user switches to "Upload New Mapping", the version/type selection is bypassed — they upload a YAML file directly. No changes needed to this path.

### Verify Phase 4
1. Open Onboard → X12.
2. Version dropdown appears with 5 versions (3040, 3050, 4010, 4030, 5010). 5010 auto-selected.
3. Transaction type combobox shows ~318 transaction types.
4. Search "810" → filters to 810.
5. Select 810 → schema loads showing segments (BIG, NTE, N1, ITD, DTM, etc.) and fields.
6. Change version to 4010 → transaction list refreshes (294 items). Select 810 again → schema shows 4010 version.
7. Select a type without custom mapping (e.g., 270) → info banner appears, standard segments shown.
8. Select a type with custom mapping (e.g., 810) → existing mapping schema shown (richer field data).
9. Switch to "Upload New Mapping" mode → works as before.
10. Continue through Register Partner step → works as before.
11. Continue through Configure Rules step → rules auto-seed correctly.
12. Complete the wizard → profile created successfully.

---

## Phase 5 — Update Existing Endpoints for Backward Compatibility

**Goal:** Ensure the legacy `x12-types` and `x12-schema` endpoints still work for any consumers, but now source their data from the standards directory.

### File: `portal/api/routes/onboard.py` (MODIFY)

### 5.1 — Update `_X12_META` dict

Expand `_X12_META` to include descriptions for all common transaction types. Use the `name` field from the `.ediSchema` files as the description. For common types that already have category metadata, keep them. For new types discovered from standards, default to `category='Other'`.

Do not hardcode all 318 types. Instead, update the `x12_types()` endpoint to:
1. Start with the standards catalog as the base.
2. Overlay the `_X12_META` dict for known categories.
3. Overlay the `transaction_registry` for `has_mapping`.
4. For types not in `_X12_META`, use `category='Other'` and `description` from the `.ediSchema` `name` field.

### 5.2 — Update `x12_schema()` endpoint

When `version` is provided, first try to find a matching mapping YAML (existing behavior). If no version-specific mapping exists, fall back to parsing the `.ediSchema` file from the standards directory and converting to `X12SchemaResponse`.

Add a conversion function:
```python
def _schema_from_standard(msg: MessageSchema, code: str) -> X12SchemaResponse:
    """Convert a MessageSchema from standards parser to X12SchemaResponse."""
```

This mirrors what the frontend does in Phase 4.6 but on the backend, so the legacy endpoint also returns standards data.

### Verify Phase 5
- `GET /api/onboard/x12-types` → returns 318 entries (5010), each with category and description.
- `GET /api/onboard/x12-schema?type=810&version=4010` → returns schema from 4010 standard.
- `GET /api/onboard/x12-schema?type=810` (no version) → returns existing mapping YAML schema (backward compatible).
- `GET /api/onboard/x12-schema?type=270&version=5010` → returns schema parsed from standards (no mapping YAML exists for 270).

---

## Phase 6 — Testing

**Goal:** Verify all changes work end-to-end. Run existing tests to confirm nothing is broken, then add new tests for the standards-driven features.

### 6.1 — Run existing backend tests

```bash
cd C:\Users\SeanHoppe\VS\pycoreEdi
pytest tests/ -v
```

All existing tests must pass. Fix any failures before proceeding.

### 6.2 — Run existing E2E tests (Python/Playwright)

```bash
cd C:\Users\SeanHoppe\VS\pycoreEdi
pytest portal/tests/e2e/ -v
```

Pay special attention to `test_onboard.py` — the onboard wizard tests must still pass.

### 6.3 — Run existing frontend Playwright tests

```bash
cd C:\Users\SeanHoppe\VS\pycoreEdi\portal\ui
npx playwright test x12-wizard.spec.ts
```

All X12 wizard tests must still pass. These tests verify:
- Format selector displays
- Transaction type dropdown loads
- Schema review displays
- Mode toggle (Existing/Upload)
- Navigation through all 3 steps
- Match key auto-population
- Full registration + rules save workflow
- Duplicate profile name error handling
- Rules auto-seeding from X12 schema

### 6.4 — Add backend unit tests for standards parser

Create: `tests/test_standards_parser.py`

```python
"""Tests for the .ediSchema standards parser."""
import pytest
from pathlib import Path
from pyedi_core.standards_parser import (
    parse_edi_schema,
    scan_standards_dir,
    get_message_segments,
    MessageSchema,
)

_STANDARDS_DIR = Path(__file__).resolve().parent.parent / "standards"
_SKIP_NO_STANDARDS = pytest.mark.skipif(
    not (_STANDARDS_DIR / "x12").exists(),
    reason="standards directory not present"
)


@_SKIP_NO_STANDARDS
class TestParseEdiSchema:
    """Tests for parse_edi_schema()."""

    def test_810_v004010_metadata(self) -> None:
        """Parse 810 Invoice from 4010 and verify metadata."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "810"
        assert result.name == "Invoice"
        assert result.version == "004010"
        assert result.functional_group == "IN"
        assert result.standard_type == "x12"

    def test_850_v004010_metadata(self) -> None:
        """Parse 850 Purchase Order from 4010."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message850.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "850"
        assert result.name == "Purchase Order"
        assert result.version == "004010"

    def test_997_v004010_small_file(self) -> None:
        """Parse 997 Functional Ack — a small file as smoke test."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message997.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "997"
        assert result.name == "Functional Acknowledgment"

    def test_810_has_areas(self) -> None:
        """Verify the 810 schema contains multiple areas with segments."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert len(result.areas) >= 2  # header, detail, at minimum
        # Area 1 should contain ST and BIG segments
        area1_names = [ref.name for ref in result.areas[0]]
        assert "ST" in area1_names
        assert "BIG" in area1_names

    def test_810_has_segment_defs(self) -> None:
        """Verify segment definitions are parsed."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert "BIG" in result.segment_defs
        big = result.segment_defs["BIG"]
        assert big.name == "Beginning Segment for Invoice"
        assert len(big.elements) > 0

    def test_810_segment_group_children(self) -> None:
        """Verify segment groups contain child segment refs."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        # Find the N1 segment group in area 1
        n1_group = None
        for ref in result.areas[0]:
            if ref.name == "N1" and ref.ref_type == "segmentGroup":
                n1_group = ref
                break
        assert n1_group is not None, "N1 segment group not found in area 1"
        child_names = [c.name for c in n1_group.children]
        assert "N1" in child_names
        assert "N2" in child_names

    def test_810_v005010_different_version(self) -> None:
        """Parse the same transaction from a different version."""
        path = _STANDARDS_DIR / "x12" / "v005010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        assert result.code == "810"
        assert result.version == "005010"

    def test_cardinality_parsing(self) -> None:
        """Verify min/max cardinality is parsed correctly."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        result = parse_edi_schema(path)
        # ST should be [1..1]
        st = next(r for r in result.areas[0] if r.name == "ST")
        assert st.min_occurs == 1
        assert st.max_occurs == 1
        # NTE should be [0..100]
        nte = next(r for r in result.areas[0] if r.name == "NTE")
        assert nte.min_occurs == 0
        assert nte.max_occurs == 100


@_SKIP_NO_STANDARDS
class TestScanStandardsDir:
    """Tests for scan_standards_dir()."""

    def test_returns_x12(self) -> None:
        """Catalog should contain x12 standard."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert "x12" in result

    def test_x12_has_five_versions(self) -> None:
        """X12 should have 5 versions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert len(result["x12"]) == 5

    def test_v004010_has_294_transactions(self) -> None:
        """v004010 should have 294 transactions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert len(result["x12"]["4010"]) == 294

    def test_v005010_has_318_transactions(self) -> None:
        """v005010 should have 318 transactions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        assert len(result["x12"]["5010"]) == 318

    def test_transaction_entry_has_required_fields(self) -> None:
        """Each transaction entry should have code, name, file."""
        result = scan_standards_dir(_STANDARDS_DIR)
        entry = result["x12"]["4010"][0]
        assert "code" in entry
        assert "name" in entry
        assert "file" in entry

    def test_810_exists_in_all_versions(self) -> None:
        """810 should be available in all 5 X12 versions."""
        result = scan_standards_dir(_STANDARDS_DIR)
        for version, txns in result["x12"].items():
            codes = [t["code"] for t in txns]
            assert "810" in codes, f"810 not found in version {version}"


@_SKIP_NO_STANDARDS
class TestGetMessageSegments:
    """Tests for get_message_segments()."""

    def test_810_segments(self) -> None:
        """810 should include common invoice segments."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message810.ediSchema"
        segments = get_message_segments(path)
        assert "ST" in segments
        assert "BIG" in segments
        assert "SE" in segments  # trailer

    def test_850_segments(self) -> None:
        """850 should include BEG segment."""
        path = _STANDARDS_DIR / "x12" / "v004010" / "schemas" / "Message850.ediSchema"
        segments = get_message_segments(path)
        assert "BEG" in segments
```

### 6.5 — Add backend API tests for standards endpoints

Create: `tests/test_standards_api.py`

```python
"""Tests for the standards-driven onboard API endpoints."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

_STANDARDS_DIR = Path(__file__).resolve().parent.parent / "standards"
_SKIP_NO_STANDARDS = pytest.mark.skipif(
    not (_STANDARDS_DIR / "x12").exists(),
    reason="standards directory not present"
)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the portal API."""
    from portal.api.server import create_app
    app = create_app()
    return TestClient(app)


@_SKIP_NO_STANDARDS
class TestStandardsCatalog:
    """Tests for GET /api/onboard/standards."""

    def test_returns_x12(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards")
        assert resp.status_code == 200
        data = resp.json()
        standards = [s["standard"] for s in data["standards"]]
        assert "x12" in standards

    def test_x12_has_versions(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards")
        data = resp.json()
        x12 = next(s for s in data["standards"] if s["standard"] == "x12")
        assert len(x12["versions"]) == 5


@_SKIP_NO_STANDARDS
class TestStandardsTransactions:
    """Tests for GET /api/onboard/standards/{standard}/{version}/transactions."""

    def test_x12_4010_returns_transactions(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["standard"] == "x12"
        assert data["version"] == "4010"
        assert len(data["transactions"]) == 294

    def test_810_has_mapping_flag(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/transactions")
        data = resp.json()
        t810 = next(t for t in data["transactions"] if t["code"] == "810")
        # 810 should have a custom mapping in transaction_registry
        assert t810["has_mapping"] is True

    def test_invalid_version_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/9999/transactions")
        assert resp.status_code == 404

    def test_invalid_standard_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/hl7/4010/transactions")
        assert resp.status_code == 404


@_SKIP_NO_STANDARDS
class TestStandardsSchema:
    """Tests for GET /api/onboard/standards/{standard}/{version}/{code}/schema."""

    def test_810_schema(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/810/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "810"
        assert data["name"] == "Invoice"
        assert data["version"] == "004010"
        assert len(data["areas"]) >= 2
        assert "BIG" in data["segment_defs"]

    def test_997_schema(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/997/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "997"

    def test_nonexistent_code_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/standards/x12/4010/999/schema")
        assert resp.status_code == 404


@_SKIP_NO_STANDARDS
class TestLegacyEndpointsStillWork:
    """Ensure existing endpoints remain backward compatible."""

    def test_x12_types_returns_data(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/x12-types")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["types"]) > 0
        # Should still have the original fields
        entry = data["types"][0]
        assert "code" in entry
        assert "label" in entry
        assert "has_mapping" in entry

    def test_x12_schema_810(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/x12-schema?type=810")
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_type"] is not None

    def test_x12_versions_810(self, client: TestClient) -> None:
        resp = client.get("/api/onboard/x12-types/810/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "5010" in data["versions"] or "004010" in data["versions"]
```

### 6.6 — Update existing Playwright tests if needed

Read `portal/ui/tests/x12-wizard.spec.ts` before modifying. The tests may need adjustments for:
- The version dropdown (new UI element the tests didn't expect).
- The transaction type dropdown now loads from standards instead of `x12-types`.
- Loading times may change (standards scan is larger dataset).

**Adjustments to consider:**
1. If tests select a transaction type by clicking a dropdown option, verify the option text still matches (e.g., "810 — Invoice" vs "810").
2. If tests check for specific element counts in the schema review table, these may differ between mapping YAML data and standards data.
3. Add wait-for-element calls if the version dropdown adds an async step.

Only modify tests where they fail — do not preemptively change test assertions.

### 6.7 — Manual smoke test checklist

Run the portal and manually verify:

```
Portal Startup:
  [ ] cd portal && python -m api.server starts without errors
  [ ] Frontend loads at http://localhost:15174

Standards Discovery:
  [ ] GET /api/onboard/standards returns x12 with 5 versions
  [ ] GET /api/onboard/standards/x12/5010/transactions returns 318 items
  [ ] GET /api/onboard/standards/x12/4010/810/schema returns full schema

Onboard Wizard — X12 Path:
  [ ] Click "X12 / EDIFACT" format button
  [ ] Version dropdown appears with 5 options, 5010 selected by default
  [ ] Transaction type combobox shows ~318 types for 5010
  [ ] Search "invoice" filters to 810
  [ ] Select 810 → schema loads with segments and fields
  [ ] Change version to 4010 → transaction list refreshes
  [ ] Select 810 from 4010 → schema loads (4010 version)
  [ ] Select type without custom mapping (e.g., 270) → standard segments shown with info banner
  [ ] Click "Upload New Mapping" → upload mode works as before
  [ ] Proceed to Register Partner → form works as before
  [ ] Fill in profile details and register → success
  [ ] Proceed to Configure Rules → rules auto-seed from schema
  [ ] Save rules → wizard completes

Onboard Wizard — Other Path (flat-file):
  [ ] Click "Flat-File / XML" format button
  [ ] Compile DSL → works as before (no changes to this path)
  [ ] Register and configure rules → works as before

Existing Features Not Broken:
  [ ] Compare page → profiles load, comparison works
  [ ] Partners page → all profiles listed, delete works
  [ ] Rules page → rules load and save
  [ ] Dashboard → renders correctly
  [ ] Pipeline → runs correctly
  [ ] Validate → validates files correctly
```

### 6.8 — Cleanup test profile

After manual testing, delete any test profiles created during the smoke test:
```bash
curl -X DELETE http://localhost:18041/api/onboard/profile/test_profile_name
```

---

## File Change Summary

| File | Phase | Change |
|------|-------|--------|
| `standards/x12/v*/schemas/*.ediSchema` | 0 | **NEW** — copied from certPortal (~1,333 files) |
| `.gitignore` | 0 | Add `standards/` |
| `config/config.yaml` | 0 | Add `standards_dir` key |
| `pyedi_core/standards_parser.py` | 1 | **NEW** — .ediSchema DSL parser (~200-250 lines) |
| `portal/api/routes/onboard.py` | 2, 5 | New endpoints + update existing endpoints |
| `portal/ui/src/api.ts` | 3 | New types + API methods |
| `portal/ui/src/pages/Onboard.tsx` | 4 | Version dropdown, dynamic transaction list, standards schema |
| `tests/test_standards_parser.py` | 6 | **NEW** — parser unit tests |
| `tests/test_standards_api.py` | 6 | **NEW** — API integration tests |

## Deferred Work

- **EDIFACT support**: Add EDIFACT as a third format mode in the wizard. Copy EDIFACT standards directories. Extend the parser for EDIFACT DSL differences (alphanumeric codes, different numbering). Add `edifact` option to format selector.
