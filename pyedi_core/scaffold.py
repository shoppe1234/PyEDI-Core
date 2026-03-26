"""Scaffold compare rules YAML from compiled schema.

Reads column definitions from a compiled schema YAML, generates a starter
compare rules file with correct numeric flags based on column types.
Optionally seeds the crosswalk table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


def scaffold_rules(
    schema_path: str,
    output_path: Optional[str] = None,
    profile: Optional[str] = None,
    db_path: Optional[str] = None,
) -> str:
    """Generate a starter compare rules YAML from a compiled schema.

    Args:
        schema_path: Path to compiled schema YAML
        output_path: Output rules YAML path (default: config/compare_rules/<stem>.yaml)
        profile: Profile name for optional crosswalk seeding
        db_path: SQLite DB path for crosswalk seeding

    Returns:
        Path to the generated rules YAML file
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    columns = schema.get("schema", {}).get("columns", [])
    if not columns:
        raise ValueError(f"No columns found in schema: {schema_path}")

    numeric_types = {"float", "integer", "decimal"}

    classification: list[dict] = []
    for col in columns:
        col_type = col.get("type", "string").lower()
        entry = {
            "segment": "*",
            "field": col["name"],
            "severity": "hard",
            "ignore_case": False,
            "numeric": col_type in numeric_types,
        }
        classification.append(entry)

    # Add default wildcard
    classification.append({
        "segment": "*",
        "field": "*",
        "severity": "hard",
        "ignore_case": False,
        "numeric": False,
    })

    rules = {"classification": classification, "ignore": []}

    # Determine output path
    if output_path is None:
        stem = Path(schema_path).stem.replace("_map", "")
        output_path = f"config/compare_rules/{stem}.yaml"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(rules, f, default_flow_style=False, sort_keys=False)

    # Optionally seed crosswalk table
    if profile and db_path:
        from pyedi_core.comparator.store import init_db, upsert_crosswalk

        init_db(db_path)
        for col in columns:
            col_type = col.get("type", "string").lower()
            upsert_crosswalk(
                db_path=db_path,
                profile=profile,
                field_name=col["name"],
                severity="hard",
                numeric=col_type in numeric_types,
                ignore_case=False,
                amount_variance=None,
                updated_by="scaffold",
            )

    return output_path
