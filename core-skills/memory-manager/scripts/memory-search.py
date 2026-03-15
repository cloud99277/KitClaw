#!/usr/bin/env python3
"""
memory-search.py — Cross-layer memory search for memory-manager skill

Searches L1 (Identity), L2 (Whiteboard/Session), L3 (Knowledge) layers.
Zero external dependencies — pure Python stdlib + subprocess grep.

Usage:
    python3 memory-search.py "keyword"
    python3 memory-search.py "keyword" --layer=L2
    python3 memory-search.py "keyword" --project=agent-os
    python3 memory-search.py "keyword" --scope=dev
    python3 memory-search.py "keyword" --json
"""

import argparse
import json
import subprocess
from pathlib import Path

VERSION = "1.1.0"

# ─── L1 Identity Layer paths ──────────────────────────────────────────────────
L1_PATHS = [
    Path.home() / ".claude" / "CLAUDE.md",
    Path.home() / ".gemini" / "GEMINI.md",
    Path.home() / ".codex" / "AGENTS.md",
    Path.home() / ".agents" / "AGENTS.md",
]

AI_MEMORY_DIR = Path.home() / ".ai-memory"
WHITEBOARD_PATH = AI_MEMORY_DIR / "whiteboard.json"
CONFIG_PATH = AI_MEMORY_DIR / "config.json"

# ─── Scope definitions (Phase 8: domain-based search) ────────────────────────
# Each scope maps to a list of L3 search paths.
# These override config.json l3_paths when --scope is specified.
# To customize, modify the paths below to match your directory structure.
SCOPE_DEFINITIONS = {
    "dev": [
        str(Path.home() / ".ai-skills"),
        str(Path.home() / "projects"),
    ],
    "content": [
        str(Path.home() / "content"),
        str(Path.home() / ".openclaw" / "workspace"),
    ],
    "personal": [
        str(Path.home() / ".openclaw" / "workspace"),
    ],
}


def load_config():
    """Load ~/.ai-memory/config.json, return empty config if not found."""
    if not CONFIG_PATH.exists():
        return {"schema_version": "1.0", "l3_paths": []}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": "1.0", "l3_paths": []}


def search_l1(keyword, as_json=False):
    """Search L1 Identity Layer files."""
    results = []
    for path in L1_PATHS:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            matches = []
            for i, line in enumerate(content.splitlines(), 1):
                if keyword.lower() in line.lower():
                    matches.append({"line": i, "content": line.strip()})
            if matches:
                results.append({"file": str(path), "matches": matches})
        except OSError:
            continue

    if as_json:
        return {"layer": "L1", "status": "ok", "results": results}

    if not results:
        print(f"L1: no matches for '{keyword}'")
        return None

    print(f"L1 (Identity Layer) — {sum(len(r['matches']) for r in results)} match(es):")
    for r in results:
        print(f"  📄 {r['file']}")
        for m in r["matches"]:
            print(f"    L{m['line']}: {m['content']}")
    return results


def search_l2(keyword, project=None, as_json=False):
    """Search L2 Session Layer (whiteboard.json)."""
    if not WHITEBOARD_PATH.exists():
        msg = "L2: skipped (whiteboard not initialized — run memory-update.py first)"
        if as_json:
            return {"layer": "L2", "status": "skipped", "reason": "whiteboard not initialized", "results": []}
        print(msg)
        return None

    try:
        data = json.loads(WHITEBOARD_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        msg = f"L2: error reading whiteboard ({e})"
        if as_json:
            return {"layer": "L2", "status": "error", "reason": str(e), "results": []}
        print(msg)
        return None

    entries = data.get("entries", [])
    matches = []
    for entry in entries:
        if project and entry.get("project") != project:
            continue
        kw = keyword.lower()
        searchable = " ".join([
            entry.get("content", ""),
            entry.get("project", ""),
            " ".join(entry.get("tags", [])),
        ]).lower()
        if kw in searchable:
            matches.append(entry)

    if as_json:
        return {"layer": "L2", "status": "ok", "results": matches}

    if not matches:
        print(f"L2: no matches for '{keyword}'" + (f" in project '{project}'" if project else ""))
        return None

    print(f"L2 (Whiteboard) — {len(matches)} match(es):")
    for entry in matches:
        icon = {"decision": "🔵", "action": "🟡", "learning": "🟢"}.get(entry.get("type", ""), "⚪")
        print(f"  {icon} [{entry.get('type', '?')}] {entry.get('content', '')}")
        print(f"     project={entry.get('project', '-')} tags={entry.get('tags', [])}")
    return matches


def search_l3(keyword, as_json=False, scope_paths=None):
    """Search L3 Knowledge Layer via grep.

    Args:
        scope_paths: If provided, overrides config.json l3_paths (Phase 8 scope feature).
    """
    if scope_paths is not None:
        l3_paths = scope_paths
    else:
        config = load_config()
        l3_paths = config.get("l3_paths", [])

    if not l3_paths:
        msg = "L3: skipped (no search paths — configure ~/.ai-memory/config.json or use --scope)"
        if as_json:
            return {"layer": "L3", "status": "skipped", "reason": "no l3_paths configured", "results": []}
        print(msg)
        return None

    all_results = []
    for raw_path in l3_paths:
        p = Path(raw_path).expanduser()
        if not p.exists():
            skip_msg = f"L3: skipped (path not found: {p})"
            if not as_json:
                print(skip_msg)
            continue

        try:
            result = subprocess.run(
                ["grep", "-rniF", "--include=*.md", keyword, str(p)],
                capture_output=True, text=True, timeout=10
            )
            if result.stdout:
                lines = result.stdout.strip().splitlines()
                all_results.extend(lines)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    scope_label = " [scoped]" if scope_paths is not None else ""

    if as_json:
        result = {"layer": "L3", "status": "ok", "results": all_results}
        if scope_paths is not None:
            result["scope_paths"] = scope_paths
        return result

    if not all_results:
        print(f"L3: no matches for '{keyword}'{scope_label}")
        return None

    print(f"L3 (Knowledge Layer){scope_label} — {len(all_results)} match(es):")
    for line in all_results[:20]:  # cap display at 20
        print(f"  {line}")
    if len(all_results) > 20:
        print(f"  ... and {len(all_results) - 20} more")
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Search cross-layer memory (L1/L2/L3)"
    )
    parser.add_argument("keyword", help="Search keyword")
    parser.add_argument("--layer", choices=["L1", "L2", "L3"], help="Restrict to specific layer")
    parser.add_argument("--project", help="Filter L2 by project name")
    parser.add_argument("--scope", choices=list(SCOPE_DEFINITIONS.keys()),
                        help="Restrict L3 search to a predefined domain (dev/content/personal)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    parser.add_argument("--version", action="version", version=f"memory-search {VERSION}")
    args = parser.parse_args()

    if not args.keyword.strip():
        parser.error("keyword must not be empty")

    layers_to_search = [args.layer] if args.layer else ["L1", "L2", "L3"]

    # Resolve scope paths (Phase 8)
    scope_paths = SCOPE_DEFINITIONS.get(args.scope) if args.scope else None

    if args.as_json:
        output = {"keyword": args.keyword, "layers": []}
        if args.scope:
            output["scope"] = args.scope
        for layer in layers_to_search:
            if layer == "L1":
                output["layers"].append(search_l1(args.keyword, as_json=True))
            elif layer == "L2":
                output["layers"].append(search_l2(args.keyword, project=args.project, as_json=True))
            elif layer == "L3":
                output["layers"].append(search_l3(args.keyword, as_json=True, scope_paths=scope_paths))
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        for layer in layers_to_search:
            if layer == "L1":
                search_l1(args.keyword)
            elif layer == "L2":
                search_l2(args.keyword, project=args.project)
            elif layer == "L3":
                search_l3(args.keyword, scope_paths=scope_paths)


if __name__ == "__main__":
    main()
