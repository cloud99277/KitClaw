---
rfc: "001"
title: "运行时中间件 vs 纯脚本集：KitClaw v2 架构决策"
status: proposed
created: 2026-04-07
---

# RFC-001: 运行时中间件 vs 纯脚本集

## 背景

KitClaw v1 采用"纯脚本集"架构：每个 skill 是独立的 Python 脚本，通过 SKILL.md 描述，Agent 按需调用。

这个架构的核心假设是：**Agent 会自觉地在正确的时机调用正确的 skill。**

实际使用中发现这个假设很脆弱。Agent 经常不调、调错、调晚。

## 决策

**选项 A：保持纯脚本集，增强文档和 prompt 注入**
- 风险：仍然依赖 Agent 自觉
- 投入：低
- 上限：有限

**选项 B：构建轻量运行时层（CLI 统一入口 + 协议约定）**
- 通过 `kitclaw` CLI 统一入口
- 通过 AGENTS.md 注入"关键时刻必须调用 kitclaw"的协议
- 不是 daemon，不是服务端，仍然是 Agent 主动调用
- 但调用体验标准化，生命周期 hooks 自动执行
- 风险：中等
- 投入：中等
- 上限：高

**选项 C：构建常驻 daemon 服务**
- 风险：违背"零基础设施"原则
- 投入：高
- 上限：最高，但维护成本也最高

## 决定

**选择 B：轻量运行时层。**

理由：
1. 保持 KitClaw "零服务端"的核心原则
2. `kitclaw` CLI 是对用户透明的——Agent 调用一个命令而不是一堆脚本
3. hooks 自动执行解决了"靠 Agent 自觉"的问题
4. 为未来升级到 C 留出了空间

## 具体含义

```
v1 调用方式：
  python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "query"

v2 调用方式：
  kitclaw memory search "query"
  kitclaw compact --model sonnet
  kitclaw session end --auto-extract
```

v2 的 `kitclaw` CLI 内部会：
1. 解析命令 → 找到对应 skill
2. 执行 pre-hooks（权限检查、输入校验）
3. 运行 skill 脚本
4. 执行 post-hooks（观测记录、自动 L2）
5. 返回结果

Agent 只需要知道一个入口：`kitclaw`。

## 影响

- AGENTS.md 模板需要重写
- 所有 core skill 需要注册到 CLI
- skill-specification.md 需要增加 lifecycle hooks 字段
- 需要一个 Python package（pyproject.toml）
