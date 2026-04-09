---
title: "Context Engine 详细设计"
status: draft
created: 2026-04-07
engine: context-engine
claude_code_refs:
  - "src/services/compact/autoCompact.ts"
  - "src/services/compact/compact.ts"
  - "src/services/compact/prompt.ts"
  - "src/services/contextCollapse/"
  - "src/utils/tokens.ts"
  - "src/utils/contextAnalysis.ts"
---

# Context Engine 详细设计

## 1. 问题陈述

当前 KitClaw 没有任何上下文管理能力。Agent 在长对话中：
- 上下文窗口被撑爆 → API 报错，用户体验断裂
- 用户手动说 `/compact` → 打断工作流
- 换 Agent 后丢失所有上下文 → 从零开始

Claude Code 的 autoCompact 是其最核心的基础设施之一。我们的 Context Engine 需要提取其精华但适配 KitClaw 的"非 Agent 内部"定位。

## 2. 设计约束

| 约束 | 说明 |
|------|------|
| 不在 Agent 循环内 | KitClaw 不控制 Agent 的 query 循环，只能被调用 |
| 不绑定 API | 不直接调 Anthropic/OpenAI API，通过 Agent 间接执行 |
| 纯函数式 | 输入对话，输出摘要+保留消息，无副作用 |
| 可离线工作 | token 估算有本地 fallback |

## 3. 核心 API

```python
# kitclaw/engines/context.py

from dataclasses import dataclass

@dataclass
class CompactResult:
    """压缩结果"""
    summary: str                    # 压缩后的摘要文本
    preserved_messages: list[dict]  # 保留的关键消息（未压缩的尾部）
    original_token_count: int       # 原始 token 数
    compacted_token_count: int      # 压缩后 token 数
    compression_ratio: float        # 压缩率
    metadata: dict                  # 额外元数据

@dataclass
class TokenAnalysis:
    """Token 使用分析"""
    total_tokens: int
    context_window: int             # 模型的上下文窗口大小
    usage_pct: float                # 使用百分比
    tokens_remaining: int           # 剩余 token
    should_compact: bool            # 是否建议压缩
    urgency: str                    # "normal" | "warning" | "critical"

class ContextEngine:
    """上下文管理引擎"""

    # ---- 模型上下文窗口映射 ----
    CONTEXT_WINDOWS = {
        "sonnet": 200_000,
        "opus": 200_000,
        "haiku": 200_000,
        "gpt-4o": 128_000,
        "gpt-4-turbo": 128_000,
        "gemini-2.5-pro": 1_000_000,
        "gemini-2.5-flash": 1_000_000,
    }

    # ---- 阈值常量（参考 Claude Code autoCompact.ts）----
    BUFFER_TOKENS = 13_000            # 压缩保留缓冲区
    WARNING_THRESHOLD_TOKENS = 20_000 # 警告阈值
    MAX_OUTPUT_TOKENS = 20_000        # 压缩摘要最大输出
    MAX_CONSECUTIVE_FAILURES = 3      # 熔断器阈值

    def estimate_tokens(self, text: str, model: str = "sonnet") -> int:
        """估算文本 token 数
        优先使用 tiktoken，fallback 到字数估算（中文×1.5, 英文÷4）"""

    def analyze(self, messages: list[dict], model: str) -> TokenAnalysis:
        """分析当前上下文的 token 使用状况"""

    def should_compact(self, messages: list[dict], model: str) -> bool:
        """判断是否需要压缩
        公式：token_count >= context_window - max_output - buffer"""

    def get_compact_prompt(self, messages: list[dict]) -> str:
        """生成压缩 prompt"""

    def apply_compact(self, messages: list[dict], session_id: str | None = None) -> list[dict]:
        """执行压缩：
        1. 组装 prompt
        2. 发送给后台 Ghost Agent
        3. 拿到 summary，保留尾部重要消息
        4. (可选) 保存到 session 快照
        5. 返回新 messages"""
```

## 4. 压缩 Prompt 模板

> 直接参考 Claude Code `services/compact/prompt.ts`，适配为 Markdown 模板。

```markdown
# kitclaw/prompts/compact.md

Your task is to create a detailed summary of the conversation so far,
paying close attention to the user's explicit requests and preferences.

Your summary should include the following sections:

## 1. Primary Request and Intent
State the user's original request precisely. Include important context
like deadlines, constraints, or specific requirements.

## 2. Key Technical Decisions Made
List every significant technical decision, including:
- What was chosen and what was rejected
- The reasoning behind each choice
- Any constraints that influenced the decision

## 3. Current Progress
Describe what has been completed so far:
- Files created or modified (with brief descriptions)
- Tests run and their results
- Issues discovered and resolved

## 4. Open Issues and Blockers
List anything that is still unresolved:
- Errors that persist
- Questions that need answers
- Dependencies that are missing

## 5. Exact Current State
Where did the conversation leave off? Include:
- The last thing being worked on
- Direct quotes from the most recent exchange
- Any partially completed work

## 6. Immediate Next Steps
What should happen next? Be specific and actionable.

Rules:
- Be precise and specific — use exact file paths, error messages, variable names
- Preserve all technical details that would be needed to continue the work
- Do NOT summarize away details that might be needed later
- Keep the summary under 2000 tokens
```

## 5. Token 估算策略

```python
# kitclaw/utils/tokens.py

def estimate_tokens(text: str, model: str = "sonnet") -> int:
    """三级 fallback token 估算"""
    # Level 1: tiktoken（最精确，需要依赖）
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(_normalize_model(model))
        return len(enc.encode(text))
    except ImportError:
        pass

    # Level 2: 字符数估算（无依赖）
    # 英文: ~4 chars/token, 中文: ~1.5 chars/token
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    en_chars = len(text) - cn_chars
    return int(cn_chars * 1.5 + en_chars / 4)
```

## 6. 使用场景

### 场景 1：Agent 主动索对话压缩

Agent 在 AGENTS.md 中被指示：当对话很长时调用 `kitclaw compact`。

```bash
# Agent 调用
kitclaw context analyze --input /tmp/messages.json
# 输出：{ "should_compact": true, "usage_pct": 87, "urgency": "warning" }

# 如果需要压缩，由 kitclaw 调用其后台 Ghost Agent 直接执行
kitclaw context compact --input /tmp/messages.json --session abc123
# CLI 内部通过自身内置的 API Key，用低廉的小模型处理数十万 token 压缩
# 输出并写入：全新的已压缩 messages 列表。不需要 Agent 分心去写摘要。
```

### 场景 2：会话结束时自动压缩保存

```bash
kitclaw session end --auto-compact
# 内部流程:
# 1. 读取当前会话消息
# 2. 如果超阈值 → 生成 compact prompt
# 3. 内部调用 Ghost Agent 得到压缩摘要
# 4. 保存 compact 结果 + 原始尾部消息到 session 快照
```

## 7. 与其他引擎的交互

| 交互方向 | 说明 |
|----------|------|
| → Session Manager | compact 结果保存到 session 快照 |
| → Memory Engine | compact 前触发记忆提取（防丢失） |
| → Observability | 记录 compact 事件（前后 token 数、压缩率） |
| ← Skill Router | 当 token 超限时推荐 `kitclaw compact` |

## 8. Claude Code 参考映射

| 本设计 | Claude Code 源文件 | 借鉴点 |
|--------|-------------------|--------|
| `estimate_tokens()` | `utils/tokens.ts` → `tokenCountWithEstimation()` | 估算算法 |
| `should_compact()` | `autoCompact.ts` → `getAutoCompactThreshold()` | 阈值公式 |
| 压缩 prompt | `compact/prompt.ts` → `BASE_COMPACT_PROMPT` | prompt 结构 |
| 熔断器 | `autoCompact.ts` → `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3` | 失败保护 |
| `BUFFER_TOKENS` | `autoCompact.ts` → `AUTOCOMPACT_BUFFER_TOKENS = 13_000` | 缓冲区大小 |
