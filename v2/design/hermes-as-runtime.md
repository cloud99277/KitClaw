---
title: "Hermes Agent 作为 KitClaw 最佳运行时载体"
status: draft
created: 2026-04-09
depends_on: ["rfcs/002-ghost-agent-backend.md", "rfcs/003-unified-persona-engine.md", "rfcs/004-memory-extraction-pipeline.md"]
---

# Hermes Agent 作为 KitClaw 最佳运行时载体

## 定位

KitClaw 是设计规范（记忆模型、skill 体系、人格引擎），不是运行时。

在所有 CLI Agent 中，Hermes 是 KitClaw 最佳的运行时载体——不是因为 Hermes 是"最好的 Agent"，而是因为它补上了 KitClaw 缺少的基础设施层。

## 各 Agent 能力对比

| 能力 | Claude Code | Codex | Gemini CLI | OpenClaw | Hermes |
|------|------------|-------|------------|----------|--------|
| 编码能力 | ★★★★★ | ★★★★ | ★★★★ | ★★★ | ★★★ |
| 多平台消息 | ✗ | ✗ | ✗ | ✓ | ✓ (生产级) |
| 多 Provider | ✗ (锁 Anthropic) | ✗ (锁 OpenAI) | ✗ (锁 Google) | ✓ | ✓ |
| 记忆插件架构 | ✗ | ✗ | ✗ | ✗ | ✓ (8 个插件) |
| 内置调度器 | ✗ | ✗ | ✗ | ✓ (heartbeat) | ✓ (cron) |
| Skill Hub 分发 | ✗ | ✗ | ✗ | ✗ | ✓ (GitHub) |
| Systemd 集成 | ✗ | ✗ | ✗ | ✗ | ✓ |
| Session 持久化 | ✓ (SQLite) | ✗ | ✗ | ✓ | ✓ (SQLite) |

## 五大可取之处

### 1. Gateway：唯一有多平台消息接入的 Agent

Claude Code、Codex、Gemini 都没有原生的 Telegram/Discord/Slack/WhatsApp 集成。Hermes 有，且是生产级的。

- systemd user service 管理
- session 持久化（SQLite）
- 多平台统一消息路由
- Hook 机制（事件驱动自动化）

**对 KitClaw 的价值**：Z7 可以通过 Telegram/Discord 随时在线，不需要用户开终端。Persona Engine（RFC-003）的人格注入可以通过 Gateway 实时生效。

### 2. 多 Provider 支持

不锁任何一家 API。支持所有 OpenAI 兼容 endpoint（Nous、OpenRouter、DeepSeek、Ollama、本地模型）。

**对 KitClaw 的价值**：Ghost Agent（RFC-002/004）可以直接复用 Hermes 的 provider 体系，用廉价模型做记忆提取和压缩，不需要额外搭建 API 网关。

### 3. Memory Provider 插件架构

`MemoryProvider` ABC 定义了完整的生命周期接口：

```
initialize()           → 连接、预热
system_prompt_block()  → 注入 system prompt
prefetch(query)        → 每轮预取相关记忆
sync_turn(user, asst)  → 每轮同步
get_tool_schemas()     → 暴露工具给模型
handle_tool_call()     → 分发工具调用
shutdown()             → 清理
```

支持的外部插件：mem0、hindsight、honcho、openviking、holographic、retaindb、byterover、supermemory。

**对 KitClaw 的价值**：可以把 KitClaw L2/L3 做成 Hermes 的 MemoryProvider 插件，让 Hermes 原生调用 KitClaw 记忆，而不是靠 skill 脚本桥接。实现真正的"记忆即插件"。

### 4. Cron 内置调度器

- `~/.hermes/cron/jobs.json` 管理定时任务
- 与 systemd 集成，持久化运行
- 支持多平台投递（cron 结果推送到 Telegram/Discord）

**对 KitClaw 的价值**：RFC-004 的"睡眠整理"（定期记忆合并/归档/索引重建）可以直接跑在 Hermes 的 cron 里，不需要额外部署进程。

### 5. Skills Hub

- 从 GitHub 仓库动态安装 skill
- 安全审计（quarantine、trusted repos）
- 索引缓存和搜索

**对 KitClaw 的价值**：KitClaw 的 skill 可以通过 Hermes 的 hub 分发，用户一行命令安装，降低使用门槛。

## 集成方向

```
KitClaw 设计层                    Hermes 运行时层
─────────────                    ──────────────
RFC-002 Ghost Agent        ←→    Provider 体系（廉价模型 API）
RFC-003 Persona Engine     ←→    SOUL.md + Gateway（多平台推送）
RFC-004 记忆提取管线        ←→    MemoryProvider 插件 + Cron
L1/L2/L3 记忆模型          ←→    MemoryProvider 插件实现
Skill 体系                 ←→    Skills Hub + external_dirs
Observability              ←→    Gateway logs + state.db
```

## 待思考

1. **KitClaw MemoryProvider 插件**：是否要开发 `kitclaw` memory provider，让 Hermes 原生接入 L2/L3？
2. **Gateway 作为 KitClaw 的 Gateway**：是否让 KitClaw CLI 直接调用 Hermes Gateway 发消息？
3. **Skill 分发渠道**：KitClaw skills 是否通过 Hermes Skills Hub 发布？
4. **Ghost Agent 部署**：Ghost Agent 是否以 Hermes cron job 形式运行？
