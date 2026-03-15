#!/usr/bin/env python3
"""
memory-update.py — Write and manage L2 Whiteboard Memory entries

Handles initialization, incremental updates, and conflict detection.
Zero external dependencies — pure Python stdlib.

Usage:
    python3 memory-update.py --from-text "..." --type=decision --project=agent-os
    python3 memory-update.py --from-file conversation.md --project=agent-os
    python3 memory-update.py --list
    python3 memory-update.py --delete-project=_test
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"

AI_MEMORY_DIR = Path.home() / ".ai-memory"
WHITEBOARD_PATH = AI_MEMORY_DIR / "whiteboard.json"
CONFIG_PATH = AI_MEMORY_DIR / "config.json"

VALID_TYPES = {"decision", "action", "learning"}


# ─── Initialization ────────────────────────────────────────────────────────────

def ensure_initialized():
    """First-run initialization: create ~/.ai-memory/ and blank JSON files."""
    AI_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if not WHITEBOARD_PATH.exists():
        _write_json(WHITEBOARD_PATH, {
            "schema_version": "1.0",
            "last_updated": _now_iso(),
            "entries": []
        })
        print(f"✅ Initialized whiteboard: {WHITEBOARD_PATH}")

    if not CONFIG_PATH.exists():
        _write_json(CONFIG_PATH, {
            "schema_version": "1.0",
            "l3_paths": []
        })
        print(f"✅ Initialized config: {CONFIG_PATH}")


# ─── Core I/O ──────────────────────────────────────────────────────────────────

def _read_whiteboard():
    ensure_initialized()
    try:
        data = json.loads(WHITEBOARD_PATH.read_text(encoding="utf-8"))
        if not isinstance(data.get("entries"), list):
            data["entries"] = []
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ Error reading whiteboard: {e}", file=sys.stderr)
        sys.exit(1)


def _write_json(path, data):
    """Atomic JSON write: write to temp file then rename to prevent corruption."""
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    tmp.replace(path)  # atomic on POSIX


def _save_whiteboard(data):
    data["last_updated"] = _now_iso()
    _write_json(WHITEBOARD_PATH, data)


def _now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()


def _generate_id(entries):
    return f"wb-{len(entries) + 1:03d}-{uuid.uuid4().hex[:6]}"


# ─── Conflict Detection ────────────────────────────────────────────────────────

def _similarity(a, b):
    """Simple word overlap similarity (Jaccard) in [0, 1]."""
    a, b = a.lower(), b.lower()
    if not a or not b:
        return 0.0
    set_a, set_b = set(a.split()), set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / max(len(set_a), len(set_b))


def _check_duplicates(entries, new_content, threshold=0.8):
    """Return list of similar existing entries."""
    similar = []
    for entry in entries:
        sim = _similarity(new_content, entry.get("content", ""))
        if sim >= threshold:
            similar.append((sim, entry))
    return similar


# ─── Add Entry ────────────────────────────────────────────────────────────────

def add_entry(content, entry_type, project, tags=None, source_conversation=None, force=False):
    """Add a new entry to the whiteboard with conflict detection."""
    if entry_type not in VALID_TYPES:
        print(f"❌ Invalid type '{entry_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}")
        sys.exit(1)

    data = _read_whiteboard()
    entries = data["entries"]

    # Conflict detection
    if not force:
        similar = _check_duplicates(entries, content)
        if similar:
            print(f"⚠️  Found {len(similar)} similar existing entry(ies):")
            for sim, entry in similar:
                print(f"   [{sim:.0%}] [{entry['type']}] {entry['content'][:80]}")
            print("\nAdd anyway? [y/N]: ", end="", flush=True)
            answer = input().strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted.")
                return

    # Build new entry
    new_entry = {
        "id": _generate_id(entries),
        "type": entry_type,
        "content": content.strip(),
        "project": project or "",
        "tags": tags or [],
        "created_at": _now_iso(),
    }
    if source_conversation:
        new_entry["source_conversation"] = source_conversation

    entries.append(new_entry)
    _save_whiteboard(data)

    icon = {"decision": "🔵", "action": "🟡", "learning": "🟢"}.get(entry_type, "⚪")
    print(f"{icon} Added [{entry_type}]: {content[:80]}")
    print(f"   id={new_entry['id']} project={project}")


# ─── List Entries ──────────────────────────────────────────────────────────────

def list_entries(project=None, entry_type=None):
    """List whiteboard entries."""
    data = _read_whiteboard()
    entries = data["entries"]

    filtered = [
        e for e in entries
        if (not project or e.get("project") == project)
        and (not entry_type or e.get("type") == entry_type)
    ]

    if not filtered:
        qualifier = ""
        if project:
            qualifier += f" in project '{project}'"
        if entry_type:
            qualifier += f" of type '{entry_type}'"
        print(f"No entries{qualifier}.")
        return

    print(f"Whiteboard — {len(filtered)} entry(ies):\n")
    for entry in filtered:
        icon = {"decision": "🔵", "action": "🟡", "learning": "🟢"}.get(entry.get("type", ""), "⚪")
        print(f"  {icon} [{entry.get('type')}] {entry.get('content', '')}")
        print(f"     id={entry.get('id')} project={entry.get('project', '-')} tags={entry.get('tags', [])}")
        print(f"     created={entry.get('created_at', '-')[:19]}")
        print()


# ─── Delete by Project ────────────────────────────────────────────────────────

def delete_project(project):
    """Delete all entries for a given project (used for test cleanup)."""
    data = _read_whiteboard()
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e.get("project") != project]
    after = len(data["entries"])
    _save_whiteboard(data)
    removed = before - after
    print(f"🗑️  Deleted {removed} entry(ies) from project '{project}'.")


# ─── Extract from File ────────────────────────────────────────────────────────

def extract_from_file(filepath, project):
    """
    Agent-guided extraction: print the file content with extraction instructions.
    The Agent reads the file and calls add_entry for each identified D/A/L.
    """
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8", errors="replace")
    print("═" * 60)
    print("📋 MEMORY EXTRACTION REQUEST")
    print("═" * 60)
    print(f"Source: {filepath}")
    print(f"Project: {project}")
    print()
    print("Please identify Decisions, Actions, and Learnings from the content below.")
    print("For each, run:")
    print(f'  python3 memory-update.py --from-text "..." --type=decision|action|learning --project={project}')
    print()
    print("─" * 60)
    print(content[:3000])
    if len(content) > 3000:
        print(f"\n... [{len(content) - 3000} more characters — read the full file for complete extraction]")
    print("─" * 60)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Write and manage L2 Whiteboard Memory entries"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--from-text", metavar="TEXT", help="Add entry from inline text")
    group.add_argument("--from-file", metavar="FILE", help="Extract entries from a file (Agent-guided)")
    group.add_argument("--list", action="store_true", help="List existing entries")
    group.add_argument("--delete-project", metavar="PROJECT", help="Delete all entries for a project")
    group.add_argument("--init", action="store_true", help="Initialize ~/.ai-memory/ directory")

    parser.add_argument("--type", choices=list(VALID_TYPES), help="Entry type (required with --from-text)")
    parser.add_argument("--project", default="", help="Project tag for the entry")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--force", action="store_true", help="Skip duplicate check")
    parser.add_argument("--filter-project", help="Filter --list by project")
    parser.add_argument("--filter-type", choices=list(VALID_TYPES), help="Filter --list by type")
    parser.add_argument("--version", action="version", version=f"memory-update {VERSION}")

    args = parser.parse_args()

    # Init
    if args.init:
        ensure_initialized()
        print("✅ ~/.ai-memory/ is ready.")
        return

    # List
    if args.list:
        list_entries(project=args.filter_project, entry_type=args.filter_type)
        return

    # Delete project
    if args.delete_project:
        delete_project(args.delete_project)
        return

    # Add from text
    if args.from_text:
        if not args.type:
            print("❌ --type is required with --from-text (decision, action, or learning)")
            sys.exit(1)
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
        add_entry(
            content=args.from_text,
            entry_type=args.type,
            project=args.project,
            tags=tags,
            force=args.force,
        )
        return

    # Extract from file
    if args.from_file:
        extract_from_file(args.from_file, args.project)
        return


if __name__ == "__main__":
    main()
