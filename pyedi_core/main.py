"""
PyEDI-Core CLI Entry Point.

Command-line interface for processing EDI, CSV, and XML files.
"""

import argparse
import sys
from pathlib import Path
from typing import List

from .pipeline import Pipeline, PipelineResult


def main(args: List[str] = None) -> int:
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
    
    # Configuration
    parser.add_argument(
        "--config",
        "-c",
        default="./config/config.yaml",
        help="Path to configuration file (default: ./config/config.yaml)"
    )
    
    # File input
    parser.add_argument(
        "--file",
        "-f",
        help="Single file to process"
    )
    
    parser.add_argument(
        "--files",
        nargs="+",
        help="Multiple files to process"
    )
    
    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and transform without writing output files"
    )
    
    parser.add_argument(
        "--return-payload",
        action="store_true",
        help="Return JSON payload in memory instead of writing to disk"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    # Parse args
    parsed = parser.parse_args(args)
    
    # Create pipeline
    try:
        pipeline = Pipeline(config_path=parsed.config)
    except Exception as e:
        print(f"Error initializing pipeline: {e}", file=sys.stderr)
        return 1
    
    # Override dry_run if specified
    dry_run = parsed.dry_run
    return_payload = parsed.return_payload
    
    # Override log level if verbose
    if parsed.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run pipeline
    try:
        result = pipeline.run(
            file=parsed.file,
            files=parsed.files,
            dry_run=dry_run,
            return_payload=return_payload
        )
        
        # Handle single result
        if isinstance(result, PipelineResult):
            _print_result(result)
            return 0 if result.status == "SUCCESS" else 1
        
        # Handle multiple results
        results = result
        success_count = sum(1 for r in results if r.status == "SUCCESS")
        failed_count = sum(1 for r in results if r.status == "FAILED")
        skipped_count = sum(1 for r in results if r.status == "SKIPPED")
        
        print(f"\n=== Batch Processing Summary ===")
        print(f"Total files: {len(results)}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {failed_count}")
        print(f"  Skipped: {skipped_count}")
        
        # Print failed results
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
