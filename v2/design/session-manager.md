---
title: "Session Manager 详细设计"
status: draft
created: 2026-04-07
engine: session-manager
claude_code_refs:
  - "src/utils/sessionStorage.ts"
  - "src/utils/sessionActivity.ts"
  - "src/services/SessionMemory/"
  - "src/services/compact/compact.ts"
---

# Session Manager 详细设计

## 1. 问题陈述

当前 KitClaw 没有"会话"概念。每次 Agent 对话都是一次性的：
- 关闭 Agent → 所有上下文丢失
- 换 Agent → 从头解释
- 第二天继续 → 不记得昨天做了什么

这是 KitClaw v2 的**杀手功能**：跨 Agent 会话续接。

## 2. 核心概念

```
Session = 一段有始有终的工作单元

一个 Session 包含：
- 元数据（谁、什么项目、什么时间）
- 上下文快照（压缩后的对话摘要）
- 记忆提取（这个会话产生的记忆条目）
- 状态（active / paused / completed）
```

## 3. 数据模型

```python
@dataclass
class SessionMeta:
    """会话元数据"""
    session_id: str                     # UUID
    project: str                        # 项目名
    agent: str                          # 创建者 Agent (claude / gemini / codex)
    started_at: datetime
    ended_at: datetime | None = None
    status: Literal["active", "paused", "completed"] = "active"
    parent_session: str | None = None   # 续接自哪个会话
    tags: list[str] = field(default_factory=list)
    summary: str = ""                   # 会话摘要（人类可读）
    token_count_start: int = 0          # 开始时的 token 数
    token_count_end: int = 0            # 结束时的 token 数
    tool_calls: int = 0                 # 工具调用次数
    compactions: int = 0                # 压缩次数

@dataclass
class Session:
    """完整会话"""
    meta: SessionMeta
    context_snapshot: str | None = None         # 压缩后的上下文
    extracted_memories: list[MemoryEntry] = field(default_factory=list)
    handoff_note: str | None = None             # 交接备注
```

## 4. 存储结构

```
~/.kitclaw/sessions/
├── index.json                          # 所有会话的索引
└── <session-id>/
    ├── meta.json                       # SessionMeta
    ├── context.md                      # 压缩后的上下文（Markdown，人类可读）
    ├── context.json.gz                 # 原始消息快照（压缩存储，可选）
    ├── memories.json                   # 本次提取的记忆
    └── handoff.md                      # 交接备注（给下一个 Agent 看）
```

### 会话索引

```json
{
  "schema_version": "2.0",
  "sessions": [
    {
      "id": "abc-123",
      "project": "kitclaw",
      "agent": "claude",
      "status": "completed",
      "started_at": "2026-04-07T10:00:00+08:00",
      "ended_at": "2026-04-07T12:30:00+08:00",
      "summary": "完成 Context Engine 设计文档",
      "tags": ["design", "v2"]
    },
    {
      "id": "def-456",
      "project": "kitclaw",
      "agent": "gemini",
      "status": "active",
      "started_at": "2026-04-07T14:00:00+08:00",
      "parent_session": "abc-123",
      "summary": "续接：开始实现 Context Engine"
    }
  ]
}
```

## 5. 核心 API

```python
class SessionManager:

    def start(self, project: str, agent: str, *,
              resume_from: str | None = None,
              tags: list[str] | None = None) -> Session:
        """开始新会话
        如果 resume_from 指定，加载上一个会话的上下文和记忆"""

    def end(self, session_id: str, *,
            auto_compact: bool = True,
            auto_extract_memory: bool = True,
            messages: list[dict] | None = None) -> SessionMeta:
        """结束会话（Ghost Agent 全自动闭环）
        1. 可选：Ghost Agent 压缩当前上下文（内部 API 调用）
        2. 可选：Ghost Agent 提取记忆（内部 API 调用）
        3. 文件锁保护写入
        4. 保存快照 + 更新索引
        5. 降级保护：Ghost Agent 不可用时，保存原始 gzip 快照"""

    def pause(self, session_id: str) -> SessionMeta:
        """暂停会话（保存状态但不结束）"""

    def resume(self, session_id: str, agent: str | None = None) -> Session:
        """恢复会话（可以用不同的 Agent 恢复）"""

    def list(self, *,
             project: str | None = None,
             agent: str | None = None,
             status: str | None = None,
             limit: int = 20) -> list[SessionMeta]:
        """列出会话"""

    def handoff(self, session_id: str, to_agent: str, *,
                note: str | None = None) -> str:
        """生成交接文档（给目标 Agent 的上下文注入）"""

    def cleanup(self, retention_days: int = 30) -> int:
        """清理过期会话快照"""
```

## 6. 杀手场景：跨 Agent 会话续接

```
14:00 — 用 Claude Code 写 KitClaw v2 的 Context Engine
  ↓
16:00 — Claude Code 限额用完 / 需要换思路
  ↓
用户：kitclaw session end --agent claude --project kitclaw
  ↓ （Ghost Agent 内部自动压缩上下文、提取记忆、加锁写入、保存快照）
  ↓ （如果 Ghost Agent 不可用，降级保存原始 gzip 快照）
  ↓
用户：kitclaw session start --agent gemini --project kitclaw --resume-latest
  ↓
Gemini 收到的启动上下文：

---
## 会话续接 — 来自 Claude Code 的上下文

### 之前的工作
[这里是 Context Engine 生成的压缩摘要]

### 关键决策
- 选择 click 作为 CLI 框架
- token 估算采用 tiktoken + 字数 fallback
- 压缩阈值设为 80% 上下文窗口

### 当前状态
Context Engine 的 estimate_tokens 和 should_compact 已实现。
正在写 apply_compact 方法。

### 待完成
1. apply_compact 方法实现
2. 单元测试
3. 与 Session Manager 的集成
---

Gemini 可以无缝继续。
```

## 7. 交接文档模板

```markdown
# kitclaw/prompts/session_handoff.md

## Session Handoff

**Project**: {project}
**Previous Agent**: {from_agent}
**Previous Session**: {session_id}
**Duration**: {duration}

### Context Summary
{context_snapshot}

### Key Decisions Made
{decisions}

### Current Working State
{current_state}

### Related Memories
{related_memories}

### Handoff Note
{handoff_note}

---
Continue from where the previous session left off.
Do NOT re-do work that has already been completed.
If you need clarification on any previous decision, ask the user.
```

## 8. CLI 命令

```bash
# 开始会话
kitclaw session start --project kitclaw --agent claude
# → 输出 session_id，注入 AGENTS.md 指令

# 结束会话（自动压缩 + 提取记忆）
kitclaw session end
# → 输出摘要 + 提取的记忆条目

# 列出最近会话
kitclaw session list --project kitclaw
# → 表格显示 id / agent / status / summary

# 续接会话
kitclaw session resume --latest --agent gemini
# → 输出交接文档（直接注入到 Gemini 的上下文）

# 交接（显式指定）
kitclaw session handoff abc-123 --to gemini --note "请继续写测试"
# → 生成交接文档

# 查看会话详情
kitclaw session show abc-123
# → 显示完整的 meta + context + memories
```

## 9. AGENTS.md 注入

v2 的 AGENTS.md 模板中注入以下指令：

```markdown
## 会话生命周期

在开始工作前，运行：
`kitclaw session start --project <project> --agent <your-name>`

在完成主要任务后（不是每轮对话后），运行：
`kitclaw session end`
（KitClaw 会自动通过内置 Ghost Agent 完成压缩和记忆提取，你无需额外操作）

如果用户说"换个 Agent 继续"或"我一会儿用 xxx 继续"，运行：
`kitclaw session handoff --to <agent>`
```

> 🟡 **先行实现**：`~/.ai-skills/project-manager/scripts/kit-start.py`
> 在 `kitclaw session start` CLI 完成前，`kit-start.py` 是手动版"会话启动"替代方案：
> - 自动运行 `collect-status.py --brief` 采集项目简报
> - 拼装成"带上下文的对话起手式"
> - 复制到剪贴板，用户粘贴到新对话即可获得等效的上下文注入效果
>
> 计划：`kitclaw session start` 实现后，`kit-start.py` 的逻辑直接迁移为 `session start` 的 context injection 步骤。



## 10. 与其他引擎的交互

| 方向 | 交互 |
|------|------|
| → Context Engine | `session end` 时调用 `compact()` |
| → Memory Engine | `session end` 时调用 `extract_from_conversation()` |
| → Observability | 记录会话生命周期事件 |
| ← Skill Router | 会话开始时加载相关记忆供 Agent 使用 |
