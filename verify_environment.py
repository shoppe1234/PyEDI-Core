import sys
import importlib

required_packages = [
    ('badx12', 'badx12'),
    ('pandas', 'pandas'),
    ('yaml', 'pyyaml'),
    ('pydantic', 'pydantic'),
    ('structlog', 'structlog'),
    ('fastapi', 'fastapi'),  # Phase 3
    ('uvicorn', 'uvicorn'),  # Phase 3
]

print("Verifying Python environment...")
print(f"Python version: {sys.version}")

missing = []
for import_name, package_name in required_packages:
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, '__version__', 'unknown')
        print(f"✓ {package_name}: {version}")
    except ImportError:
        missing.append(package_name)
        print(f"✗ {package_name}: NOT FOUND")

if missing:
    print(f"\n⚠️  Missing packages: {', '.join(missing)}")
    sys.exit(1)
else:
    print("\n✓ All required packages installed")
