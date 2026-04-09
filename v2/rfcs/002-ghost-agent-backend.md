---
rfc: "002"
title: "KitClaw v2 影子 Agent (Ghost Agent) 模型：后台自动化闭环"
status: accepted
created: 2026-04-07
depends_on: ["rfcs/001-runtime-vs-scripts.md", "design/V2-AUDIT-REPORT.md"]
---

# RFC-002: KitClaw v2 影子 Agent (Ghost Agent) 模型

## 背景

在设计 v2 的自动上下文压缩 (`auto-compact`) 和自动记忆提取 (`auto-extract`) 时，暴露了一个架构硬伤：
KitClaw 是单纯的 CLI 命令，自身并无智能。当前台大模型 Agent（例如 Claude Code）调用 `kitclaw session end` 时，KitClaw 只能印出 Prompt 让前台 Agent 替它执行。
但这会导致**握手断层**：前台 Agent 执行出结果后，由于 CLI 进程早已结束，提取结果无法自动保存并进行去重合并管理。

## 选择

**选项 A：退化为一个可交互的 Agent Loop。** 让 KitClaw 接管完整的终端会话，内置交互框架。
  - 代价：沦为 Claude Code / Cursor 的直接竞品，丧失“支持一切终端 Agent 的通用中间件”定位。

**选项 B：握手接力协议。** `session end` 打印出 Prompt，要求 Agent 处理后通过新的 `kitclaw task submit` 进行提交。
  - 代价：太复杂，增加不稳定性，消耗昂贵的前台模型算力。

**选项 C：影子 Agent (Ghost Agent) 模型（强烈推荐）。**
  - 为 KitClaw `config.toml` 配置一组独立且廉价的 API (如 Google Gemini 1.5 Flash / Claude Haiku / DeepSeek)。
  - 核心后台智力任务（压缩、记忆提取）不再要求前台 Agent 做，而是由 KitClaw 在后台直接组装 Prompt 发包给自己的影子小模型。

## 决定

**坚决采用选项 C：影子 Agent 模型。**

## 具体含义与优势

1. **分离大小脑与控制成本**：前台你可以用天价且缓慢的 Sonnet 3.5 写代码，但在底层默默为你做长文本压缩、历史打标签的工作，由后台闪电般廉价的 Flash 替你静默完成。
2. **彻底的全自动闭环**：`kitclaw session end` 被调用后，内部：读取上下文 -> 传给影子 API -> 获取答案 -> 在文件系统上锁 -> 更新索引库 -> 返回成功状态 -> 进程退出。
3. **极简的代码依赖**：只需要挂载极简的 Python API 请求库封装（如果可以保持 StdLib 就用 urllib 写几个简单的 HTTP 请求直连）。它绝不动摇“KitClaw 是中间件架构”的定位，只是中间件长了一颗专门干杂活的“小脑”。

## 影响

- 在 `config.toml` 增加 `[llm_backend]` 区块。
- 在相关的设计文档（Context Engine 和 Memory Engine）中全面废弃掉“抛回 Prompt 给 Agent”的做法，明确它们直接通过 `Ghost Agent` 得到执行反馈并在内部闭环！
- Storage Layer 需要引入文件锁解决并发。
