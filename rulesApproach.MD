# Rules-Based Approach — PyEDI-Core Architecture

## Executive Summary

PyEDI-Core is a **generic EDI/CSV/XML processing and comparison engine** whose every behavior — parsing, transformation, severity classification, field matching, and discovery — is governed by **YAML configuration rules** rather than hardcoded logic. This document describes how that rules-based approach works, its strengths, its trade-offs, and the opportunities it creates.

---

## How the Rules-Based Approach Works

### The Three-Tier Rule Hierarchy

Rules are defined in YAML files organized into three tiers. Each tier can override the one above it, creating a specificity cascade similar to CSS:

```
Tier 1 — Universal (_universal.yaml)
  │  Applies to ALL profiles, ALL transaction types.
  │  Defines baseline: envelope-field ignores, default severity.
  │
  ├── Tier 2 — Transaction Type (_global_810.yaml, _global_850.yaml, …)
  │     Applies to all profiles that share a transaction type (810, 850, 856, etc.).
  │     Overrides universal rules for that transaction family.
  │
  └──── Tier 3 — Partner / Profile (bevager_810.yaml, 810_invoice.yaml, …)
          Applies to a single trading-partner or comparison profile.
          Overrides transaction AND universal rules.
```

When the engine runs a comparison, it calls `load_tiered_rules()`, which reads all three tiers in order, then `merge_rules()` flattens them into one resolved rule set. The most specific tier always wins.

### What a Rule Looks Like

Each rule targets a **(segment, field)** pair and assigns properties that control how that field is compared:

```yaml
classification:
  - segment: N1
    field: N102
    severity: hard          # hard = fail | soft = warn | ignore = skip
    ignore_case: true       # normalize to lowercase before comparing
    numeric: false          # compare as string, not float
    conditional_qualifier: null
    amount_variance: null

  - segment: "*"
    field: InvoiceTotal
    severity: hard
    numeric: true
    amount_variance: 0.01   # allow ±$0.01 rounding variance

ignore:
  - segment: ISA
    field: "*"
    reason: "Envelope-level, not business data"
```

Wildcards (`*`) act as catch-alls. Resolution priority is:
`(exact segment, exact field)` > `(exact segment, *)` > `(*, exact field)` > `(*, *)`

### Rule Types Across the System

| Rule Category | Where Defined | What It Controls |
|---|---|---|
| **Classification** | `config/compare_rules/*.yaml` | Severity (hard/soft/ignore), comparison mode (numeric, case-insensitive, conditional, variance) |
| **Ignore** | `config/compare_rules/*.yaml` | Fields/segments to skip entirely during comparison |
| **Transformation** | `schemas/compiled/*_map.yaml` | How raw values are converted before mapping (`to_float`, `upper`, `strip`, `to_date`, `substring`, `replace`, `default`) |
| **Schema / Validation** | `schemas/compiled/*_map.yaml` | Column types, required fields, max lengths, read_empty_as_null |
| **Profile / Match Key** | `config/config.yaml` | How source/target documents are paired (match key segment+field or JSON path), segment qualifier fields for sub-matching |

### The Full Pipeline

```
Raw File (X12 / CSV / XML)
      │
      ▼
┌──────────────┐
│ Format Detect │  Extension-based, data-driven
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ Schema + Mapper       │  Compiled YAML defines columns, types,
│ (YAML-driven)         │  transforms, defaults — zero hardcoded
│                       │  field logic in Python
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Intermediate JSON     │  Normalized envelope:
│ { header, lines,      │  { header: {…}, lines: [{…}], summary: {…} }
│   summary }           │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Compare Engine        │  load_tiered_rules() → merge_rules()
│ (rules-driven)        │  compare_pair() applies severity, numeric,
│                       │  ignore_case, conditional, variance
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Result + Discovery    │  Diffs stored with severity + provenance
│ (SQLite)              │  Wildcard-fallback diffs auto-flagged
└──────────────────────┘
```

No Python code contains `if field == 'InvoiceTotal'` or `if transaction_type == '810'`. All such logic lives in YAML.

---

## Strengths

### 1. Zero-Code Onboarding of New Partners and Formats

Adding a new trading partner, transaction type, or file format requires **only YAML files** — no Python changes, no redeployment:

- Create a schema DSL file → compile to YAML
- Create a compare rules YAML file
- Add a profile entry in `config.yaml`

This dramatically reduces the cost and risk of onboarding. A business analyst with YAML knowledge can onboard a partner without touching application code.

### 2. Tiered Inheritance Eliminates Duplication

The universal → transaction → partner cascade means common rules are written once. A new 810 partner inherits all universal ignores (envelope fields) and all 810-level classification rules automatically. Only partner-specific overrides need to be authored. This prevents rule sprawl and keeps configurations DRY.

### 3. Hot-Updateable via API

The Portal API exposes full CRUD for all three tiers (`/api/rules/tiers`, `/api/rules/universal`, `/api/rules/transaction/{type}`, `/api/rules/partner/{profile}`). Rules changes take effect on the next comparison run — no process restart, no redeploy. The `/api/rules/effective/{profile}` endpoint shows the merged result with **tier provenance**, so operators know exactly which tier is controlling each field.

### 4. Reclassification Without Re-Processing

The `/api/compare/runs/{id}/reclassify` endpoint re-evaluates all diffs from a prior run against the **current** rule set. This enables:
- A/B testing rule changes against historical data
- Retroactive severity adjustments without re-ingesting files
- Incremental tuning: adjust a rule, reclassify, review, repeat

### 5. Self-Improving Discovery Loop

Fields that hit the wildcard `(*, *)` fallback are automatically flagged as **discoveries** — new field combinations the system hasn't been explicitly told how to handle. The Portal UI surfaces these for human classification. Once classified, the field gets a real rule, and future runs handle it explicitly. The system **learns** its rule set over time through use.

### 6. Auditable and Explainable

Every diff carries:
- The **severity** assigned and **which tier** assigned it
- Whether it was a **wildcard fallback** (discovery) or explicitly classified
- The **source and target values** compared
- The **rule properties** applied (numeric, ignore_case, variance)

This makes compliance auditing straightforward — you can explain exactly why any field was flagged or ignored, and point to the YAML line that controls it.

### 7. Format-Agnostic Core

The same comparison engine and rule structure work across X12 EDI, CSV, fixed-width, and XML. Segment-based rules handle EDI naturally; `segment: "*"` with field names handles flat formats. One engine, one rule syntax, multiple formats.

---

## Trade-Offs and Risks

### 1. YAML Complexity at Scale

As the number of trading partners and transaction types grows, the `config/compare_rules/` directory can accumulate dozens of files with subtle override interactions. A rule in `_universal.yaml` may be overridden by `_global_810.yaml`, which is then re-overridden by `bevager_810.yaml`. Debugging "why is this field soft instead of hard?" requires tracing through three files. The `/api/rules/effective/{profile}` endpoint mitigates this, but the underlying complexity remains.

### 2. No Compile-Time Safety Net

YAML has no type system. A typo in a segment name (`N01` instead of `N1`), a misspelled property (`numric` instead of `numeric`), or an invalid severity value (`medium` instead of `soft`) will not be caught until runtime — and may silently fall through to wildcard defaults rather than raising an error. Validation exists at the API layer, but direct file edits bypass it.

### 3. Discovery Requires Human-in-the-Loop

The wildcard-fallback discovery mechanism is powerful but depends on a human reviewing and classifying new fields. If discoveries accumulate without review, comparison results degrade to mostly-wildcard matches with low confidence. The system needs operational discipline around discovery triage.

### 4. Rule Conflicts Can Be Silent

When two rules at the same tier target the same (segment, field) pair, the last-loaded one wins. There is no conflict detection or warning. Similarly, an ignore rule and a classification rule for the same field can interact in non-obvious ways (ignore takes precedence). As the rule set grows, unintended interactions become harder to spot.

### 5. Testing Rules Requires Test Data

Unlike code (which can be unit-tested with mocks), rules are only meaningful when applied to real document pairs. Testing a rule change means running a comparison against representative data. There is no "rule unit test" — the reclassification endpoint is the closest equivalent, but it still requires a prior run with actual documents.

---

## Opportunities

### 1. Rule Validation and Linting

A YAML linter specific to the rule schema could catch typos, invalid values, unreachable rules (overridden at a higher-specificity tier), and conflicts before they reach production. This could run as a pre-commit hook or as a Portal API validation step.

### 2. Discovery-to-Rule Automation

Today, discoveries require manual classification. The system could suggest severities based on:
- Field name patterns (fields containing "amount", "total", "price" → `numeric: true, severity: hard`)
- Historical classification decisions (if `N102` was classified as `hard` in 5 other profiles, suggest `hard`)
- Value analysis (if both values are always numeric, suggest `numeric: true`)

This would reduce the human-in-the-loop burden without eliminating human oversight.

### 3. Rule Versioning and Rollback

Rules are currently files on disk. Adding version control (timestamps, changelogs, or Git-tracked rule directories) would enable:
- Rollback to a previous rule set
- Diff between rule versions
- Audit trail of who changed what and when

### 4. Cross-Profile Rule Analytics

With multiple profiles running comparisons, the system could surface insights like:
- "Field X is classified as `hard` in 12 profiles but `soft` in 1 — is that intentional?"
- "Profile Y has 47 discoveries pending — it needs attention"
- "Universal rule Z is overridden in every single profile — should it be changed at the universal level?"

### 5. Conditional Rule Chains

Currently, rules are evaluated independently per field. Supporting conditional chains ("if field A mismatches, then also flag field B as hard") would handle scenarios where business fields are interdependent — e.g., if the invoice total is wrong, the line-item amounts become hard failures too.

### 6. Rule Templates for Common Patterns

Recurring rule patterns (e.g., "all amount fields: numeric + hard + variance 0.01") could be defined as named templates and referenced in partner rules, reducing boilerplate:

```yaml
classification:
  - segment: "*"
    field: InvoiceTotal
    template: amount_hard    # expands to numeric: true, severity: hard, amount_variance: 0.01
```

### 7. Export and Sharing

Rules could be exported as portable packages (ZIP of YAML + schema) for sharing between PyEDI-Core installations or for onboarding partners who run their own instance. A partner could receive a "rule pack" that configures their comparison profile in one step.

---

## Summary Matrix

| Dimension | Assessment |
|---|---|
| **Flexibility** | Excellent — new partners, formats, and rules without code changes |
| **Maintainability** | Good at small scale; requires tooling (linting, analytics) at large scale |
| **Auditability** | Excellent — every decision traceable to a YAML rule + tier provenance |
| **Onboarding Speed** | Fast — YAML-only, no developer required for standard cases |
| **Error Detection** | Moderate — runtime-only; no compile-time safety for YAML |
| **Self-Improvement** | Strong — discovery loop surfaces unknowns automatically |
| **Scalability** | Good with discipline — tiered inheritance prevents duplication, but conflict detection needed at scale |

---

## Conclusion

The rules-based approach is the architectural backbone of PyEDI-Core. It turns a potentially rigid EDI comparison tool into a **configurable platform** — one where business logic lives in data (YAML) rather than code (Python), where changes are instant rather than requiring development cycles, and where the system actively surfaces what it doesn't yet know (discoveries) rather than silently falling back to defaults. The trade-offs are real — YAML complexity, lack of compile-time safety, and reliance on human discovery triage — but each has a clear mitigation path. The approach is well-suited to the domain: EDI processing is inherently partner-specific and rule-heavy, making configuration-over-code not just a preference but a practical necessity.
