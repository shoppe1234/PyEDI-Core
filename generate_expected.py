import json
import shutil
import os
import yaml
from pathlib import Path
from pyedi_core import Pipeline

pipeline = Pipeline(config_path='./config/config.yaml')

# Load metadata.yaml
with open('./tests/user_supplied/metadata.yaml', 'r') as f:
    config = yaml.safe_load(f)

for case in config.get("test_cases", []):
    input_rel_path = case["input_file"]
    expected_rel_path = case["expected_output"]
    target_inbound_dir = Path(case["target_inbound_dir"])
    
    # Copy from tests/user_supplied to inbound
    source_file = Path("tests/user_supplied") / input_rel_path
    if not source_file.exists():
        # Fallback to current directory for UnivT701 edge cases
        source_file = Path(source_file.name)
        
    target_inbound_dir.mkdir(parents=True, exist_ok=True)
    input_file = target_inbound_dir / source_file.name
    shutil.copy(source_file, input_file)
    
    try:
        result = pipeline.run(file=str(input_file), return_payload=True, dry_run=True)
        if result.status == 'SUCCESS':
            out_path = Path('tests/user_supplied') / expected_rel_path
            with open(out_path, 'w') as f:
                json.dump(result.payload, f, indent=2)
            print(f"Successfully generated {out_path}.")
        else:
            print(f"Pipeline failed for {input_file}: {result.errors}")
    finally:
        if input_file.exists():
            os.remove(input_file)
