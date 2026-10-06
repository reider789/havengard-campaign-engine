#!/usr/bin/env python3
"""One regression entry point for local work and both workflows."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for path in sorted((root / "tests").glob("test_*.py")):
    print(path.name, flush=True)
    subprocess.run([sys.executable, str(path)], cwd=root, check=True)
subprocess.run([sys.executable, str(root / "tools/campaignctl.py"), "--project", str(root), "check-views"], check=True)
