---
name: mcp-export
title: "MCP Export Skill"
tags: [skills, mcp, interoperability]
scope: dev
description: >
  Export SKILL.md frontmatter to MCP (Model Context Protocol) compatible JSON
  schema. Generates tools/list style JSON so MCP-aware runtimes can discover
  and route KitClaw skills. Use when the user asks for MCP export, tools/list,
  MCP schema, or skill metadata interoperability.
io:
  input:
    - type: directory
      description: Skills root to scan. Defaults to KitClaw core-skills.
      required: false
  output:
    - type: json_data
      description: MCP-compatible tool schema export
      path_pattern: "mcp-tools.json"
---

# MCP Export

Export `SKILL.md` frontmatter into MCP-compatible `tools/list` JSON.

## Why It Exists

KitClaw treats each skill as a reusable runtime unit. `mcp-export` makes that
metadata portable so other MCP-aware agents or runtimes can discover the same
skills without re-authoring tool schemas by hand.

## Common Commands

```bash
# Export KitClaw core-skills to stdout
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --pretty

# Export to a file
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py \
  --output /tmp/mcp-tools.json --pretty

# Export a subset
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py \
  --skill memory-manager \
  --skill knowledge-search

# Export another shared skills repo instead of KitClaw core-skills
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py \
  --skills-dir ~/.ai-skills \
  --stats
```

## Output

The script emits:

- `schema_version`
- `mcp_spec_version`
- `exported_at`
- `skills_dir`
- `stats`
- `tools`

Each exported tool includes:

- `name`
- `description`
- `inputSchema`
- `annotations`

## Notes

- Default scan root is this KitClaw repo's `core-skills/`
- Output is pure JSON; this skill does not run an MCP server
- The script uses Python stdlib only
