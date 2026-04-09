---
name: agent-orchestrator
description: Validate and plan linear skill chains defined in YAML. Reads IO contracts from skill frontmatter, verifies type compatibility between chained steps, and outputs step-by-step execution plans. Use when the user wants to orchestrate multiple skills in sequence, validate a chain definition, or see an execution plan for a multi-skill pipeline. 当用户提到"编排""orchestrate""chain""pipeline""串联 skill""执行链"时触发。NOT for single skill execution. NOT for DAG or parallel orchestration. Prefer this for chain validation and planning; actual skill execution is done by the user or agent following the generated plan.
io:
  input:
    - type: text
      description: YAML 编排链文件路径
    - type: directory
      description: Skill 仓库目录（用于读取 IO 契约）
      required: false
  output:
    - type: json_data
      description: 编排验证结果或分步执行计划
---

# Agent Orchestrator — 线性链式 Skill 编排

## 定位

基于 Phase 1 IO 契约的线性链式编排 MVP。读取 YAML 编排链定义，验证相邻 skill 的 IO 类型匹配，输出分步执行计划。

> **不是执行器**：orchestrator 验证链的合法性并生成执行指引，不直接调用 agent 执行 skill。

## 核心能力

1. **validate** — 验证编排链的 IO 类型匹配（精确匹配 + 兼容匹配）
2. **plan** — 输出带变量替换的分步执行指引
3. **list** — 列出所有已注册的预定义编排链

## 使用方式

```bash
# 验证链
python3 scripts/run-chain.py validate chains/translate-tweet-publish.yaml

# 生成执行计划（带变量）
python3 scripts/run-chain.py plan chains/translate-tweet-publish.yaml --var URL=https://x.com/...

# 列出所有链
python3 scripts/run-chain.py list
```

## 编排链 YAML 格式

见 `references/chain-schema.md`。

## 依赖

- Phase 1 IO 契约（`type-registry.json`、skill frontmatter `io:` 声明）
- 零外部依赖（纯 Python stdlib）
