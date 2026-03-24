"""Test harness API routes — run tests, list cases, verify environment."""

from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, HTTPException

from ..models import TestCaseResult, TestRunRequest, TestRunResponse

router = APIRouter(prefix="/api/test", tags=["test"])


@router.post("/run", response_model=TestRunResponse)
def test_run(req: TestRunRequest) -> TestRunResponse:
    """Run the test harness and return structured results."""
    import io
    import sys

    from pyedi_core.test_harness import run_tests

    # Capture stdout to parse results
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        exit_code = run_tests(
            metadata_path=req.metadata_path or "tests/user_supplied/metadata.yaml",
            verbose=req.verbose,
        )
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()
    lines = output.strip().splitlines()

    # Parse results from output
    cases: List[TestCaseResult] = []
    total = passed = failed = warned = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("PASS"):
            name = stripped.split(None, 1)[1] if len(stripped.split(None, 1)) > 1 else ""
            cases.append(TestCaseResult(name=name, status="PASS"))
        elif stripped.startswith("FAIL"):
            parts = stripped.split(" — ", 1)
            name = parts[0].replace("FAIL", "").strip()
            detail = parts[1] if len(parts) > 1 else ""
            cases.append(TestCaseResult(name=name, status="FAIL", details=detail))
        elif stripped.startswith("WARN"):
            parts = stripped.split(" — ", 1)
            name = parts[0].replace("WARN", "").strip()
            detail = parts[1] if len(parts) > 1 else ""
            cases.append(TestCaseResult(name=name, status="WARN", details=detail))
        elif stripped.startswith("Total:"):
            # Parse summary line: Total: N  Passed: N  Failed: N  Warnings: N
            import re

            m = re.search(r"Total:\s*(\d+)\s+Passed:\s*(\d+)\s+Failed:\s*(\d+)\s+Warnings:\s*(\d+)", stripped)
            if m:
                total, passed, failed, warned = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))

    return TestRunResponse(
        total=total, passed=passed, failed=failed, warned=warned, cases=cases,
    )


@router.get("/cases")
def test_cases(
    metadata_path: str = "tests/user_supplied/metadata.yaml",
) -> List[Dict[str, Any]]:
    """List test cases from metadata.yaml."""
    meta_file = Path(metadata_path)
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail=f"Metadata not found: {metadata_path}")

    with open(meta_file) as f:
        metadata = yaml.safe_load(f)

    return metadata.get("test_cases", [])


@router.post("/generate-expected")
def generate_expected(
    metadata_path: str = "tests/user_supplied/metadata.yaml",
) -> Dict[str, str]:
    """Regenerate expected output baselines."""
    from pyedi_core.test_harness import generate_expected as gen_expected

    exit_code = gen_expected(metadata_path=metadata_path)
    if exit_code != 0:
        raise HTTPException(status_code=500, detail="generate_expected failed")
    return {"status": "ok"}


@router.get("/verify")
def verify_environment() -> Dict[str, Any]:
    """Check environment packages and project structure."""
    import io
    import sys

    from pyedi_core.test_harness import verify

    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        exit_code = verify()
    finally:
        sys.stdout = old_stdout

    return {
        "exit_code": exit_code,
        "output": buf.getvalue(),
        "ok": exit_code == 0,
    }
