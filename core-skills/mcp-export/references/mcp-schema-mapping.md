---
name: mcp-schema-mapping
title: Mcp Schema Mapping
type: reference
---
# MCP Schema Mapping — SKILL.md → MCP Tool JSON 映射规则

> **MCP 规范版本**：2025-03-26
> **参考源**：https://modelcontextprotocol.io/specification/2025-03-26/server/tools

---

## 一、MCP Tool JSON 结构

```json
{
  "name": "string",
  "description": "string",
  "inputSchema": {
    "type": "object",
    "properties": { ... },
    "required": [ ... ]
  },
  "annotations": {
    "title": "string (optional)",
    "readOnlyHint": "boolean (default: false)",
    "destructiveHint": "boolean (default: true)",
    "idempotentHint": "boolean (default: false)",
    "openWorldHint": "boolean (default: true)"
  }
}
```

---

## 二、frontmatter → MCP 映射表

| SKILL.md frontmatter | MCP Tool 字段 | 映射策略 |
|---------------------|--------------|---------|
| `name` | `name` | 直接映射，保留 kebab-case |
| `description` | `description` | 直接映射（多行折叠为单行） |
| `io.input[]` | `inputSchema.properties` | 见 §三 |
| `io.input[].required` | `inputSchema.required` | 默认 true，明确标 `required: false` 才排除 |
| （推断） | `annotations.title` | 从 `name` 生成：kebab-case → Title Case |
| （推断） | `annotations.readOnlyHint` | 有 scripts/ → false，无 → true |
| （推断） | `annotations.destructiveHint` | 默认 false |
| — | `annotations.idempotentHint` | 默认 false |
| （推断） | `annotations.openWorldHint` | 默认 false |

---

## 三、IO 类型 → JSON Schema 映射

基于 `~/.ai-skills/.system/io-contracts/type-registry.json` 中的 7 种标准类型：

| type-registry `id` | JSON Schema | 备注 |
|--------------------|-----------  |------|
| `text` | `{"type": "string"}` | 最宽泛类型 |
| `markdown_file` | `{"type": "string", "description": "Path to Markdown file (.md)"}` | |
| `url` | `{"type": "string", "format": "uri"}` | 标准 URI 格式 |
| `image_file` | `{"type": "string", "description": "Path to image file (.png/.jpg/.webp)"}` | |
| `json_data` | `{"type": "string", "description": "Path to JSON file or inline JSON string"}` | |
| `html_file` | `{"type": "string", "description": "Path to HTML file (.html)"}` | |
| `directory` | `{"type": "string", "description": "Path to directory"}` | |

### InputSchema 生成规则

**有 `io:` 声明**：
```json
{
  "type": "object",
  "properties": {
    "input_0_markdown_file": {
      "type": "string",
      "description": "需要翻译的 Markdown 文件"
    },
    "input_1_url": {
      "type": "string",
      "format": "uri",
      "description": "需要获取并翻译的 URL"
    }
  },
  "required": ["input_0_markdown_file"]
}
```

property 命名规则：`input_{index}_{type}`（确保唯一性）。  
required 判定：默认 required = true，除非 io.input[] 中标注 `required: false`。

**无 `io:` 声明**：
```json
{
  "type": "object"
}
```

表示"无结构化参数要求，Agent 可自由传参"。

---

## 四、annotations 推断规则

| 字段 | 规则 | 依据 |
|------|------|------|
| `title` | `name.replace("-", " ").title()` | MCP 规范可选字段，用于 UI 展示 |
| `readOnlyHint` | 检查 skill 目录下是否存在 `scripts/` | 有 scripts = 可执行 = 非只读 |
| `destructiveHint` | 固定 `false` | Agent Toolchain skill 基本不做破坏性操作 |
| `idempotentHint` | 固定 `false` | 大多数 skill 产出因 LLM 非确定性而不幂等 |
| `openWorldHint` | 固定 `false` | 保守默认，实际使用中部分 skill 会访问网络 |

### 已知局限

> v1->v2 变更：来源：双重审查 盲点 4 + PHASE-7-REVIEW 盲点 1。

- **`readOnlyHint` 推断粗放**：当前用"是否有 `scripts/` 目录"来推断。但部分纯 SKILL.md 的 skill（如 `baoyu-post-to-wechat`）虽无 scripts 目录，实际上会指导 Agent 执行有副作用的操作（发布到微信）。MCP 客户端可能因此跳过确认提示。
- **未来改进**（Backlog B7-1）：考虑在 SKILL.md frontmatter 中支持可选的 `mcp_annotations:` 覆盖字段，允许 skill 作者显式指定 annotations。

---

## 五、导出 JSON 顶层结构

> v1->v2 变更：来源：双重审查 盲点 3 + PHASE-7-REVIEW 建议 3。标注哪些字段是 MCP 标准、哪些是 Agent Toolchain 扩展。

```json
{
  "schema_version": "1.0",
  "mcp_spec_version": "2025-03-26",
  "exported_at": "ISO 8601 时间戳",
  "skills_dir": "skill 仓库路径",
  "stats": {
    "total_skills": 90,
    "with_io": 5,
    "exported": 90
  },
  "tools": [ ... ]
}
```

**字段标准性说明**：
- `tools` — MCP `tools/list` 响应标准字段
- `schema_version`、`mcp_spec_version`、`exported_at`、`skills_dir`、`stats` — **Agent Toolchain 自定义扩展**，不属于 MCP 标准。MCP 客户端会忽略未知字段，不影响兼容性。
