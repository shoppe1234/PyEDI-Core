"""
PyEDI-Core CLI Entry Point.

Command-line interface for processing EDI, CSV, and XML files.

Subcommands:
    (default)  Process files through the pipeline
    test       Run test harness, generate expected outputs, or verify environment
"""

import argparse
import sys
from typing import List, Optional

from .pipeline import Pipeline, PipelineResult


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for CLI.

    Args:
        args: Command-line arguments (if None, uses sys.argv)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="PyEDI-Core - Configuration-driven EDI, CSV, and XML processing engine"
    )

    subparsers = parser.add_subparsers(dest="command")

    # --- "run" subcommand (also the default when no subcommand given) ---
    run_parser = subparsers.add_parser("run", help="Process files through the pipeline")
    _add_run_args(run_parser)

    # --- "test" subcommand ---
    test_parser = subparsers.add_parser("test", help="Run test harness")
    test_parser.add_argument(
        "--generate-expected",
        action="store_true",
        help="Regenerate expected output baselines",
    )
    test_parser.add_argument(
        "--verify",
        action="store_true",
        help="Check environment packages and project structure",
    )
    test_parser.add_argument(
        "--watch",
        action="store_true",
        help="Re-run tests when source files change",
    )
    test_parser.add_argument(
        "--metadata",
        default="tests/user_supplied/metadata.yaml",
        help="Path to test metadata YAML (default: tests/user_supplied/metadata.yaml)",
    )
    test_parser.add_argument(
        "--config",
        "-c",
        default="./config/config.yaml",
        help="Path to configuration file (default: ./config/config.yaml)",
    )
    test_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed discrepancy output",
    )

    # --- "validate" subcommand ---
    validate_parser = subparsers.add_parser("validate", help="Validate a DSL schema")
    validate_parser.add_argument(
        "--dsl", required=True, help="Path to DSL .txt file"
    )
    validate_parser.add_argument(
        "--sample", default=None, help="Path to sample data file"
    )
    validate_parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output JSON instead of human-readable report",
    )
    validate_parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show all field traces",
    )
    validate_parser.add_argument(
        "--output-dir", default="./schemas/compiled",
        help="Compiled YAML output directory (default: ./schemas/compiled)",
    )

    # Add run args to the top-level parser too (backward compat)
    _add_run_args(parser)

    parsed = parser.parse_args(args)

    if parsed.command == "test":
        return _handle_test(parsed)

    if parsed.command == "validate":
        return _handle_validate(parsed)

    # Default: run pipeline (whether via `pyedi run ...` or `pyedi --file ...`)
    return _handle_run(parsed)


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    """Add file-processing arguments to a parser."""
    parser.add_argument(
        "--config", "-c",
        default="./config/config.yaml",
        help="Path to configuration file (default: ./config/config.yaml)",
    )
    parser.add_argument("--file", "-f", help="Single file to process")
    parser.add_argument("--files", nargs="+", help="Multiple files to process")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate and transform without writing output files",
    )
    parser.add_argument(
        "--return-payload", action="store_true",
        help="Return JSON payload in memory instead of writing to disk",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging",
    )


# ---------------------------------------------------------------------------
# Run handler (existing behavior)
# ---------------------------------------------------------------------------

def _handle_run(parsed: argparse.Namespace) -> int:
    """Process files through the pipeline."""
    try:
        pipeline = Pipeline(config_path=parsed.config)
    except Exception as e:
        print(f"Error initializing pipeline: {e}", file=sys.stderr)
        return 1

    dry_run = parsed.dry_run
    return_payload = parsed.return_payload

    if parsed.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        result = pipeline.run(
            file=parsed.file,
            files=parsed.files,
            dry_run=dry_run,
            return_payload=return_payload,
        )

        if isinstance(result, PipelineResult):
            _print_result(result)
            return 0 if result.status == "SUCCESS" else 1

        results = result
        success_count = sum(1 for r in results if r.status == "SUCCESS")
        failed_count = sum(1 for r in results if r.status == "FAILED")
        skipped_count = sum(1 for r in results if r.status == "SKIPPED")

        print(f"\n=== Batch Processing Summary ===")
        print(f"Total files: {len(results)}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {failed_count}")
        print(f"  Skipped: {skipped_count}")

        if failed_count > 0:
            print(f"\n=== Failed Files ===")
            for r in results:
                if r.status == "FAILED":
                    print(f"  {r.source_file}: {r.errors}")

        return 0 if failed_count == 0 else 1

    except Exception as e:
        print(f"Error running pipeline: {e}", file=sys.stderr)
        if parsed.verbose:
            import traceback
            traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# Test handler
# ---------------------------------------------------------------------------

def _handle_test(parsed: argparse.Namespace) -> int:
    """Dispatch test subcommand."""
    from . import test_harness

    if parsed.verify:
        return test_harness.verify()

    if parsed.generate_expected:
        return test_harness.generate_expected(
            config_path=parsed.config,
            metadata_path=parsed.metadata,
        )

    if parsed.watch:
        return _watch_tests(parsed)

    return test_harness.run_tests(
        config_path=parsed.config,
        metadata_path=parsed.metadata,
        verbose=parsed.verbose,
    )


def _watch_tests(parsed: argparse.Namespace) -> int:
    """Re-run tests when source files change."""
    import time

    watch_dirs = ["pyedi_core", "tests/user_supplied", "config", "schemas"]
    print(f"Watching for changes in: {', '.join(watch_dirs)}")
    print("Press Ctrl+C to stop.\n")

    def _snapshot():
        times = {}
        for d in watch_dirs:
            for root, _, files in os.walk(d):
                for fname in files:
                    p = os.path.join(root, fname)
                    try:
                        times[p] = os.path.getmtime(p)
                    except OSError:
                        pass
        return times

    import os
    from . import test_harness

    prev = _snapshot()
    # Initial run
    test_harness.run_tests(
        config_path=parsed.config,
        metadata_path=parsed.metadata,
        verbose=parsed.verbose,
    )

    try:
        while True:
            time.sleep(2)
            curr = _snapshot()
            if curr != prev:
                changed = [k for k in curr if curr.get(k) != prev.get(k)]
                print(f"\n--- Changes detected: {len(changed)} file(s) ---")
                for c in changed[:5]:
                    print(f"  {c}")
                if len(changed) > 5:
                    print(f"  ... and {len(changed) - 5} more")
                print()
                test_harness.run_tests(
                    config_path=parsed.config,
                    metadata_path=parsed.metadata,
                    verbose=parsed.verbose,
                )
                prev = curr
    except KeyboardInterrupt:
        print("\nWatch mode stopped.")
        return 0


# ---------------------------------------------------------------------------
# Validate handler
# ---------------------------------------------------------------------------

def _handle_validate(parsed: argparse.Namespace) -> int:
    """Dispatch validate subcommand."""
    from .validator import validate

    try:
        result = validate(
            dsl_path=parsed.dsl,
            sample_path=parsed.sample,
            compiled_dir=parsed.output_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if parsed.json_output:
        _print_validate_json(result)
    else:
        _print_validate_report(result, verbose=parsed.verbose)
    return 0


def _print_validate_report(result: "object", verbose: bool = False) -> None:
    """Human-readable console output for validation results."""
    from .validator import ValidationResult

    assert isinstance(result, ValidationResult)

    yaml_data = result.compiled_yaml
    print(f"\n=== DSL Compilation Report ===")
    print(f"Source:           {result.dsl_path}")
    print(f"Compiled To:      {result.compiled_yaml_path}")
    print(f"Transaction Type: {yaml_data.get('transaction_type', 'N/A')}")
    print(f"Delimiter:        \"{yaml_data.get('schema', {}).get('delimiter', ',')}\"")
    print(f"Records Found:    {len(result.records)} ({', '.join(result.records.keys())})")

    print(f"\n=== Schema Columns ({len(result.columns)} fields) ===")
    print(f"  {'Name':<30} {'Type':<10} {'DSL Type':<12} {'OK?'}")
    limit = len(result.columns) if verbose else min(20, len(result.columns))
    for col in result.columns[:limit]:
        ok = "YES" if col.type_preserved else "NO"
        dsl = col.dsl_type or "—"
        print(f"  {col.name:<30} {col.compiled_type:<10} {dsl:<12} {ok}")
    if not verbose and len(result.columns) > 20:
        print(f"  ... and {len(result.columns) - 20} more (use --verbose to see all)")

    print(f"\n=== Type Preservation ===")
    if not result.type_warnings:
        print(f"  All types preserved correctly.")
    else:
        shown = result.type_warnings if verbose else result.type_warnings[:5]
        for tw in shown:
            print(f"  WARNING: {tw.field_name} ({tw.record_name}): "
                  f"DSL={tw.dsl_type} -> compiled={tw.compiled_type}")
        if not verbose and len(result.type_warnings) > 5:
            print(f"  ... {len(result.type_warnings) - 5} more warnings (use --verbose)")

    if result.compilation_warnings:
        print(f"\n=== Compilation Warnings ===")
        for w in result.compilation_warnings:
            print(f"  {w}")

    print(f"\n=== Record Definitions ===")
    for rname, fields in result.records.items():
        preview = ", ".join(fields[:5])
        suffix = f", ..." if len(fields) > 5 else ""
        print(f"  {rname} -> {len(fields)} fields [{preview}{suffix}]")

    if result.sample_row_count is not None:
        print(f"\n=== Sample File ({result.sample_row_count} rows parsed) ===")

        if result.coverage:
            c = result.coverage
            print(f"\n=== Mapping Coverage ===")
            print(f"  Source fields: {c.source_fields_total} total, "
                  f"{c.source_fields_mapped} mapped, "
                  f"{len(c.source_fields_unmapped)} unmapped")
            print(f"  Target fields: {c.target_fields_total} total, "
                  f"{c.target_fields_populated} populated, "
                  f"{len(c.target_fields_empty)} empty")
            print(f"  Coverage: {c.coverage_pct:.1f}%")
            if c.source_fields_unmapped:
                print(f"\n  Unmapped: {c.source_fields_unmapped[:10]}")
            if c.target_fields_empty:
                print(f"  Empty:    {c.target_fields_empty[:10]}")

        if result.field_traces:
            max_traces = len(result.field_traces) if verbose else min(3, len(result.field_traces))
            print(f"\n=== Field Trace (first {max_traces} rows) ===")
            for row_idx in range(max_traces):
                print(f"  Row {row_idx + 1}:")
                traces = result.field_traces[row_idx]
                shown = traces if verbose else traces[:10]
                for ft in shown:
                    marker = "=" if ft.mapped else "∅"
                    val = repr(ft.value) if ft.mapped else "—"
                    print(f"    {ft.target_field:<30} <- {ft.source_path:<30} {marker} {val}")
                if not verbose and len(traces) > 10:
                    print(f"    ... and {len(traces) - 10} more fields")

    if result.sample_errors:
        print(f"\n=== Sample Errors ===")
        for e in result.sample_errors:
            print(f"  {e}")


def _print_validate_json(result: "object") -> None:
    """JSON output for validation results."""
    import dataclasses
    import json as json_mod

    data = dataclasses.asdict(result)
    print(json_mod.dumps(data, indent=2, default=str))


def _print_result(result: PipelineResult) -> None:
    """Print a PipelineResult in a human-readable format."""
    print(f"\n=== Processing Result ===")
    print(f"Status: {result.status}")
    print(f"Correlation ID: {result.correlation_id}")
    print(f"Source File: {result.source_file}")
    print(f"Transaction Type: {result.transaction_type}")
    print(f"Processing Time: {result.processing_time_ms}ms")

    if result.output_path:
        print(f"Output Path: {result.output_path}")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error}")


if __name__ == "__main__":
    sys.exit(main())
