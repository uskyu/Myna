import os
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.chdir(str(BACKEND))

runpy.run_path(str(BACKEND / "main.py"), run_name="__main__")
