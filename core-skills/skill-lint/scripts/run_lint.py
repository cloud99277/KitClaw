#!/usr/bin/env python3
"""
Wrapper script for repository-wide skill linting.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_path = Path(__file__).resolve()
    scripts_dir = script_path.parent
    lint_script = scripts_dir / "lint_skills.py"
    if not lint_script.exists():
        skill_dir = scripts_dir.parent
        repo_root = skill_dir.parent
        lint_script = repo_root / ".system" / "skill-creator" / "scripts" / "lint_skills.py"

    if not lint_script.exists():
        print(f"[ERROR] lint_skills.py not found: {lint_script}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(lint_script), *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
