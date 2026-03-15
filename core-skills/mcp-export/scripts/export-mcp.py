#!/usr/bin/env python3
"""Export KitClaw SKILL.md frontmatter to MCP-compatible JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MCP_SPEC_VERSION = "2025-03-26"
SCHEMA_VERSION = "1.0"
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_SKILLS_DIR = REPO_ROOT / "core-skills"

SKIP_DIRS = {
    ".git",
    ".logs",
    ".system",
    "__pycache__",
    ".archive",
    ".backup",
    ".deprecated",
}

IO_TYPE_TO_JSON_SCHEMA: dict[str, dict[str, Any]] = {
    "text": {"type": "string"},
    "markdown_file": {"type": "string", "description": "Path to a Markdown file"},
    "json_data": {"type": "string", "description": "JSON file path or inline JSON string"},
    "directory": {"type": "string", "description": "Directory path"},
    "url": {"type": "string", "format": "uri"},
}


def parse_frontmatter(skill_md_path: Path) -> dict[str, Any] | None:
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    lines = match.group(1).splitlines()
    result: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue

        top_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)", line)
        if not top_match:
            index += 1
            continue

        key = top_match.group(1).strip()
        value = top_match.group(2).strip()

        if key == "io":
            io_decl, index = parse_io_block(lines, index + 1)
            result["io"] = io_decl
            continue

        if value in (">", "|"):
            block_value, index = parse_block_scalar(lines, index + 1, value)
            result[key] = block_value
            continue

        result[key] = clean_value(value)
        index += 1

    return result


def parse_block_scalar(lines: list[str], start: int, style: str) -> tuple[str, int]:
    block_lines: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            if style == "|":
                block_lines.append("")
                index += 1
                continue
            break
        if line[0] in (" ", "\t"):
            block_lines.append(line.strip())
            index += 1
            continue
        break

    if style == ">":
        return " ".join(block_lines), index
    return "\n".join(block_lines), index


def parse_io_block(lines: list[str], start: int) -> tuple[dict[str, list[dict[str, str]]], int]:
    io: dict[str, list[dict[str, str]]] = {"input": [], "output": []}
    current_section: str | None = None
    current_item: dict[str, str] | None = None
    index = start

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0 and stripped and not stripped.startswith("#"):
            break

        section_match = re.match(r"^(input|output)\s*:", stripped)
        if section_match:
            if current_item is not None and current_section is not None:
                io[current_section].append(current_item)
            current_section = section_match.group(1)
            current_item = None
            index += 1
            continue

        item_match = re.match(r"^-\s+(\w[\w_-]*)\s*:\s*(.*)", stripped)
        if item_match and current_section:
            if current_item is not None:
                io[current_section].append(current_item)
            current_item = {item_match.group(1): clean_value(item_match.group(2))}
            index += 1
            continue

        cont_match = re.match(r"^(\w[\w_-]*)\s*:\s*(.*)", stripped)
        if cont_match and current_item is not None:
            current_item[cont_match.group(1)] = clean_value(cont_match.group(2))
            index += 1
            continue

        index += 1

    if current_item is not None and current_section is not None:
        io[current_section].append(current_item)

    return io, index


def clean_value(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        return cleaned[1:-1]
    return cleaned


def discover_skills(
    skills_dir: Path,
    filter_names: set[str] | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    if not skills_dir.is_dir():
        print(f"Error: skills directory not found: {skills_dir}", file=sys.stderr)
        return []

    skills: list[tuple[Path, dict[str, Any]]] = []
    for entry in sorted(skills_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        frontmatter = parse_frontmatter(skill_md)
        if frontmatter is None or "name" not in frontmatter:
            continue
        if filter_names and frontmatter["name"] not in filter_names:
            continue
        skills.append((entry, frontmatter))
    return skills


def build_input_schema(io_decl: dict[str, list[dict[str, str]]] | None) -> dict[str, Any]:
    if not io_decl or not io_decl.get("input"):
        return {"type": "object"}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for index, item in enumerate(io_decl["input"]):
        io_type = item.get("type", "text")
        description = item.get("description", "")
        prop_name = f"input_{index}_{io_type}"
        schema = dict(IO_TYPE_TO_JSON_SCHEMA.get(io_type, {"type": "string"}))
        if description:
            schema["description"] = description
        properties[prop_name] = schema
        is_required = item.get("required", "true").lower()
        if is_required not in {"false", "no", "0"}:
            required.append(prop_name)

    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def build_annotations(name: str, skill_dir: Path) -> dict[str, Any]:
    return {
        "title": name.replace("-", " ").title(),
        "readOnlyHint": not (skill_dir / "scripts").is_dir(),
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def skill_to_tool(skill_dir: Path, frontmatter: dict[str, Any]) -> dict[str, Any]:
    name = str(frontmatter.get("name", skill_dir.name))
    description = str(frontmatter.get("description", "")).strip()
    return {
        "name": name,
        "description": description,
        "inputSchema": build_input_schema(frontmatter.get("io")),
        "annotations": build_annotations(name, skill_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export SKILL.md frontmatter to MCP-compatible tool JSON"
    )
    parser.add_argument(
        "--skills-dir",
        default=str(DEFAULT_SKILLS_DIR),
        help=f"Skills directory to scan (default: {DEFAULT_SKILLS_DIR})",
    )
    parser.add_argument("--output", "-o", help="Write JSON output to a file")
    parser.add_argument(
        "--skill",
        action="append",
        default=None,
        help="Export only the specified skill name. Can be repeated.",
    )
    parser.add_argument("--stats", action="store_true", help="Print summary stats only")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCHEMA_VERSION} (MCP {MCP_SPEC_VERSION})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skills_dir = Path(args.skills_dir).expanduser().resolve()
    filter_names = set(args.skill) if args.skill else None
    skills = discover_skills(skills_dir, filter_names)
    if not skills:
        print("No skills found.", file=sys.stderr)
        return 1

    with_io = 0
    tools: list[dict[str, Any]] = []
    for skill_dir, frontmatter in skills:
        if frontmatter.get("io"):
            with_io += 1
        tools.append(skill_to_tool(skill_dir, frontmatter))

    if args.stats:
        print(f"Skills directory: {skills_dir}")
        print(f"Total skills discovered: {len(skills)}")
        print(f"With IO declarations: {with_io}")
        print(f"Without IO declarations: {len(skills) - with_io}")
        print(f"Tools exported: {len(tools)}")
        return 0

    document = {
        "schema_version": SCHEMA_VERSION,
        "mcp_spec_version": MCP_SPEC_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "skills_dir": str(skills_dir),
        "stats": {
            "total_skills": len(skills),
            "with_io": with_io,
            "exported": len(tools),
        },
        "tools": tools,
    }

    payload = json.dumps(document, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
        print(f"Exported {len(tools)} tools to {output_path}", file=sys.stderr)
        return 0

    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
