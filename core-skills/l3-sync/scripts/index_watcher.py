#!/usr/bin/env python3
"""
l3-sync: Watch L3 knowledge base directories and auto-trigger incremental indexing.

Modes:
  --once    Single incremental index of all l3_paths, then exit
  --watch   Continuous filesystem watching with debounced re-indexing

Configuration: reads l3_paths from ~/.ai-memory/config.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Config ---

CONFIG_PATH = os.path.expanduser("~/.ai-memory/config.json")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_ENGINE = os.path.expanduser("~/projects/kitclaw/rag-engine/knowledge_index.py")
LOG_PATH = os.path.expanduser("~/.ai-skills/.logs/executions.jsonl")

DEBOUNCE_SECONDS = 5.0  # Batch changes within this window
POLL_INTERVAL = 2.0     # Polling fallback interval


def load_l3_paths() -> list[str]:
    """Load L3 paths from config."""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Config not found: {CONFIG_PATH}", file=sys.stderr)
        print("   Run: bash install.sh --with-rag", file=sys.stderr)
        sys.exit(1)

    with open(config_path := CONFIG_PATH, "r") as f:
        config = json.load(f)

    paths = config.get("l3_paths", [])
    if not paths:
        print("❌ No l3_paths configured in config.json", file=sys.stderr)
        sys.exit(1)

    # Expand ~ and resolve paths
    expanded = []
    for p in paths:
        expanded_path = os.path.expanduser(p)
        if os.path.isdir(expanded_path):
            expanded.append(expanded_path)
        else:
            print(f"⚠️  Path not found, skipping: {p}", file=sys.stderr)

    if not expanded:
        print("❌ No valid l3_paths found", file=sys.stderr)
        sys.exit(1)

    return expanded


def run_index(watch_dirs: list[str]) -> dict:
    """Run incremental index on specified directories."""
    if not os.path.exists(RAG_ENGINE):
        print(f"❌ RAG engine not found: {RAG_ENGINE}", file=sys.stderr)
        print("   Run: bash install.sh --with-rag", file=sys.stderr)
        sys.exit(1)

    results = {"timestamp": datetime.now().isoformat(), "dirs": [], "status": "success"}

    for watch_dir in watch_dirs:
        print(f"📦 Indexing: {watch_dir}")
        try:
            proc = subprocess.run(
                [sys.executable, RAG_ENGINE, "--update", watch_dir],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode == 0:
                print(f"   ✅ Done")
                results["dirs"].append({"path": watch_dir, "status": "success"})
            else:
                print(f"   ❌ Failed: {proc.stderr[:200]}")
                results["dirs"].append({"path": watch_dir, "status": "error", "error": proc.stderr[:200]})
                results["status"] = "partial"
        except subprocess.TimeoutExpired:
            print(f"   ⏰ Timeout (>300s)")
            results["dirs"].append({"path": watch_dir, "status": "timeout"})
            results["status"] = "partial"
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results["dirs"].append({"path": watch_dir, "status": "error", "error": str(e)})
            results["status"] = "partial"

    return results


def log_execution(results: dict):
    """Log to skill-observability."""
    log_dir = os.path.dirname(LOG_PATH)
    os.makedirs(log_dir, exist_ok=True)

    entry = {
        "timestamp": results["timestamp"],
        "skill": "l3-sync",
        "agent": "hermes",
        "status": results["status"],
        "notes": f"Indexed {len(results['dirs'])} dirs",
    }

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_latest_mtime(directory: str) -> float:
    """Get the latest modification time of any .md file in directory (recursive)."""
    latest = 0.0
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith((".md", ".markdown")):
                try:
                    mtime = os.path.getmtime(os.path.join(root, fname))
                    if mtime > latest:
                        latest = mtime
                except OSError:
                    pass
    return latest


def watch_with_inotify(watch_dirs: list[str]):
    """Watch using inotify_simple (preferred on Linux/WSL)."""
    try:
        from inotify_simple import INotify, IN_MODIFY, IN_CREATE, IN_DELETE, IN_MOVED_TO
    except ImportError:
        return None  # Fall through to polling

    inotify = INotify()
    watch_map = {}  # wd -> dir_path

    for watch_dir in watch_dirs:
        wd = inotify.add_watch(
            watch_dir,
            IN_MODIFY | IN_CREATE | IN_DELETE | IN_MOVED_TO,
            recursive=True,
        )
        watch_map[wd] = watch_dir
        print(f"👁️  Watching (inotify): {watch_dir}")

    pending_dirs = set()
    last_event_time = time.time()

    while True:
        # Read events with timeout
        events = inotify.read(timeout=int(DEBOUNCE_SECONDS * 1000))

        if events:
            for event in events:
                # Find which watch_dir this event belongs to
                for wd, dir_path in watch_map.items():
                    if event.wd == wd:
                        pending_dirs.add(dir_path)
                        break
            last_event_time = time.time()

        # Debounce: if no new events for DEBOUNCE_SECONDS and we have pending changes
        if pending_dirs and (time.time() - last_event_time) >= DEBOUNCE_SECONDS:
            dirs_to_index = list(pending_dirs)
            pending_dirs.clear()
            print(f"\n🔄 Changes detected in {len(dirs_to_index)} dir(s), indexing...")
            results = run_index(dirs_to_index)
            log_execution(results)


def watch_with_polling(watch_dirs: list[str]):
    """Fallback: poll mtime of .md files periodically."""
    print("ℹ️  Using polling mode (inotify not available)")

    last_mtimes = {}
    for watch_dir in watch_dirs:
        last_mtimes[watch_dir] = get_latest_mtime(watch_dir)
        print(f"👁️  Watching (poll): {watch_dir}")

    while True:
        time.sleep(POLL_INTERVAL)
        changed_dirs = []

        for watch_dir in watch_dirs:
            current_mtime = get_latest_mtime(watch_dir)
            if current_mtime > last_mtimes[watch_dir]:
                changed_dirs.append(watch_dir)
                last_mtimes[watch_dir] = current_mtime

        if changed_dirs:
            # Debounce: wait a bit more to batch changes
            time.sleep(DEBOUNCE_SECONDS)
            # Re-check mtimes after debounce
            for watch_dir in changed_dirs:
                last_mtimes[watch_dir] = get_latest_mtime(watch_dir)

            print(f"\n🔄 Changes detected in {len(changed_dirs)} dir(s), indexing...")
            results = run_index(changed_dirs)
            log_execution(results)


def watch(watch_dirs: list[str]):
    """Start watching directories for changes."""
    print(f"🚀 l3-sync watching {len(watch_dirs)} directory(ies)")
    print(f"   Debounce: {DEBOUNCE_SECONDS}s")
    print(f"   Press Ctrl+C to stop\n")

    # Try inotify first, fall back to polling
    try:
        watch_with_inotify(watch_dirs)
    except Exception:
        watch_with_polling(watch_dirs)


def main():
    parser = argparse.ArgumentParser(description="L3 Knowledge Base Auto-Indexer")
    parser.add_argument("--once", action="store_true", help="Single incremental index, then exit")
    parser.add_argument("--watch", action="store_true", help="Continuous filesystem watching")
    args = parser.parse_args()

    watch_dirs = load_l3_paths()

    if args.once:
        print(f"📦 Single index of {len(watch_dirs)} dir(s)\n")
        results = run_index(watch_dirs)
        log_execution(results)
        if results["status"] != "success":
            sys.exit(1)
    elif args.watch:
        try:
            watch(watch_dirs)
        except KeyboardInterrupt:
            print("\n🛑 Stopped")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
