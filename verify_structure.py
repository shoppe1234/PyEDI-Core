import os
import sys

print("Verifying PyEDI-Core directory structure...")

required_dirs = [
    "pyedi_core",
    "pyedi_core/core",
    "pyedi_core/drivers",
    "pyedi_core/schemas/source",
    "pyedi_core/schemas/compiled",
    "pyedi_core/rules",
    "tests",
    "tests/fixtures",
    "config",
    "inbound/csv/gfs_ca"
]

required_files = [
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
    "config/config.yaml"
]

missing_dirs = [d for d in required_dirs if not os.path.isdir(d)]
missing_files = [f for f in required_files if not os.path.isfile(f)]

if not missing_dirs and not missing_files:
    print("✓ Directory structure complete")
else:
    if missing_dirs:
        print(f"⚠️  Missing directories: {missing_dirs}")
    if missing_files:
        print(f"⚠️  Missing files: {missing_files}")
    sys.exit(1)
