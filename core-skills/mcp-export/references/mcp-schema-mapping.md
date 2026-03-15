---
title: "MCP Schema Mapping"
tags: [mcp, schema, skills]
scope: dev
---

# MCP Schema Mapping

`mcp-export` maps KitClaw skill metadata to a small MCP-compatible tool schema.

## Current Mapping

- `name` -> MCP tool `name`
- `description` -> MCP tool `description`
- `io.input[*]` -> `inputSchema.properties`
- `io.input[*].required` -> `inputSchema.required`
- skill folder structure -> `annotations.readOnlyHint`

## Input Type Mapping

| Skill IO type | JSON Schema |
| --- | --- |
| `text` | `{ "type": "string" }` |
| `markdown_file` | `{ "type": "string" }` |
| `json_data` | `{ "type": "string" }` |
| `directory` | `{ "type": "string" }` |
| `url` | `{ "type": "string", "format": "uri" }` |
| unknown | `{ "type": "string" }` |

## Scope

This mapping is intentionally conservative.

- It does not encode full execution semantics
- It does not expose side-effect policy beyond a few annotations
- It is intended for discovery and lightweight routing, not full sandbox policy
