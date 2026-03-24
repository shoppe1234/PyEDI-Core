"""
Test Harness for PyEDI-Core.

Provides run_tests, generate_expected, and verify commands
accessible via the `pyedi test` CLI subcommand.
"""

import importlib
import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from .pipeline import Pipeline


# ---------------------------------------------------------------------------
# compare_outputs — recursive deep comparison
# ---------------------------------------------------------------------------

def compare_outputs(
    actual: Any,
    expected: Any,
    skip_fields: Set[str],
    discrepancies: List[str],
    path: str = ""
) -> None:
    """Deep compare two structures and collect discrepancies."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        all_keys = set(expected.keys()) | set(actual.keys())
        for k in sorted(all_keys):
            if k in skip_fields:
                continue
            current_path = f"{path}.{k}" if path else k
            if k not in actual:
                discrepancies.append(f"Missing key in actual: '{current_path}'")
                continue
            if k not in expected:
                discrepancies.append(f"Unexpected key in actual: '{current_path}'")
                continue
            compare_outputs(actual[k], expected[k], skip_fields, discrepancies, current_path)

    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            discrepancies.append(
                f"List length mismatch at '{path}': expected {len(expected)}, got {len(actual)}"
            )
        else:
            for i, (a, e) in enumerate(zip(actual, expected)):
                compare_outputs(a, e, skip_fields, discrepancies, f"{path}[{i}]")
    else:
        if isinstance(actual, float) and isinstance(expected, float):
            if math.isnan(actual) and math.isnan(expected):
                return
        if (
            isinstance(actual, (int, float))
            and isinstance(expected, (int, float))
            and type(actual) == type(expected)
        ):
            if abs(actual - expected) >= 0.01:
                discrepancies.append(
                    f"Value mismatch at '{path}': expected {expected}, got {actual}"
                )
        else:
            if actual != expected:
                discrepancies.append(
                    f"Value mismatch at '{path}': expected '{expected}', got '{actual}'"
                )


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------

def run_tests(
    config_path: str = "./config/config.yaml",
    metadata_path: str = "tests/user_supplied/metadata.yaml",
    verbose: bool = False,
) -> int:
    """
    Run all user-supplied test cases sequentially.

    Returns:
        0 if all tests pass, 1 if any fail.
    """
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        print(f"Metadata file not found: {metadata_path}", file=sys.stderr)
        return 1

    with open(metadata_file) as f:
        metadata = yaml.safe_load(f)

    test_cases = metadata.get("test_cases", [])
    if not test_cases:
        print("No test cases found in metadata.")
        return 0

    # Lazy imports — only needed for direct-read bypass
    from .drivers.x12_handler import X12Handler
    from .drivers.xml_handler import XMLHandler

    pipeline = Pipeline(config_path=config_path)
    base_dir = metadata_file.parent

    # Clear outputs dir
    outputs_dir = base_dir / "outputs"
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    passed = 0
    failed = 0
    warned = 0
    results_detail: List[str] = []

    for case in test_cases:
        name = case["name"]
        input_path = base_dir / case["input_file"]
        output_path = base_dir / case["output_file"]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        target_inbound_dir = case.get("target_inbound_dir")
        dry_run = case.get("dry_run", True)
        skip_fields = set(case.get("skip_fields", []))
        copied_path = None

        try:
            # --- execute ---
            actual_payload = None
            status = "SUCCESS"
            errors: List[str] = []

            if target_inbound_dir:
                target_dir = Path(target_inbound_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                copied_path = target_dir / input_path.name
                shutil.copy(input_path, copied_path)

                result = pipeline.run(
                    file=str(copied_path), return_payload=True, dry_run=dry_run
                )
                status = result.status
                errors = result.errors
                actual_payload = result.payload
            else:
                if case.get("transaction_type") == "x12":
                    driver = X12Handler()
                    actual_payload = driver.read(str(input_path))
                elif case.get("transaction_type") == "cxml":
                    driver = XMLHandler()
                    actual_payload = driver.read(str(input_path))
                else:
                    results_detail.append(f"  FAIL  {name} — no target_inbound_dir and not x12/cxml")
                    failed += 1
                    continue

            # Write actual output
            with open(output_path, "w") as f:
                json.dump(actual_payload, f, indent=2)

            # --- validate ---
            if case.get("should_succeed", True):
                if status != "SUCCESS":
                    results_detail.append(f"  FAIL  {name} — expected SUCCESS, got {status}: {errors}")
                    failed += 1
                    continue

                expected_path = base_dir / case["expected_output"]
                if not expected_path.exists():
                    results_detail.append(f"  FAIL  {name} — expected output file missing: {expected_path}")
                    failed += 1
                    continue

                with open(expected_path) as f:
                    expected = json.load(f)
                with open(output_path) as f:
                    actual = json.load(f)

                discrepancies: List[str] = []
                compare_outputs(actual, expected, skip_fields, discrepancies)

                # Size check
                actual_size = output_path.stat().st_size
                expected_size = expected_path.stat().st_size
                if actual_size != expected_size:
                    diff_pct = ((actual_size - expected_size) / expected_size) * 100
                    if abs(diff_pct) > 1.0:
                        discrepancies.append(
                            f"Size diff: expected={expected_size}b, actual={actual_size}b ({diff_pct:+.1f}%)"
                        )

                if discrepancies:
                    field_diffs = [d for d in discrepancies if not d.startswith("Size diff")]
                    is_strict = case.get("strict", True)

                    if field_diffs and is_strict:
                        results_detail.append(f"  FAIL  {name} — {len(field_diffs)} field discrepancies")
                        if verbose:
                            for d in discrepancies:
                                results_detail.append(f"        {d}")
                        failed += 1
                    else:
                        results_detail.append(f"  WARN  {name} — non-fatal discrepancies ({len(discrepancies)})")
                        if verbose:
                            for d in discrepancies:
                                results_detail.append(f"        {d}")
                        warned += 1
                        passed += 1
                else:
                    results_detail.append(f"  PASS  {name}")
                    passed += 1

            else:
                # should_succeed == False
                if status != "FAILED":
                    results_detail.append(f"  FAIL  {name} — expected FAILED, got {status}")
                    failed += 1
                    continue

                if "expected_error_stage" in case:
                    error_json_path = Path("./failed") / f"{Path(case['input_file']).stem}.error.json"
                    if error_json_path.exists():
                        with open(error_json_path) as f:
                            error_data = json.load(f)
                        if error_data.get("stage") != case["expected_error_stage"]:
                            results_detail.append(
                                f"  FAIL  {name} — expected stage {case['expected_error_stage']}, "
                                f"got {error_data.get('stage')}"
                            )
                            failed += 1
                            continue

                results_detail.append(f"  PASS  {name}")
                passed += 1

        finally:
            if copied_path and copied_path.exists():
                os.remove(copied_path)

    # --- summary ---
    total = passed + failed
    print(f"\n=== Test Harness Results ===")
    for line in results_detail:
        print(line)
    print(f"\nTotal: {total}  Passed: {passed}  Failed: {failed}  Warnings: {warned}")

    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# generate_expected
# ---------------------------------------------------------------------------

def generate_expected(
    config_path: str = "./config/config.yaml",
    metadata_path: str = "tests/user_supplied/metadata.yaml",
) -> int:
    """
    Regenerate expected output baselines for all test cases.

    Returns:
        0 on success, 1 on failure.
    """
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        print(f"Metadata file not found: {metadata_path}", file=sys.stderr)
        return 1

    with open(metadata_file) as f:
        metadata = yaml.safe_load(f)

    test_cases = metadata.get("test_cases", [])
    if not test_cases:
        print("No test cases found in metadata.")
        return 0

    pipeline = Pipeline(config_path=config_path)
    base_dir = metadata_file.parent
    success_count = 0
    fail_count = 0

    for case in test_cases:
        name = case["name"]
        input_path = base_dir / case["input_file"]
        expected_path = base_dir / case["expected_output"]
        expected_path.parent.mkdir(parents=True, exist_ok=True)

        target_inbound_dir = case.get("target_inbound_dir")
        if not target_inbound_dir:
            print(f"  SKIP  {name} — no target_inbound_dir")
            continue

        target_dir = Path(target_inbound_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        source_file = input_path
        if not source_file.exists():
            source_file = Path(source_file.name)

        copied_path = target_dir / source_file.name
        shutil.copy(source_file, copied_path)

        try:
            result = pipeline.run(file=str(copied_path), return_payload=True, dry_run=True)
            if result.status == "SUCCESS":
                with open(expected_path, "w") as f:
                    json.dump(result.payload, f, indent=2)
                print(f"  OK    {name} -> {expected_path}")
                success_count += 1
            else:
                print(f"  FAIL  {name} — {result.errors}")
                fail_count += 1
        finally:
            if copied_path.exists():
                os.remove(copied_path)

    print(f"\nGenerated: {success_count}  Failed: {fail_count}")
    return 0 if fail_count == 0 else 1


# ---------------------------------------------------------------------------
# verify — environment + structure checks
# ---------------------------------------------------------------------------

REQUIRED_PACKAGES = [
    ("badx12", "badx12"),
    ("pandas", "pandas"),
    ("yaml", "pyyaml"),
    ("pydantic", "pydantic"),
    ("structlog", "structlog"),
    ("defusedxml", "defusedxml"),
]

REQUIRED_DIRS = [
    "pyedi_core",
    "pyedi_core/core",
    "pyedi_core/drivers",
    "tests",
    "config",
]

REQUIRED_FILES = [
    "pyproject.toml",
    "pyedi_core/__init__.py",
    "pyedi_core/main.py",
    "pyedi_core/pipeline.py",
    "pyedi_core/core/logger.py",
    "pyedi_core/core/manifest.py",
    "pyedi_core/core/error_handler.py",
    "pyedi_core/core/mapper.py",
    "pyedi_core/core/schema_compiler.py",
    "pyedi_core/drivers/base.py",
    "pyedi_core/drivers/x12_handler.py",
    "pyedi_core/drivers/csv_handler.py",
    "pyedi_core/drivers/xml_handler.py",
    "config/config.yaml",
]


def verify() -> int:
    """
    Check environment packages and project structure.

    Returns:
        0 if all checks pass, 1 if any fail.
    """
    ok = True

    # --- packages ---
    print("=== Environment Packages ===")
    print(f"Python {sys.version}")
    for import_name, package_name in REQUIRED_PACKAGES:
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", "unknown")
            print(f"  OK    {package_name} {version}")
        except ImportError:
            print(f"  MISS  {package_name}")
            ok = False

    # --- directories ---
    print("\n=== Project Structure ===")
    for d in REQUIRED_DIRS:
        if Path(d).is_dir():
            print(f"  OK    {d}/")
        else:
            print(f"  MISS  {d}/")
            ok = False

    # --- files ---
    for f in REQUIRED_FILES:
        if Path(f).is_file():
            print(f"  OK    {f}")
        else:
            print(f"  MISS  {f}")
            ok = False

    print()
    if ok:
        print("All checks passed.")
    else:
        print("Some checks failed.", file=sys.stderr)

    return 0 if ok else 1
