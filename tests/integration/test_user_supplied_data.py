import pytest
import yaml
import json
from pathlib import Path
from pyedi_core.drivers.x12_handler import X12Handler

# Load user-supplied test cases
def load_test_cases():
    """Load test cases from metadata.yaml"""
    metadata_path = Path('tests/user_supplied/metadata.yaml')
    if not metadata_path.exists():
        pytest.skip("No user-supplied test data found")
    
    with open(metadata_path) as f:
        metadata = yaml.safe_load(f)
    
    return metadata['test_cases']

@pytest.mark.parametrize("test_case", load_test_cases())
def test_user_supplied_file(test_case):
    """Test each user-supplied file against expected output"""
    
    # Setup
    input_path = Path('tests/user_supplied') / test_case['input_file']
    expected_path = Path('tests/user_supplied') / test_case['expected_output']
    
    driver = X12Handler()
    actual = driver.read(str(input_path))
    
    # Validate expectation
    if test_case['should_succeed']:
        # Load expected output
        with open(expected_path) as f:
            expected = json.load(f)
        
        # Compare actual vs expected
        assert_output_matches(actual, expected, test_case['name'])
        
    else:
        # Check error scenario
        pytest.fail("Test case expected to fail not implemented")

def assert_output_matches(actual, expected, test_name):
    """Deep comparison of actual vs expected output"""
    assert_dict_matches(actual, expected, test_name)

def assert_dict_matches(actual, expected, context):
    """Compare two dicts with helpful error messages"""
    for key, expected_value in expected.items():
        if key in ['id', 'timestamp', '_source_file']:
            continue # skip generated keys
            
        assert key in actual, f"Missing key '{key}' in {context}"
        
        actual_value = actual[key]
        
        if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            assert abs(actual_value - expected_value) < 0.01, \
                f"Value mismatch for '{key}' in {context}: expected {expected_value}, got {actual_value}"
        elif isinstance(expected_value, dict) and isinstance(actual_value, dict):
            assert_dict_matches(actual_value, expected_value, f"{context}.{key}")
        elif isinstance(expected_value, list) and isinstance(actual_value, list):
            assert len(actual_value) == len(expected_value), f"List length mismatch for '{key}' in {context}"
            for i, (act_item, exp_item) in enumerate(zip(actual_value, expected_value)):
                if isinstance(exp_item, dict) and isinstance(act_item, dict):
                    assert_dict_matches(act_item, exp_item, f"{context}.{key}[{i}]")
                else:
                    assert act_item == exp_item, f"Item mismatch in list '{key}' at index {i}"
        else:
            assert actual_value == expected_value, \
                f"Value mismatch for '{key}' in {context}: expected {expected_value}, got {actual_value}"
