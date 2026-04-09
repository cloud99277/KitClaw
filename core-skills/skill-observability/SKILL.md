---
name: skill-observability
description: Record skill execution logs, generate usage statistics, find unused skills, and produce observability reports. Use when the user wants to track which skills are being used, find unused or high-failure-rate skills, or generate a monthly usage report. NOT for security scanning (use skill-security-audit), NOT for skill format validation (use skill-lint). 当用户提到"可观测""执行日志""使用统计""未使用 skill""月度报告""observability""log execution"时触发。
io:
  input:
    - type: text
      description: 要记录的 skill 名称、agent、执行状态等信息
  output:
    - type: json_data
      description: 执行日志（JSONL 格式）或统计报告
      path_pattern: "~/.ai-skills/.logs/executions.jsonl"
---

# Skill Observability — 执行日志与使用统计

## 角色定义

你是一个 **Skill 运维分析师**，负责追踪 skill 的执行情况，识别高频使用和从未使用的 skill，帮助用户了解工具链的健康状况。

## 工具清单

| 脚本 | 功能 | 典型用法 |
|------|------|---------|
| `scripts/log-execution.py` | 记录一次 skill 执行 | 每次执行完 skill 后调用 |
| `scripts/find-unused.py` | 查找从未使用的 skill | 仓库瘦身候选 |
| `scripts/report.py` | 生成使用统计报告 | 月度回顾 |

## 使用场景

### 记录执行日志

执行完一个 skill 后，用 `log-execution.py` 记录：

```bash
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill translate --agent gemini --status success \
  --input-fields file to mode --output-file translation.md
```

### 查找未使用 Skill

```bash
python3 ~/.ai-skills/skill-observability/scripts/find-unused.py \
  --skills-dir ~/.ai-skills
```

### 生成报告

```bash
python3 ~/.ai-skills/skill-observability/scripts/report.py
```

## 日志格式

每条日志是一行 JSON，追加写入 `~/.ai-skills/.logs/executions.jsonl`。

详见 `references/log-schema.md`。

## 安全约束

- `input_fields` 只记字段名，**严禁记录字段值**（防止凭据泄露）
- 日志文件权限默认 600（仅文件所有者可读写）
