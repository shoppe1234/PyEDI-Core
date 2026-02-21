import pytest
import yaml
import json
import shutil
import os
from pathlib import Path
from pyedi_core import Pipeline

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
    
    # Setup
    input_path = Path('tests/user_supplied') / test_case['input_file']
    expected_path = Path('tests/user_supplied') / test_case['expected_output']
    
    pipeline = Pipeline(config_path='./config/config.yaml')
    
    # Handle CSV mapping (PCR-2025-002)
    target_inbound_dir = test_case.get('target_inbound_dir')
    run_path = input_path
    copied_path = None
    
    if target_inbound_dir:
        # Copy to the required target inbound directory
        target_dir = Path(target_inbound_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        copied_path = target_dir / input_path.name
        shutil.copy(input_path, copied_path)
        run_path = copied_path
        
    try:
        # Run pipeline
        result = pipeline.run(file=str(run_path), return_payload=True)
        
        # Validate success/failure expectation
        if test_case['should_succeed']:
            assert result.status == 'SUCCESS', \
                f"Expected success but got {result.status}. Errors: {result.errors}"
            
            # Load expected output
            with open(expected_path) as f:
                expected = json.load(f)
            
            # Compare actual vs expected
            assert_output_matches(result.payload, expected, test_case['name'])
            
        else:
            # Should fail
            assert result.status == 'FAILED', \
                f"Expected failure but got {result.status}"
            
            # Check error stage if specified
            if 'expected_error_stage' in test_case:
                error_json_path = Path('./failed') / f"{run_path.stem}.error.json"
                assert error_json_path.exists(), "No error.json found"
                
                with open(error_json_path) as f:
                    error_data = json.load(f)
                
                assert error_data['stage'] == test_case['expected_error_stage'], \
                    f"Expected error at {test_case['expected_error_stage']} " \
                    f"but got {error_data['stage']}"
    finally:
        # Clean up copied file
        if copied_path and copied_path.exists():
            os.remove(copied_path)

def assert_output_matches(actual, expected, test_name):
    """Deep comparison of actual vs expected output"""
    
    # Compare envelope
    assert actual['envelope']['schema_version'] == expected['envelope']['schema_version']
    assert actual['envelope']['transaction_type'] == expected['envelope']['transaction_type']
    assert actual['envelope']['input_format'] == expected['envelope']['input_format']
    # Note: Don't compare UUIDs and timestamps as they're generated
    
    # Compare payload structure
    assert set(actual.keys()) == set(expected.keys()), \
        f"Payload keys don't match for {test_name}"

    # Compare header
    if 'header' in expected:
        assert_dict_matches(
            actual['header'],
            expected['header'],
            f"{test_name} header"
        )
    
    # Compare lines
    if 'lines' in expected:
        assert len(actual['lines']) == len(expected['lines']), \
            f"Line count mismatch for {test_name}"

import math

def assert_dict_matches(actual, expected, context):
    """Deep compare two dictionaries for the test suite"""
    assert set(actual.keys()) == set(expected.keys()), f"Keys mismatch in {context}"
    for k in expected:
        if isinstance(expected[k], dict):
            assert_dict_matches(actual[k], expected[k], f"{context}.{k}")
        elif isinstance(expected[k], list):
            assert len(actual[k]) == len(expected[k]), f"List length mismatch in {context}.{k}"
            for i, (a, e) in enumerate(zip(actual[k], expected[k])):
                if isinstance(e, dict):
                    assert_dict_matches(a, e, f"{context}.{k}[{i}]")
                else:
                    if isinstance(a, float) and isinstance(e, float) and math.isnan(a) and math.isnan(e):
                        continue
                    assert a == e, f"Value mismatch in {context}.{k}[{i}]: expected {e}, got {a}"
        else:
            if isinstance(actual[k], float) and isinstance(expected[k], float) and math.isnan(actual[k]) and math.isnan(expected[k]):
                continue
            assert actual[k] == expected[k], f"Value mismatch in {context}.{k}: expected {expected[k]}, got {actual[k]}"
