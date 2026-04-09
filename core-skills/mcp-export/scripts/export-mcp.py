#!/usr/bin/env python3
"""
export-mcp.py — SKILL.md frontmatter → MCP Tool JSON 导出

将 Agent Toolchain 的 SKILL.md frontmatter 导出为符合 MCP 2025-03-26 规范的
Tool JSON schema。只做导出，不做 MCP Server 运行时。

用法:
    python3 export-mcp.py                          # 导出全部到 stdout
    python3 export-mcp.py --output tools.json      # 导出到文件
    python3 export-mcp.py --skill translate         # 仅导出指定 skill
    python3 export-mcp.py --stats                  # 仅输出统计
    python3 export-mcp.py --pretty                 # Pretty-print JSON

零外部依赖：仅使用 Python stdlib。
"""

import argparse
import datetime
import json
import os
import re
import sys

# ─── Constants ───────────────────────────────────────────────────────────────

MCP_SPEC_VERSION = "2025-03-26"
SCHEMA_VERSION = "1.0"

# Default skills directory
DEFAULT_SKILLS_DIR = os.path.expanduser("~/.ai-skills")

# Type registry path (reserved for future dynamic loading)
# Current version uses hardcoded IO_TYPE_TO_JSON_SCHEMA below.
# TODO: Read type-registry.json dynamically when new types are added frequently.
TYPE_REGISTRY_REL = ".system/io-contracts/type-registry.json"

# Directories to skip when scanning skills
SKIP_DIRS = {
    ".system", ".logs", ".git", "__pycache__",
    ".archive", ".deprecated", ".backup"
}

# IO type → JSON Schema mapping (hardcoded, synced with type-registry.json v1.0)
# Kept in sync manually. If type-registry.json adds new types, update here.
IO_TYPE_TO_JSON_SCHEMA = {
    "text": {"type": "string"},
    "markdown_file": {"type": "string", "description": "Path to Markdown file (.md)"},
    "url": {"type": "string", "format": "uri"},
    "image_file": {"type": "string", "description": "Path to image file (.png/.jpg/.webp)"},
    "json_data": {"type": "string", "description": "Path to JSON file or inline JSON string"},
    "html_file": {"type": "string", "description": "Path to HTML file (.html)"},
    "directory": {"type": "string", "description": "Path to directory"},
}


# ─── Frontmatter Parser ─────────────────────────────────────────────────────

def parse_frontmatter(skill_md_path):
    """Parse SKILL.md frontmatter (YAML subset between --- markers).

    Supports:
    - key: value (simple)
    - key: > or key: | (multi-line folded/literal blocks)
    - io: nested structure (input/output lists with - type/description/required)

    Returns dict with parsed frontmatter fields.
    """
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return None

    # Extract frontmatter between --- markers
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None

    fm_text = match.group(1)
    lines = fm_text.split('\n')

    result = {}
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines and comment lines
        if not line.strip() or line.strip().startswith('#'):
            i += 1
            continue

        # Check for top-level key: value
        top_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)', line)
        if not top_match:
            i += 1
            continue

        key = top_match.group(1).strip()
        value = top_match.group(2).strip()

        if key == 'io':
            # Parse nested io structure
            result['io'], i = _parse_io_block(lines, i + 1)
        elif value in ('>', '|'):
            # Multi-line block scalar
            block_style = value
            i += 1
            block_lines = []
            while i < len(lines):
                if not lines[i].strip():
                    # Empty line: include for literal, end for folded
                    if block_style == '|':
                        block_lines.append('')
                    i += 1
                    if block_style == '>':
                        break
                    continue
                # Check indentation — block continues while indented
                if lines[i][0] in (' ', '\t'):
                    block_lines.append(lines[i].strip())
                    i += 1
                else:
                    break

            if block_style == '>':
                # Folded: join with spaces
                result[key] = ' '.join(block_lines)
            else:
                # Literal: join with newlines
                result[key] = '\n'.join(block_lines)
        elif value:
            # Simple key: value
            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            result[key] = value
            i += 1
        else:
            i += 1

    return result


def _parse_io_block(lines, start_idx):
    """Parse the io: block with nested input/output lists.

    Expected structure:
        io:
          input:
            - type: markdown_file
              description: ...
              required: false
            - type: url
              description: ...
          output:
            - type: markdown_file
              description: ...
              path_pattern: ...

    Returns (io_dict, next_line_index)
    """
    io = {"input": [], "output": []}
    i = start_idx
    current_section = None  # 'input' or 'output'
    current_item = None

    while i < len(lines):
        line = lines[i]

        # Empty line
        if not line.strip():
            i += 1
            continue

        # Calculate indentation
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Non-indented line = end of io block
        if indent == 0 and stripped and not stripped.startswith('#'):
            break

        # input: or output: section header (typically 2-space indent)
        section_match = re.match(r'^(input|output)\s*:', stripped)
        if section_match:
            # Save pending item from previous section
            if current_item is not None and current_section is not None:
                io[current_section].append(current_item)
            current_section = section_match.group(1)
            current_item = None
            i += 1
            continue

        # List item start: - type: xxx
        item_match = re.match(r'^-\s+(\w+)\s*:\s*(.*)', stripped)
        if item_match and current_section:
            # Save previous item
            if current_item is not None:
                io[current_section].append(current_item)
            current_item = {item_match.group(1): _clean_value(item_match.group(2))}
            i += 1
            continue

        # Continuation of current item: key: value (indented, no -)
        cont_match = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', stripped)
        if cont_match and current_item is not None:
            k = cont_match.group(1)
            v = _clean_value(cont_match.group(2))
            current_item[k] = v
            i += 1
            continue

        i += 1

    # Save last item
    if current_item is not None and current_section is not None:
        io[current_section].append(current_item)

    return io, i


def _clean_value(v):
    """Strip quotes and whitespace from a parsed value."""
    v = v.strip()
    if not v:
        return v
    if (v.startswith('"') and v.endswith('"')) or \
       (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v


# ─── MCP Tool Generation ────────────────────────────────────────────────────

def skill_to_mcp_tool(skill_dir, frontmatter):
    """Convert a parsed SKILL.md frontmatter to an MCP Tool JSON object."""
    name = frontmatter.get("name", os.path.basename(skill_dir))
    description = frontmatter.get("description", "")

    # Build inputSchema from io declarations
    input_schema = _build_input_schema(frontmatter.get("io"))

    # Build annotations
    annotations = _build_annotations(name, skill_dir)

    tool = {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "annotations": annotations,
    }

    return tool


def _build_input_schema(io_decl):
    """Build MCP inputSchema from io declaration.

    If io has input declarations, map each to a JSON Schema property.
    If no io, return minimal {"type": "object"}.
    """
    if not io_decl or not io_decl.get("input"):
        return {"type": "object"}

    properties = {}
    required = []

    for idx, inp in enumerate(io_decl["input"]):
        io_type = inp.get("type", "text")
        desc = inp.get("description", "")

        # Generate property name: input_{index}_{type}
        prop_name = f"input_{idx}_{io_type}"

        # Map IO type to JSON Schema
        schema = dict(IO_TYPE_TO_JSON_SCHEMA.get(io_type, {"type": "string"}))

        # Override description with io-specific description if present
        if desc:
            schema["description"] = desc

        properties[prop_name] = schema

        # Determine required status (default: true)
        is_required = inp.get("required", "true")
        if str(is_required).lower() not in ("false", "no", "0"):
            required.append(prop_name)

    result = {"type": "object", "properties": properties}
    if required:
        result["required"] = required

    return result


def _build_annotations(name, skill_dir):
    """Build MCP tool annotations based on skill metadata."""
    # Title: kebab-case → Title Case
    title = name.replace("-", " ").title()

    # readOnlyHint: has scripts/ → not read-only
    scripts_dir = os.path.join(skill_dir, "scripts")
    has_scripts = os.path.isdir(scripts_dir)

    return {
        "title": title,
        "readOnlyHint": not has_scripts,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }


# ─── Skill Discovery ────────────────────────────────────────────────────────

def discover_skills(skills_dir, filter_names=None):
    """Discover all skills with valid SKILL.md in the skills directory.

    Args:
        skills_dir: Root skills directory (e.g. ~/.ai-skills/)
        filter_names: Optional set of skill names to include (None = all)

    Returns:
        List of (skill_dir_path, frontmatter_dict) tuples.
    """
    results = []

    if not os.path.isdir(skills_dir):
        print(f"Error: Skills directory not found: {skills_dir}", file=sys.stderr)
        return results

    for entry in sorted(os.listdir(skills_dir)):
        # Skip hidden dirs and known non-skill dirs
        if entry.startswith('.') or entry in SKIP_DIRS:
            continue

        skill_dir = os.path.join(skills_dir, entry)
        if not os.path.isdir(skill_dir):
            continue

        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue

        # Parse frontmatter
        fm = parse_frontmatter(skill_md)
        if fm is None or "name" not in fm:
            continue

        # Apply filter
        if filter_names and fm["name"] not in filter_names:
            continue

        results.append((skill_dir, fm))

    return results


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Export SKILL.md frontmatter to MCP Tool JSON schema"
    )
    parser.add_argument(
        "--skills-dir", default=DEFAULT_SKILLS_DIR,
        help=f"Skills directory (default: {DEFAULT_SKILLS_DIR})"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--skill", action="append", default=None,
        help="Export only specified skill(s) (can repeat)"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show statistics only, don't output JSON"
    )
    parser.add_argument(
        "--pretty", action="store_true",
        help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    skills_dir = os.path.expanduser(args.skills_dir)
    filter_names = set(args.skill) if args.skill else None

    # Discover skills
    skills = discover_skills(skills_dir, filter_names)

    if not skills:
        print("No skills found.", file=sys.stderr)
        sys.exit(1)

    # Convert to MCP tools
    tools = []
    with_io_count = 0

    for skill_dir, fm in skills:
        tool = skill_to_mcp_tool(skill_dir, fm)
        tools.append(tool)
        if fm.get("io"):
            with_io_count += 1

    # Stats mode
    if args.stats:
        print(f"Skills directory: {skills_dir}")
        print(f"Total skills discovered: {len(skills)}")
        print(f"With IO declarations: {with_io_count}")
        print(f"Without IO declarations: {len(skills) - with_io_count}")
        print(f"Tools exported: {len(tools)}")
        print()
        print("Skills with IO declarations:")
        for skill_dir, fm in skills:
            if fm.get("io"):
                io = fm["io"]
                n_in = len(io.get("input", []))
                n_out = len(io.get("output", []))
                print(f"  {fm['name']}: {n_in} input(s), {n_out} output(s)")
        return

    # Build output document
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = {
        "schema_version": SCHEMA_VERSION,
        "mcp_spec_version": MCP_SPEC_VERSION,
        "exported_at": now,
        "skills_dir": skills_dir,
        "stats": {
            "total_skills": len(skills),
            "with_io": with_io_count,
            "exported": len(tools),
        },
        "tools": tools,
    }

    # Serialize
    indent = 2 if args.pretty else None
    json_str = json.dumps(output, ensure_ascii=False, indent=indent)

    # Output
    if args.output:
        out_path = os.path.expanduser(args.output)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json_str)
            f.write("\n")
        print(f"Exported {len(tools)} tools to {out_path}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
