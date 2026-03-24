# TODO

## Low Priority

- [ ] **Standardize YAML quoting conventions** — 11 YAML files use mixed quoting styles (single, double, unquoted). Proposed convention: single quotes for numeric-looking strings/delimiters, no quotes for plain strings, double quotes only for escapes. Requires before/after `yaml.safe_load()` comparison per file to avoid type-coercion breakage. See `instructions/tier3_tier4_remaining_tasks.md` Task 4 for full details.
