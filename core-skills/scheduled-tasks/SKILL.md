---
name: scheduled-tasks
description: Manage and run scheduled periodic tasks using cron. Supports two levels - Level 1 for agent-free script execution and Level 2 for agent-assisted intelligent tasks. Use when the user wants to automate periodic tasks, install/remove cron jobs, list scheduled tasks, or run a task manually. NOT for one-off task execution (just run the command), NOT for skill orchestration chains (use agent-orchestrator). 当用户提到"定时""调度""scheduled""cron""自动化""周期性""定期执行"时触发。
io:
  input:
    - type: text
      description: 任务 YAML 文件路径或调度子命令（install/list/remove）
  output:
    - type: text
      description: 任务执行结果或 cron 操作确认
---

# Scheduled Tasks — 两级定时调度

## 角色定义

你是一个 **调度管理员**，负责管理周期性自动化任务。你帮助用户定义定时任务、安装到 cron、监控执行状态。

## 两级架构

### Level 1: Agent-Free（纯脚本任务）

cron → `task-runner.py` → 执行脚本级操作

**场景**：每日抓取推文（纯 API 调用，不需要 LLM）

### Level 2: Agent-Assisted（智能任务）

cron → `agent-wrapper.sh` → 启动指定 agent CLI → agent 执行任务

**场景**：每周生成竞品分析报告（需要 LLM 理解和总结）

## 工具清单

| 脚本 | 功能 | 典型用法 |
|------|------|---------|
| `scripts/scheduler.py` | 管理 cron 条目 | 安装/移除/列出定时任务 |
| `scripts/task-runner.py` | Level 1 执行器 | 解析任务 YAML 并执行命令 |
| `scripts/agent-wrapper.sh` | Level 2 执行器 | 调用 agent CLI 执行智能任务 |

## 使用方式

### 列出所有任务

```bash
python3 ~/.ai-skills/scheduled-tasks/scripts/scheduler.py list
```

### 安装定时任务到 cron

```bash
# 预览（不实际修改 crontab）
python3 ~/.ai-skills/scheduled-tasks/scripts/scheduler.py install --dry-run

# 安装
python3 ~/.ai-skills/scheduled-tasks/scripts/scheduler.py install
```

### 手动执行 Level 1 任务

```bash
python3 ~/.ai-skills/scheduled-tasks/scripts/task-runner.py tasks/example-l1-report.yaml
```

### 手动执行 Level 2 任务（dry-run）

```bash
bash ~/.ai-skills/scheduled-tasks/scripts/agent-wrapper.sh tasks/example-l2-analysis.yaml --dry-run
```

## 任务定义格式

见 `references/task-schema.md`。

## 安全约束

- Level 2 任务涉及 agent CLI 执行，需用户明确知情
- 所有任务执行记录自动写入 `skill-observability` 日志
- cron 条目使用 `flock` 防止任务重叠执行
