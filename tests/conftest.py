from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

for rel_path in ("src/rag", "src/governance", "src/hooks"):
    path = str(ROOT / rel_path)
    if path not in sys.path:
        sys.path.insert(0, path)
