# Update Flat-File Process — Task List

## Context

When importing a `.ffSchema` DSL file (e.g., `RetalixPIInvoiceFileSchemaSacFF.ffSchema`), the schema compiler correctly parses **record blocks** with `fieldIdentifier` values (e.g., `OIN_SACD1`, `OIN_DTL9`, `OIN_SACS1`) and associates fields to their parent record. However, the Onboard wizard UI and rules configuration lose this record-level context — presenting a flat list of fields with no indication of which record they belong to.

**Key constraint:** Field names (e.g., `recordID`, `amount`) repeat across multiple records, so record context is essential for disambiguation.

---

## Task 1: Onboard Wizard — Show Record Identifiers in Schema Import (Step 1)

**Problem:** Step 1 (Import & Compile) displays a flat columns table with name, DSL type, compiled type, width, and type_preserved — but no record identification.

**Current data flow:**
- `schema_compiler.py:_parse_dsl_record()` extracts `fieldIdentifier` value and record name
- `validator.py:_build_column_info()` sets `record_name` on each `ColumnInfo`
- `validate.py` API returns `ColumnInfoModel` which includes `record_name`
- **Gap:** `Onboard.tsx` Step 1 does not use `record_name` from the response

**Changes needed:**

### Backend (already sufficient)
- `ColumnInfoModel` already has `record_name: str` — no API changes needed
- Verify the `/api/validate` response includes populated `record_name` values

### Frontend — `portal/ui/src/pages/Onboard.tsx` (StepCompile)
1. **Group columns by record** — instead of a flat table, render columns grouped under record headers showing `record_name` and `fieldIdentifier` value
2. **Add search/filter** — text input that matches against column `name` headers; results show the matching field(s) with their parent record context (critical for repeated field names)
3. **Visual record separators** — use collapsible sections or colored record headers so users can distinguish OIN_SACD1 fields from OIN_DTL9 fields
4. **Record summary** — show count of records detected and total fields per record

---

## Task 2: Configure Rules — Record-Level Granularity (Step 3)

**Problem:** Step 3 (Configure Rules) shows a flat rules list with no record identification. The rules template API (`/api/onboard/rules-template`) extracts columns from the compiled YAML but does not include record context. Rules use `segment: "*"` which applies to all records indiscriminately.

**Current data flow:**
- `onboard.py:rules_template()` reads compiled YAML columns, builds rules with field/severity/numeric
- **Gap:** Does not read record metadata from the compiled YAML or original DSL
- `Onboard.tsx` Step 3 renders rules as a flat table

**Changes needed:**

### Backend — `portal/api/routes/onboard.py`
1. **Enrich rules template response** — include `record_name` for each field in the rules template
2. **Source record data** — either:
   - (a) Read from compiled YAML `schema.records` dict (keys are fieldIdentifier values), or
   - (b) Re-parse the DSL to get record_defs (less ideal, adds latency)
3. **Update `RulesTemplateResponse` model** — add `record_name` field to classification rule items

### Frontend — `portal/ui/src/pages/Onboard.tsx` (StepRules)
1. **Group rules by record** — render rules under collapsible record headers
2. **Add search/filter** — text input to find fields across records; show record context in results
3. **Per-record severity defaults** — allow setting severity at the record level (applies to all fields in that record), with per-field overrides
4. **Catch-all rule scoping** — clarify that `* / *` catch-all applies across all records

### Compiled YAML — `pyedi_core/core/schema_compiler.py`
1. **Preserve record→field mapping** — ensure the compiled YAML `schema.records` dict is accessible for the rules template API
2. **Consider adding a `record_inventory` section** to the compiled YAML:
   ```yaml
   record_inventory:
     OinSacd1:
       fieldIdentifier: "OIN_SACD1 "
       field_count: 42
     OinDtl9:
       fieldIdentifier: "OIN_DTL9  "
       field_count: 18
   ```

---

## Task 3: Darken Sidebar Color

**Problem:** The sidebar background (`bg-gray-50/80` in `App.tsx` line ~58) is too light and doesn't provide enough visual separation from the main content area.

**File:** `portal/ui/src/App.tsx`

**Current classes:**
```
nav: bg-gray-50/80 border-r border-gray-200 text-gray-600
inactive item hover: hover:bg-gray-100 hover:text-gray-900
active item: bg-blue-50 text-blue-700 border-l-[3px] border-blue-500
API status text: text-gray-400
```

**Changes needed:**
1. **Darken nav background** — change `bg-gray-50/80` to `bg-gray-200` or `bg-gray-300` (evaluate which provides best contrast)
2. **Adjust text colors** — ensure nav item text has sufficient contrast against darker background
3. **Update hover states** — adjust `hover:bg-gray-100` to work with darker base (e.g., `hover:bg-gray-300`)
4. **Active item contrast** — verify active item (`bg-blue-50`) still reads well against darker sidebar
5. **Border adjustment** — may need to darken `border-gray-200` to match

---

## Implementation Order

1. **Task 3** (sidebar color) — smallest scope, quick visual fix
2. **Task 1** (record display in Step 1) — backend data already available, mostly frontend work
3. **Task 2** (record-aware rules) — requires backend + frontend changes, builds on Task 1 patterns
