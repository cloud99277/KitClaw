---
name: log-schema
title: Log Schema
type: reference
---
# Execution Log JSONL Schema

> **版本**：1.0
> **格式**：JSONL（每行一个 JSON 对象）
> **文件位置**：`~/.ai-skills/.logs/executions.jsonl`

---

## Schema 定义

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-03-12T00:00:00Z",
  "skill_name": "translate",
  "agent": "gemini",
  "status": "success",
  "duration_seconds": 3.5,
  "input_fields": ["file", "to", "mode"],
  "output_file": "translation.md",
  "notes": null
}
```

## 字段规范

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | ✅ | 当前为 `"1.0"`，破坏性变更时递增（PROJECT.md 约束 6） |
| `timestamp` | string | ✅ | ISO 8601 UTC 格式，如 `"2026-03-12T00:00:00Z"` |
| `skill_name` | string | ✅ | skill 目录名，如 `"translate"` |
| `agent` | string | ✅ | 执行 Agent：`"gemini"` / `"claude"` / `"codex"` / `"unknown"` |
| `status` | string | ✅ | 执行状态：`"success"` / `"failure"` / `"partial"` |
| `duration_seconds` | number / null | ⬜ | 执行耗时（秒），无法获取时为 `null` |
| `input_fields` | array[string] / null | ⬜ | 输入字段名列表（**不记录值，防止凭据泄露**） |
| `output_file` | string / null | ⬜ | 输出文件路径 |
| `notes` | string / null | ⬜ | 备注（如失败原因简述） |

## 安全约束

- `input_fields` **只记字段名**，严禁记录字段值
- 日志文件权限应为 `600`（仅文件所有者可读写）

## 变更策略

- `schema_version` 必须随破坏性变更递增
- 新增可选字段不算破坏性变更（消费者应忽略未知字段）
- 修改/删除必填字段或变更语义算破坏性变更，需提供迁移脚本
