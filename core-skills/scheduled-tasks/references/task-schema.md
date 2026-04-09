---
name: task-schema
title: Task Schema
type: reference
---
# Task YAML Schema

> **版本**：1.0
> **格式**：YAML 子集（扁平键值对 + 内联数组）

---

## 字段定义

### 必填字段

| 字段 | 类型 | 说明 | 校验规则 |
|------|------|------|---------|
| `schema_version` | string | 数据格式版本 | 当前必须为 `"1.0"` |
| `name` | string | 任务唯一标识 | `[a-z0-9-]+`，kebab-case |
| `description` | string | 人类可读说明 | 非空 |
| `level` | integer | 执行级别 | `1` 或 `2` |
| `schedule` | string | cron 表达式 | 5 字段标准格式 |
| `enabled` | boolean | 是否启用 | `true` 或 `false` |

### Level 1 必填字段

| 字段 | 类型 | 说明 | 校验规则 |
|------|------|------|---------|
| `command` | string | 要执行的命令 | 非空 |

### Level 2 必填字段

| 字段 | 类型 | 说明 | 校验规则 |
|------|------|------|---------|
| `agent` | string | 执行 agent | `gemini` \| `claude` \| `codex` |
| `prompt` | string | 给 agent 的完整指令 | 非空 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `args` | array[string] | `[]` | Level 1 命令参数列表 |
| `working_dir` | string | `$HOME` | 工作目录 |
| `timeout_seconds` | integer | `300` | 超时时间（秒） |
| `on_failure` | string | `"log"` | 失败策略：`log` \| `retry` |
| `max_retries` | integer | `0` | 重试次数 |
| `output_dir` | string | `null` | 输出目录 |

---

## 示例

### Level 1 任务

```yaml
schema_version: "1.0"
name: monthly-observability-report
description: 每月 1 日生成上月 skill 使用报告
level: 1
schedule: "0 9 1 * *"
enabled: true
command: "python3"
args: ["~/.ai-skills/skill-observability/scripts/report.py", "--output", "~/.ai-skills/.logs/report-latest.md"]
working_dir: "~"
timeout_seconds: 60
on_failure: log
max_retries: 0
```

### Level 2 任务

```yaml
schema_version: "1.0"
name: weekly-skill-health-check
description: 每周日生成 skill 健康度分析报告（需要 LLM 总结）
level: 2
schedule: "0 10 * * 0"
enabled: false
agent: gemini
prompt: "请运行 skill-observability 的 report.py 和 find-unused.py，然后总结出本周 skill 使用趋势和建议。将报告保存到 ~/.ai-skills/.logs/weekly-health.md"
timeout_seconds: 600
on_failure: log
max_retries: 0
```

---

## cron 表达式参考

```
┌───────────── 分钟 (0-59)
│ ┌───────────── 小时 (0-23)
│ │ ┌───────────── 日 (1-31)
│ │ │ ┌───────────── 月 (1-12)
│ │ │ │ ┌───────────── 星期 (0-7, 0和7都是周日)
│ │ │ │ │
* * * * *
```

常用示例：
- `0 8 * * *` — 每天 8:00
- `0 9 1 * *` — 每月 1 日 9:00
- `0 10 * * 0` — 每周日 10:00
- `*/30 * * * *` — 每 30 分钟
- `0 0 * * 1-5` — 工作日午夜
