#!/usr/bin/env python3
"""
watch-knowledge-base.py

Poll a knowledge root for Markdown changes and trigger:
1. frontmatter completion for missing metadata
2. incremental knowledge-search reindex

This stays stdlib-only so it can run in WSL/Linux without extra packages.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


_SCRIPT_DIR = Path(__file__).resolve().parent
_KITCLAW_DIR = _SCRIPT_DIR.parent.parent.parent  # core-skills/memory-manager/scripts/ → kitclaw/

DEFAULT_ROOT = str(Path.home() / "knowledge-base")
DEFAULT_FRONTMATTER_SCRIPT = str(_SCRIPT_DIR / "ensure-knowledge-frontmatter.py")
DEFAULT_INDEXER_PYTHON = str(_KITCLAW_DIR / "rag-engine" / ".venv" / "bin" / "python3")
DEFAULT_INDEXER_SCRIPT = str(_KITCLAW_DIR / "rag-engine" / "knowledge_index.py")
DEFAULT_DB_PATH = str(Path.home() / ".lancedb" / "knowledge")
WATCH_LABEL = "kitclaw-l3-watch"

STOP_REQUESTED = False


def handle_signal(signum, _frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"[{WATCH_LABEL}] received signal {signum}, shutting down...", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch the knowledge root and auto-run frontmatter completion plus incremental indexing."
    )
    parser.add_argument("--root", default=DEFAULT_ROOT, help=f"Knowledge root (default: {DEFAULT_ROOT})")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (default: 2)")
    parser.add_argument("--debounce", type=float, default=3.0, help="Quiet period before ingest (default: 3)")
    parser.add_argument(
        "--frontmatter-script",
        default=DEFAULT_FRONTMATTER_SCRIPT,
        help=f"Frontmatter completion script (default: {DEFAULT_FRONTMATTER_SCRIPT})",
    )
    parser.add_argument(
        "--indexer-python",
        default=DEFAULT_INDEXER_PYTHON,
        help=f"Python executable for indexer (default: {DEFAULT_INDEXER_PYTHON})",
    )
    parser.add_argument(
        "--indexer-script",
        default=DEFAULT_INDEXER_SCRIPT,
        help=f"Indexer script path (default: {DEFAULT_INDEXER_SCRIPT})",
    )
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help=f"LanceDB path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--no-initial-sync", action="store_true", help="Skip the startup sync run")
    parser.add_argument("--once", action="store_true", help="Run one ingest cycle and exit")
    return parser.parse_args()


def validate_paths(args: argparse.Namespace) -> Path:
    root = Path(args.root).expanduser()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Error: knowledge root not found: {root}")

    missing = [
        path
        for path in [args.frontmatter_script, args.indexer_python, args.indexer_script]
        if not Path(path).expanduser().exists()
    ]
    if missing:
        raise SystemExit(f"Error: required path(s) not found: {', '.join(missing)}")

    return root


def build_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        stat = path.stat()
        snapshot[str(path.relative_to(root))] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def diff_snapshots(
    previous: dict[str, tuple[int, int]],
    current: dict[str, tuple[int, int]],
) -> tuple[list[str], list[str], list[str]]:
    previous_keys = set(previous)
    current_keys = set(current)
    created = sorted(current_keys - previous_keys)
    deleted = sorted(previous_keys - current_keys)
    modified = sorted(
        path for path in (previous_keys & current_keys) if previous[path] != current[path]
    )
    return created, modified, deleted


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)


def run_ingest(root: Path, args: argparse.Namespace, reason: str) -> bool:
    print(f"[{WATCH_LABEL}] ingest start ({reason})", flush=True)

    frontmatter_cmd = [
        sys.executable,
        str(Path(args.frontmatter_script).expanduser()),
        "--root",
        str(root),
        "--apply",
    ]
    frontmatter_result = run_command(frontmatter_cmd)
    if frontmatter_result.returncode != 0:
        print(f"[{WATCH_LABEL}] frontmatter step failed", file=sys.stderr, flush=True)
        if frontmatter_result.stdout.strip():
            print(frontmatter_result.stdout.strip(), file=sys.stderr, flush=True)
        if frontmatter_result.stderr.strip():
            print(frontmatter_result.stderr.strip(), file=sys.stderr, flush=True)
        return False

    env = os.environ.copy()
    env["PRODUCTION"] = "true"
    index_cmd = [
        str(Path(args.indexer_python).expanduser()),
        str(Path(args.indexer_script).expanduser()),
        "--update",
        str(root),
        "--db-path",
        str(Path(args.db_path).expanduser()),
    ]
    index_result = run_command(index_cmd, env=env)
    if index_result.returncode != 0:
        print(f"[{WATCH_LABEL}] index step failed", file=sys.stderr, flush=True)
        if index_result.stdout.strip():
            print(index_result.stdout.strip(), file=sys.stderr, flush=True)
        if index_result.stderr.strip():
            print(index_result.stderr.strip(), file=sys.stderr, flush=True)
        return False

    print(f"[{WATCH_LABEL}] ingest complete", flush=True)
    return True


def watch(root: Path, args: argparse.Namespace) -> int:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if not args.no_initial_sync:
        run_ingest(root, args, reason="initial_sync")
        if args.once:
            return 0
    elif args.once:
        return 0

    previous = build_snapshot(root)
    pending = False
    pending_since = 0.0
    pending_created: set[str] = set()
    pending_modified: set[str] = set()
    pending_deleted: set[str] = set()

    print(
        f"[{WATCH_LABEL}] watching {root} (interval={args.interval}s, debounce={args.debounce}s)",
        flush=True,
    )

    while not STOP_REQUESTED:
        time.sleep(args.interval)
        current = build_snapshot(root)
        created, modified, deleted = diff_snapshots(previous, current)
        previous = current

        if created or modified or deleted:
            pending = True
            pending_since = time.monotonic()
            pending_created.update(created)
            pending_modified.update(modified)
            pending_deleted.update(deleted)
            print(
                f"[{WATCH_LABEL}] change detected: "
                f"{len(created)} created, {len(modified)} modified, {len(deleted)} deleted",
                flush=True,
            )
            continue

        if pending and (time.monotonic() - pending_since) >= args.debounce:
            summary = (
                f"{len(pending_created)} created, "
                f"{len(pending_modified)} modified, "
                f"{len(pending_deleted)} deleted"
            )
            run_ingest(root, args, reason=summary)
            previous = build_snapshot(root)
            pending = False
            pending_created.clear()
            pending_modified.clear()
            pending_deleted.clear()

    print(f"[{WATCH_LABEL}] stopped", flush=True)
    return 0


def main() -> int:
    args = parse_args()
    root = validate_paths(args)
    return watch(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
