import pytest
import yaml
import json
import shutil
import os
import math
import warnings
from pathlib import Path
from pyedi_core import Pipeline

pytestmark = pytest.mark.integration

@pytest.fixture(scope="session", autouse=True)
def clear_outputs():
    outputs_dir = Path("tests/user_supplied/outputs")
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

# Load user-supplied test cases
def load_test_cases():
    """Load test cases from metadata.yaml"""
    metadata_path = Path('tests/user_supplied/metadata.yaml')
    if not metadata_path.exists():
        return []
    
    with open(metadata_path) as f:
        metadata = yaml.safe_load(f)
    
    return metadata.get('test_cases', [])

@pytest.mark.parametrize("test_case", load_test_cases())
def test_user_supplied_file(test_case):
    """Test each user-supplied file against expected output"""
    
    input_path = Path('tests/user_supplied') / test_case['input_file']
    expected_path = Path('tests/user_supplied') / test_case['expected_output']
    output_path = Path('tests/user_supplied') / test_case['output_file']
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    from pyedi_core.drivers.x12_handler import X12Handler
    
    pipeline = Pipeline(config_path='./config/config.yaml')
    
    target_inbound_dir = test_case.get('target_inbound_dir')
    run_path = input_path
    copied_path = None
    
    dry_run = test_case.get('dry_run', True)
    skip_fields = set(test_case.get('skip_fields', []))
    
    try:
        actual_payload = None
        status = 'SUCCESS'
        errors = []
        
        if target_inbound_dir:
            target_dir = Path(target_inbound_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            copied_path = target_dir / input_path.name
            shutil.copy(input_path, copied_path)
            run_path = copied_path
            
            # Run pipeline
            result = pipeline.run(file=str(run_path), return_payload=True, dry_run=dry_run)
            status = result.status
            errors = result.errors
            actual_payload = result.payload
        else:
            # Direct handler bypass for pure unmapped data comparisons
            if test_case.get('transaction_type') == 'x12':
                driver = X12Handler()
                actual_payload = driver.read(str(input_path))
                status = 'SUCCESS'
            else:
                pytest.fail("Test case lacks target_inbound_dir and is not a direct x12 comparison.")
        
        # Always dump the payload to output_path
        with open(output_path, 'w') as f:
            json.dump(actual_payload, f, indent=2)

        if test_case['should_succeed']:
            if status != 'SUCCESS':
                pytest.fail(f"Expected success but got {status}. Errors: {errors}")
            
            with open(expected_path) as f:
                expected = json.load(f)
            
            with open(output_path) as f:
                actual = json.load(f)
                
            discrepancies = []
            compare_outputs(actual, expected, skip_fields, test_case['name'], discrepancies, path="")
            
            # Size discrepancy check
            actual_size = output_path.stat().st_size
            expected_size = expected_path.stat().st_size
            if actual_size != expected_size:
                diff_pct = ((actual_size - expected_size) / expected_size) * 100
                size_msg = f"Size diff: expected={expected_size}b, actual={actual_size}b ({diff_pct:+.1f}%)"
                if abs(diff_pct) > 1.0: # Only care if > 1% diff
                    discrepancies.append(size_msg)
            
            if discrepancies:
                print(f"\nDISCREPANCY REPORT — {test_case['name']}")
                for d in discrepancies:
                    print(f"  - {d}")

                field_diffs = [x for x in discrepancies if not x.startswith("Size diff")]
                is_strict = test_case.get('strict', True)
                if field_diffs and is_strict:
                    pytest.fail(f"Found {len(field_diffs)} field discrepancies compared to expected output.")
                elif discrepancies:
                    warnings.warn(f"Non-fatal discrepancies found for {test_case['name']}:\n" + "\n".join(discrepancies))
            
        else:
            if result.status != 'FAILED':
                pytest.fail(f"Expected failure but got {result.status}")
                
            if 'expected_error_stage' in test_case:
                error_json_path = Path('./failed') / f"{run_path.stem}.error.json"
                if not error_json_path.exists():
                    pytest.fail("No error.json found")
                
                with open(error_json_path) as f:
                    error_data = json.load(f)
                
                if error_data.get('stage') != test_case['expected_error_stage']:
                    pytest.fail(f"Expected error at {test_case['expected_error_stage']} but got {error_data.get('stage')}")
                    
    finally:
        if copied_path and copied_path.exists():
            os.remove(copied_path)

def compare_outputs(actual, expected, skip_fields, context, discrepancies, path=""):
    """Deep compare two dictionaries and collect discrepancies."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        all_keys = set(expected.keys()) | set(actual.keys())
        for k in all_keys:
            if k in skip_fields:
                continue
                
            current_path = f"{path}.{k}" if path else k
            
            if k not in actual:
                discrepancies.append(f"Missing key in actual: '{current_path}'")
                continue
            if k not in expected:
                discrepancies.append(f"Unexpected key in actual: '{current_path}'")
                continue
                
            compare_outputs(actual[k], expected[k], skip_fields, context, discrepancies, current_path)
            
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            discrepancies.append(f"List length mismatch at '{path}': expected {len(expected)}, got {len(actual)}")
        else:
            for i, (a, e) in enumerate(zip(actual, expected)):
                compare_outputs(a, e, skip_fields, context, discrepancies, f"{path}[{i}]")
            
    else:
        # Value comparison
        if isinstance(actual, float) and isinstance(expected, float) and math.isnan(actual) and math.isnan(expected):
            return
            
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and type(actual) == type(expected):
            if abs(actual - expected) >= 0.01:
                discrepancies.append(f"Value mismatch at '{path}': expected {expected}, got {actual}")
        else:
            if actual != expected:
                discrepancies.append(f"Value mismatch at '{path}': expected '{expected}', got '{actual}'")
