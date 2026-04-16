# Orchestration Prompt — Multi-Dimensional Match Keys (Onboard + Comparator)

## Context

Today a Compare profile has exactly one match key — either `{segment, field}`
(X12) or `{json_path}` (flat JSON). The dataclass `MatchKeyConfig`
(`pyedi_core/comparator/models.py:9`) holds one of each. The matcher
(`pyedi_core/comparator/matcher.py` `extract_match_values`, `build_match_index`)
produces an index keyed on a single normalized string value. The Onboard
wizard's Register Partner step (`portal/ui/src/pages/Onboard.tsx` ~line 1036)
exposes one segment/field pair or one json field.

Several real trading partners cannot be paired on a single field. Example: an
810 where the PO Number is reused across weekly invoices; disambiguation
requires PO + Line-Item ID together. The chosen design is
**multi-dimensional match keys with AND semantics** — every configured key
must match between source and target transactions for them to pair.

Implementation insight: AND semantics over N keys is equivalent to tuple
equality, which hashes to a single composite index key. No quadratic blowup.
The difference from a "concat in one field" workaround is user ergonomics:
each key row has its own segment/field (or json_path) and its own optional
normalize regex.

## Goals

1. `MatchKeyConfig` carries an ordered list of key parts.
2. Config YAML supports both legacy singleton (`match_key: {segment, field}`)
   and new list form (`match_key: [{segment, field}, {segment, field}]`).
   Legacy loads transparently.
3. Matcher builds index using tuple of all key values; a transaction is
   dropped from the index if *any* key part cannot be extracted (strict AND).
4. Onboard Register Partner UI lets user add/remove key rows. Default stays
   one row seeded from `match_key_default`.
5. Portal API round-trips a list.
6. E2E Playwright test (`--headed`) registering a 2-key 855 profile and
   verifying `config.yaml` persists the list.

## Constraints

- Follow `CLAUDE.md` strictly (minimal diff, match existing patterns, type
  hints, no refactoring beyond scope).
- Data-driven — no hardcoded segment/field allowlist.
- Back-compat mandatory: existing profiles in `config/config.yaml` MUST keep
  pairing correctly without migration. Existing `tests/test_comparator.py`
  must stay green.
- Writer emits list form only if N > 1. If user leaves one row, write
  singleton dict to minimize diff against existing YAML.
- Flat-file JSON path mode supported identically (each row is either a
  segment/field pair *or* a json_path — not mixed within one profile for
  this iteration; enforce single-mode in UI).
- No schema changes to `compare_runs` SQLite table (`store.py:22`
  `match_key TEXT` — stringify list for display).

## Plan — 9 Steps

### Step 1 — Data model

File: `pyedi_core/comparator/models.py`.

Add:

```python
@dataclass
class MatchKeyPart:
    segment: str | None = None
    field: str | None = None
    json_path: str | None = None
    normalize: str | None = None
```

Extend `MatchKeyConfig`:

```python
@dataclass
class MatchKeyConfig:
    segment: str | None = None        # LEGACY — mirror of parts[0].segment
    field: str | None = None          # LEGACY — mirror of parts[0].field
    json_path: str | None = None      # LEGACY — mirror of parts[0].json_path
    normalize: str | None = None      # LEGACY — mirror of parts[0].normalize
    parts: list[MatchKeyPart] = field(default_factory=list)

    def __post_init__(self) -> None:
        # If parts is empty but legacy fields present, lift them into parts[0].
        if not self.parts and (self.segment or self.field or self.json_path):
            self.parts = [MatchKeyPart(
                segment=self.segment,
                field=self.field,
                json_path=self.json_path,
                normalize=self.normalize,
            )]
        # If parts present but legacy empty, mirror parts[0] for read-compat.
        elif self.parts and not (self.segment or self.field or self.json_path):
            p = self.parts[0]
            self.segment = p.segment
            self.field = p.field
            self.json_path = p.json_path
            self.normalize = p.normalize
```

Legacy consumers that read `mk.segment`/`mk.field` keep working; they see the
first part. Any code that needs all parts reads `mk.parts`.

### Step 2 — Loader

File: `pyedi_core/comparator/__init__.py`, function `_parse_profile`
(line ~352).

Accept both forms:

```python
def _parse_profile(name: str, data: dict) -> CompareProfile:
    mk_raw = data.get("match_key", {})
    if isinstance(mk_raw, list):
        parts = [MatchKeyPart(
            segment=p.get("segment"),
            field=p.get("field"),
            json_path=p.get("json_path"),
            normalize=p.get("normalize"),
        ) for p in mk_raw]
        match_key = MatchKeyConfig(parts=parts)
    else:
        match_key = MatchKeyConfig(
            segment=mk_raw.get("segment"),
            field=mk_raw.get("field"),
            json_path=mk_raw.get("json_path"),
            normalize=mk_raw.get("normalize"),
        )
    return CompareProfile(
        name=name,
        description=data.get("description", ""),
        match_key=match_key,
        ...
    )
```

Import `MatchKeyPart` at module top.

### Step 3 — Matcher: tuple-index extraction

File: `pyedi_core/comparator/matcher.py`.

Refactor `extract_match_values(json_data, match_key)`:

1. Build a helper `_extract_part_value(tx_segments_or_data, part) -> str | None`
   that returns the normalized value for a single part (X12 segment/field OR
   json_path). Return `None` when the field is missing/empty.
2. Determine mode per-profile: if **all** parts have `json_path` → flat mode;
   if **all** parts have `segment` and `field` → X12 mode. Mixed mode → raise
   `ValueError` at load time (guard in Step 2 after parsing).
3. Flat mode: resolve each part against root dict, collect tuple of values.
   Skip if any None. Join with `\x1f` (unit separator) as composite index
   key. Preserve split-key remainder skip.
4. X12 mode: for each transaction (split by ST/SE), resolve each part's
   value by scanning `tx_segments` for the matching segment and extracting
   the field. Collect tuple; skip transaction if any None. Composite key =
   `"\x1f".join(tuple)`.
5. Output `MatchEntry.match_value = composite_key`. No other field changes.

`build_match_index` and `pair_transactions` need **no** signature changes —
they already key on `entry.match_value`.

Guard: if `match_key.parts` is empty, raise `ValueError("match_key has no
parts configured")`.

### Step 4 — Portal API: accept list

File: `portal/api/routes/onboard.py`.

Change `RegisterPartnerRequest.match_key` (line 47):

```python
match_key: Dict[str, str] | List[Dict[str, str]]
```

Writer around line 371:

```python
if isinstance(req.match_key, list):
    profile_dict["match_key"] = [dict(p) for p in req.match_key]
else:
    profile_dict["match_key"] = dict(req.match_key)
```

If a list arrives with length 1, collapse to singleton dict before writing
so existing profiles stay diff-minimal. Validate that every entry either has
`segment`+`field` OR `json_path` (not both, not mixed across list). 400 on
invalid.

### Step 5 — UI: repeatable key rows

File: `portal/ui/src/pages/Onboard.tsx`, `StepRegister` around line 1036.

Replace the single-pair state with a list:

```ts
interface KeyRow { segment: string; field: string; json_path: string; normalize: string }
const [matchKeys, setMatchKeys] = useState<KeyRow[]>([
  isX12
    ? { segment: wizard.x12Schema?.match_key_default?.segment || '',
        field: wizard.x12Schema?.match_key_default?.field || '',
        json_path: '', normalize: '' }
    : { segment: '', field: '', json_path: `header.${wizard.columns[0]?.name || ''}`, normalize: '' }
])
```

UI affordances in the Match Key block (current lines 1120-1148):

- Render each row as its existing segment/field (X12) or json_path (flat)
  inputs.
- Append a compact `+ Add key` button (indigo outline, `text-xs`) below the
  last row.
- Each row past the first shows a `Remove` button.
- Preserve the existing JSON Path vs X12 toggle at the **mode** level (one
  toggle for the whole profile, not per row); changing mode wipes the list
  and seeds a fresh first row in the new mode.

Payload assembly in `register()`:

```ts
const match_key = matchKeys.length === 1
  ? (matchKeyType === 'json'
      ? { json_path: matchKeys[0].json_path }
      : { segment: matchKeys[0].segment, field: matchKeys[0].field })
  : matchKeys.map(k => matchKeyType === 'json'
      ? { json_path: k.json_path }
      : { segment: k.segment, field: k.field })
```

Validation: disable `Register` if any row is incomplete (X12 mode requires
segment AND field; JSON mode requires json_path).

### Step 6 — TypeScript API surface

File: `portal/ui/src/api.ts`.

Update `onboardRegister` request type so `match_key` accepts
`Record<string,string> | Array<Record<string,string>>`. No endpoint changes.

### Step 7 — Tests: comparator unit

File: `tests/test_comparator.py`.

Add two tests:

1. `test_multi_key_tuple_pairs_all_match` — construct two fake
   `json_data` docs with segments `BIG02=PO1, IT107=LINE1` in both; profile
   with two parts `BIG/BIG02` and `IT1/IT107`; assert `extract_match_values`
   returns exactly one entry per transaction with `match_value` equal to
   `"PO1\x1fLINE1"`.

2. `test_multi_key_missing_part_drops_transaction` — same fixture but the
   target doc omits IT107; assert the transaction is dropped from the index
   (no MatchEntry emitted).

Run:
```
pytest tests/test_comparator.py -k multi_key -v
```

### Step 8 — Typecheck

From `portal/ui/`:
```
npm run build
```
Zero TS errors.

### Step 9 — Playwright E2E (`--headed`)

Create `portal/ui/tests/onboard-multidim-match-key.spec.ts`:

```ts
import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync, readFileSync } from 'fs';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const TEST_PROFILE = '_pw_multidim_test';
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

function cleanupProfile(profileName: string): void {
  const scriptPath = join(PROJECT_ROOT, '_pw_cleanup_multidim.py');
  const script = [
    'import yaml',
    'from pathlib import Path',
    `cfg = Path(r"${join(PROJECT_ROOT, 'config', 'config.yaml')}")`,
    'data = yaml.safe_load(cfg.read_text())',
    `data.get("compare",{}).get("profiles",{}).pop("${profileName}", None)`,
    'cfg.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))',
    `Path(r"${join(PROJECT_ROOT, 'config', 'compare_rules', profileName + '.yaml')}").unlink(missing_ok=True)`,
  ].join('\n');
  try {
    writeFileSync(scriptPath, script);
    execSync(`python "${scriptPath}"`, { cwd: PROJECT_ROOT });
  } catch { /* best-effort */ }
  finally { try { unlinkSync(scriptPath); } catch { /* ignore */ } }
}

test.describe('Onboard Multi-Dimensional Match Key', () => {
  test.afterEach(() => cleanupProfile(TEST_PROFILE));

  test('Register 855 with 2 X12 match keys persists list in config.yaml', async ({ page }) => {
    // Navigate to X12 855 schema
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);
    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);
    await page.locator('select').selectOption('4010');
    await page.waitForTimeout(2000);
    await page.locator('input[placeholder="Search transaction types..."]').fill('855');
    await page.waitForTimeout(500);
    await page.locator('button', { hasText: /^855/ }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: 'Review Schema' }).click();
    await page.waitForTimeout(2500);
    await page.getByRole('button', { name: 'Next: Register Partner' }).click();
    await page.waitForTimeout(2000);

    // Register step: fill profile + add second key
    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW Multidim Test');

    // First row already pre-seeded (BAK / BAK03 default for 855). Confirm.
    const segInputs = page.locator('input[placeholder="BIG"]');
    await expect(segInputs.first()).not.toHaveValue('');

    // Click + Add key, fill PO1 / PO101 as second key
    await page.getByRole('button', { name: '+ Add key' }).click();
    await page.waitForTimeout(300);
    await segInputs.nth(1).fill('PO1');
    const fieldInputs = page.locator('input[placeholder="BIG02"]');
    await fieldInputs.nth(1).fill('PO101');

    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);
    await expect(page.getByText('Partner registered successfully')).toBeVisible();

    // Inspect config.yaml
    const cfgPath = join(PROJECT_ROOT, 'config', 'config.yaml');
    const body = readFileSync(cfgPath, 'utf8');

    // Profile section must show match_key as a list with both keys
    expect(body).toMatch(new RegExp(`${TEST_PROFILE}:`));
    // List form: two entries, both segments present
    expect(body).toMatch(/match_key:\s*[\s\S]*?segment:\s*BAK[\s\S]*?segment:\s*PO1/);
  });

  test('Remove button returns to singleton dict form', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);
    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);
    await page.locator('select').selectOption('4010');
    await page.waitForTimeout(2000);
    await page.locator('input[placeholder="Search transaction types..."]').fill('855');
    await page.waitForTimeout(500);
    await page.locator('button', { hasText: /^855/ }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: 'Review Schema' }).click();
    await page.waitForTimeout(2500);
    await page.getByRole('button', { name: 'Next: Register Partner' }).click();
    await page.waitForTimeout(2000);

    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW Multidim Test');

    // Add then remove → expect singleton
    await page.getByRole('button', { name: '+ Add key' }).click();
    await page.waitForTimeout(200);
    await page.getByRole('button', { name: 'Remove' }).first().click();
    await page.waitForTimeout(200);

    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);
    await expect(page.getByText('Partner registered successfully')).toBeVisible();

    const body = readFileSync(join(PROJECT_ROOT, 'config', 'config.yaml'), 'utf8');
    // Singleton form: `match_key:` followed by a mapping, NOT `- segment:`
    const profileBlock = body.split(`${TEST_PROFILE}:`)[1]?.split('\n\n')[0] || '';
    expect(profileBlock).toMatch(/match_key:\s*\n\s+segment:/);
    expect(profileBlock).not.toMatch(/match_key:\s*\n\s+-\s+segment:/);
  });
});
```

Run headed:
```
cd portal/ui
npx playwright test tests/onboard-multidim-match-key.spec.ts --headed
```

Both tests must pass.

#### Regression

```
pytest tests/test_comparator.py -v
cd portal/ui
npx playwright test tests/x12-wizard.spec.ts
npx playwright test tests/onboard-x12-855.spec.ts
```

All existing tests must stay green. Legacy profiles in `config/config.yaml`
(singleton dict form) must continue to pair — verify with:

```
python -m pyedi_core compare --profile <an existing profile>
```

If any existing profile fails to load, stop and report which and why
before patching.

## Testing & Confirmation

Pre-flight:
1. `curl http://localhost:18041/api/health` returns `{"status":"ok"}`.
2. `curl http://localhost:15174/` returns 200.
3. Bring servers up with `bash portal/dev.sh` if down.

Post-implementation manual check:
- Open `http://localhost:15174/#onboard`, pick any X12 transaction, reach
  Register Partner.
- Confirm single key row renders (pre-seeded defaults).
- Click `+ Add key` — second row appears with `Remove` button.
- Register, then inspect `config/config.yaml` — `match_key` should be a
  YAML list with both entries.
- Toggle JSON Path ↔ X12 wipes rows back to a fresh singleton (document
  this in a UI help tooltip if not obvious).

## Deliverables

- `pyedi_core/comparator/models.py` — `MatchKeyPart` dataclass, extended
  `MatchKeyConfig` with `parts` + back-compat `__post_init__`.
- `pyedi_core/comparator/__init__.py` — `_parse_profile` accepts list or
  dict.
- `pyedi_core/comparator/matcher.py` — tuple-based extraction, mixed-mode
  guard.
- `portal/api/routes/onboard.py` — `match_key` Union type, writer collapses
  N=1 to singleton, validation.
- `portal/ui/src/pages/Onboard.tsx` — `StepRegister` repeatable key rows.
- `portal/ui/src/api.ts` — request type union.
- `tests/test_comparator.py` — two new multi-key unit tests.
- `portal/ui/tests/onboard-multidim-match-key.spec.ts` — new headed E2E
  suite (2 tests).
- No DB schema changes. No new npm/pip dependencies.
- Commit only after pytest + both Playwright suites green.

## Out of Scope

- OR semantics (fallback list of candidate keys). Pure AND this iteration.
- Mixing X12 segment/field and JSON path within one profile's key list.
- Migrating SQLite `compare_runs.match_key` TEXT column to structured form
  — stringify the list/dict for display only.
- Rules page authoring UI for multi-dim keys outside the onboard wizard.
- CLI flags for passing multi-key overrides at run time (existing
  `--match-json-path` stays as a single-key override).
