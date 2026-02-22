import json
from pathlib import Path
from pyedi_core import Pipeline
import shutil
import os

pipeline = Pipeline(config_path='./config/config.yaml')

target_dir = Path('./inbound/csv/margin_edge')
target_dir.mkdir(parents=True, exist_ok=True)
input_file = target_dir / "NA_810_MARGINEDGE_20260129.txt"
shutil.copy("tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt", input_file)

try:
    result = pipeline.run(file=str(input_file), return_payload=True, dry_run=True)
    if result.status == 'SUCCESS':
        out_path = Path('tests/user_supplied/expected_outputs/NA_810_MARGINEDGE_20260129.json')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(result.payload, f, indent=2)
        print("Successfully generated expected output.")
    else:
        print(f"Pipeline failed: {result.errors}")
finally:
    if input_file.exists():
        os.remove(input_file)
