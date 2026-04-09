---
name: mcp-export
title: mcp-export
description: >
  Export SKILL.md frontmatter to MCP (Model Context Protocol) compatible JSON
  schema. Generates tools/list compatible JSON for any MCP-aware agent to
  discover and invoke skills. Use when user mentions "MCP", "Model Context
  Protocol", "导出 MCP", "MCP schema", "tools/list export".
  当用户提到"MCP导出""MCP兼容""导出工具列表""MCP JSON"时触发。
io:
  input:
    - type: directory
      description: Skill 仓库目录（默认 ~/.ai-skills/）
  output:
    - type: json_data
      description: MCP 兼容的 Tool JSON Schema（tools/list 格式）
      path_pattern: "mcp-tools.json"
---

# MCP Export — SKILL.md → MCP Tool JSON 导出

## 用途

将 Agent Toolchain 的 SKILL.md frontmatter 导出为符合 MCP 2025-03-26 规范的 Tool JSON schema。

> **只做导出，不做 MCP Server 运行时。** 导出的 JSON 可被任何 MCP 兼容的 Agent/Client 消费。

## 使用方式

```bash
# 导出所有 skill 到 stdout（JSON 格式）
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py

# 导出到文件
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --output tools.json

# 仅导出指定 skill
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --skill translate --skill deep-research

# 查看统计信息
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --stats

# Pretty-print 格式化输出
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --pretty
```

## 输出格式

```json
{
  "schema_version": "1.0",
  "mcp_spec_version": "2025-03-26",
  "exported_at": "2026-03-14T19:00:00+08:00",
  "tools": [
    {
      "name": "translate",
      "description": "...",
      "inputSchema": { "type": "object", "properties": {...}, "required": [...] },
      "annotations": { "readOnlyHint": false, ... }
    }
  ]
}
```

## 映射规则

详见 `references/mcp-schema-mapping.md`。

## 依赖

- Python 3（stdlib only，零外部依赖）
- `~/.ai-skills/.system/io-contracts/type-registry.json`（IO 类型映射）
