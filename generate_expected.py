import json
from pathlib import Path
from pyedi_core import Pipeline

pipeline = Pipeline(config_path='./config/config.yaml')

# We need to copy it to the required inbound directory to satisfy PCR-2025-002
import shutil
import os
target_dir = Path('./inbound/csv/gfs_ca')
target_dir.mkdir(parents=True, exist_ok=True)
input_file = target_dir / "UnivT701_small.csv"
shutil.copy("UnivT701_small.csv", input_file)

try:
    result = pipeline.run(file=str(input_file), return_payload=True, dry_run=True)
    if result.status == 'SUCCESS':
        out_path = Path('tests/user_supplied/expected_outputs/UnivT701_small.json')
        with open(out_path, 'w') as f:
            json.dump(result.payload, f, indent=2)
        print("Successfully generated expected output.")
    else:
        print(f"Pipeline failed: {result.errors}")
finally:
    if input_file.exists():
        os.remove(input_file)
