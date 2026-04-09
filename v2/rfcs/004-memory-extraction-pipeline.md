---
rfc: "004"
title: "记忆自动提取管线：Ghost Agent 驱动的全生命周期记忆管理"
status: proposed
created: 2026-04-09
depends_on: ["rfcs/002-ghost-agent-backend.md", "rfcs/003-unified-persona-engine.md", "design/memory-engine.md"]
---

# RFC-004: 记忆自动提取管线

## 背景

RFC-002 提出了 Ghost Agent 模型，RFC-003 确认了多 Agent 统一人格架构。但记忆层仍然存在一个关键缺口：**记忆提取全靠手动**。

当前流程：
- L2（whiteboard.json）靠 `l2-capture` 手动触发
- L3（Obsidian vault）靠 `conversation-distiller` 手动触发
- Agent 不自觉就不写，高价值对话结束后记忆丢失

Ghost Agent（廉价小模型）应该承担自动记忆提取，但 RFC-002 只提了这个概念，没有细化提取管线的设计。

本 RFC 补充完整的记忆提取管线：**提取 → 过滤 → 去重 → 入库 → 推送 → 整理**。

## 设计原则

| # | 原则 | 含义 |
|---|------|------|
| M1 | **零损耗优先** | 原始对话永远不丢，提取是增强层 |
| M2 | **按需提取** | 不对所有对话都做重提取，有信号才触发 |
| M3 | **置信度过滤** | 不确定的不入库，宁可漏存不可错存 |
| M4 | **跨 Agent 一致** | 所有 Agent 的记忆走同一条管线 |
| M5 | **人类可审计** | 所有记忆都是 Markdown/JSON，人能直接看懂 |

## 管线全景

```
┌─────────────────────────────────────────────────────────────┐
│                    对话生命周期                               │
│                                                             │
│  对话开始                                                    │
│    │                                                        │
│    ├─→ [Prefetch] Ghost Agent 根据当前上下文预取相关记忆      │
│    │   └─→ 注入 Agent context（不需要用户主动问）             │
│    │                                                        │
│  对话进行中（每 N 轮）                                       │
│    │                                                        │
│    ├─→ [Stream Extract] Ghost Agent 增量分析最近对话          │
│    │   └─→ 高置信条目 → staging area                        │
│    │                                                        │
│  对话正常结束                                                │
│    │                                                        │
│    ├─→ [Final Extract] Ghost Agent 最终提取 + staging 合并    │
│    │                                                        │
│  对话异常中断（crash / timeout / 用户离开）                   │
│    │                                                        │
│    └─→ [Recovery] 下次启动时处理未完成的 staging              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    提取后处理                                 │
│                                                             │
│  原始对话快照                                                │
│    │  gzip 压缩，零损耗存储                                   │
│    ↓                                                        │
│  Ghost Agent 提取候选                                        │
│    │  分类 + 置信度评分                                       │
│    ↓                                                        │
│  置信度过滤                                                  │
│    │  >0.8 → 自动入库                                       │
│    │  0.5-0.8 → 下次对话提示用户确认                          │
│    │  <0.5 → 丢弃                                           │
│    ↓                                                        │
│  去重检查                                                    │
│    │  语义相似度 > 阈值 → 跳过或合并                          │
│    ↓                                                        │
│  入库                                                        │
│    │  decision/action/learning → whiteboard.json (L2)        │
│    │  研究/SOP/架构/模板 → Obsidian vault (L3)               │
│    │  临时草稿 → staging（定期清理）                          │
│    ↓                                                        │
│  索引更新                                                    │
│    │  增量更新 LanceDB 语义索引                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    定期维护（睡眠整理）                       │
│                                                             │
│  Ghost Agent 定期（每日/每周）执行：                          │
│    1. 合并：同一 topic 下的多条相关条目 → 合并为一条           │
│    2. 清理：过期 staging 条目、低价值旧记忆                   │
│    3. 降级：L2 中超过 N 天未引用的条目 → 归档或升级到 L3       │
│    4. 索引：重建/修复 LanceDB 索引                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 存储层设计

### 三层存储

```
~/.ai-memory/
├── config.json                  # L3 路径配置
├── whiteboard.json              # L2 结构化记忆（已有）
├── whiteboard.archive.json      # L2 归档（从 whiteboard 降级而来）
├── staging/                     # 提取暂存区
│   ├── <session-id>.json        # 单会话的提取候选
│   └── pending-confirm.json     # 中置信条目，等用户确认
├── snapshots/                   # 原始对话快照（gzip）
│   ├── <session-id>.json.gz     # 零损耗原始对话
│   └── index.json               # 快照索引（时间、Agent、关键词）
└── extraction-log.jsonl         # 提取操作日志（审计用）
```

### 原始快照（M1：零损耗）

每个会话结束时，原始对话 gzip 保存。不做任何处理。

用途：
- 结构化记忆检索不到时，fallback 到原始快照全文搜索
- 用户说"我记得聊过这个但你没记住"时，可以回溯
- 提取质量回顾和调优的数据源

```json
// snapshots/index.json
{
  "sessions": [
    {
      "id": "sess-20260409-001",
      "agent": "hermes",
      "timestamp": "2026-04-09T01:30:00+08:00",
      "turns": 23,
      "topics_hint": ["kitclaw v2", "persona engine", "RFC"],
      "file": "sess-20260409-001.json.gz"
    }
  ]
}
```

### Staging 暂存区

流式提取和最终提取的结果先写 staging，不直接写入 whiteboard.json：

```json
// staging/<session-id>.json
{
  "session_id": "sess-20260409-001",
  "extracted_at": "2026-04-09T02:00:00+08:00",
  "candidates": [
    {
      "type": "decision",
      "content": "Persona Engine 选择 file sync 模式而非 prompt inject",
      "confidence": 0.92,
      "source_turns": [15, 16, 17],
      "auto_admitted": true
    },
    {
      "type": "learning",
      "content": "Hermes personality=kawaii 会覆盖 Z7 SOUL.md 的语气设定",
      "confidence": 0.65,
      "source_turns": [22],
      "auto_admitted": false,
      "pending_confirm": true
    }
  ]
}
```

## 提取策略

### 触发条件（M2：按需提取）

不是所有对话都触发提取。触发信号：

| 信号 | 权重 | 说明 |
|------|------|------|
| 用户说"记住这个"/"记下来" | 强制 | 直接提取，高置信 |
| 做出了明确选择（A 而非 B） | 高 | 决策型记忆 |
| 发现并修复了 bug | 高 | 学习型记忆 |
| 对话超过 N 轮 | 中 | 有足够内容可提取 |
| 用户表达满意/总结 | 中 | 对话可能即将结束 |
| 纯闲聊 < 5 轮 | 低 | 跳过提取 |

### 提取 Prompt（Ghost Agent 用）

```
分析以下对话，提取值得跨会话记忆的内容。

规则：
- 只提取有复用价值的内容，不要记流水账
- 每条必须是独立可理解的（脱离对话上下文也能懂）
- 分类：decision / action / learning / preference / fact
- 给每条打置信度（0-1）

输出 JSON：
{
  "candidates": [
    {
      "type": "decision|action|learning|preference|fact",
      "content": "简短结论（1-2句）",
      "confidence": 0.0-1.0,
      "source_hint": "为什么这条值得记"
    }
  ]
}

如果没有值得记忆的内容，返回 {"candidates": []}。
```

### 置信度过滤（M3）

| 置信度 | 处理 |
|--------|------|
| > 0.8 | 自动写入 L2/L3 |
| 0.5 - 0.8 | 写入 `pending-confirm.json`，下次对话时提示用户 |
| < 0.5 | 丢弃，只记录到 extraction-log |

用户确认方式（Telegram 场景）：
```
Z7: 对了，上次聊到一个事儿，要记下来吗？

「Persona Engine 用 file sync 而不是 prompt inject」
→ 回复 ✅ 记录 / ❌ 跳过
```

### 去重策略

提取候选写入 staging 前，先和已有记忆比对：

1. **精确去重**：内容完全一致 → 跳过
2. **语义去重**：embedding 余弦相似度 > 0.85 → 跳过或合并
3. **冲突检测**：新条目和已有条目矛盾 → 标记，下次对话提示用户确认

## Prefetch 预取（主动回忆）

每轮对话开始前，Ghost Agent 根据当前上下文预取相关记忆：

```
用户消息到达
  ↓
Ghost Agent 做 embedding
  ↓
检索 whiteboard.json + L3 索引
  ↓
Top-K 相关条目（K=3-5）
  ↓
注入 Agent context（作为 <memory> 块）
```

效果：用户不需要说"我记得之前聊过..."，Agent 自动想起相关记忆。

### 降级策略

- Ghost Agent 不可用 → 跳过 prefetch，Agent 无记忆注入
- 检索无结果 → 不注入，正常回答
- Prefetch 延迟 > 2 秒 → 超时跳过，不阻塞用户

## 睡眠整理（定期维护）

Ghost Agent 定期执行记忆整理（cron job 触发，非实时）：

| 任务 | 频率 | 说明 |
|------|------|------|
| L2 合并 | 每日 | 同一 project + 相似 topic 的条目合并 |
| L2 归档 | 每周 | 30 天未引用的 L2 条目 → archive |
| Staging 清理 | 每日 | 已处理的 staging 文件删除 |
| L3 索引重建 | 每周 | 增量索引 + 定期全量重建 |
| 快照清理 | 每月 | > 90 天的快照删除（或移入冷存储） |

## 配置

`~/.kitclaw/config.toml` 新增 `[memory_extraction]` 区块：

```toml
[memory_extraction]
enabled = true
ghost_agent = true                  # 使用 Ghost Agent 做提取（false = 启发式提取）

# 提取触发
min_turns_for_extraction = 3        # 至少 N 轮才触发提取
stream_extract_interval = 8         # 每 N 轮做一次流式提取

# 置信度阈值
auto_admit_threshold = 0.8          # 自动入库阈值
pending_threshold = 0.5             # 待确认阈值（低于此丢弃）

# 去重
dedup_similarity_threshold = 0.85   # 语义去重阈值

# Prefetch
prefetch_enabled = true
prefetch_top_k = 3                  # 预取条目数
prefetch_timeout_secs = 2           # 预取超时

# 存储
snapshot_retention_days = 90
staging_cleanup_days = 7
l2_archive_after_days = 30

# 睡眠整理
consolidation_enabled = true
consolidation_schedule = "daily"    # daily | weekly
```

## 影响

### 需要新建

- `~/.ai-memory/staging/` 目录
- `~/.ai-memory/snapshots/` 目录
- `engines/memory_extraction.py` — 提取管线核心逻辑
- `engines/memory_consolidation.py` — 睡眠整理
- `engines/memory_prefetch.py` — 预取逻辑
- `prompts/memory_extract.md` — Ghost Agent 提取 prompt
- CLI: `kitclaw memory extract|prefetch|consolidate|pending`

### 需要修改

- `config.toml` — 新增 `[memory_extraction]` 区块
- `v2/design/architecture.md` — Memory Engine 详化
- `v2/design/memory-engine.md` — 全面重写

### 与现有系统的关系

| 组件 | 关系 |
|------|------|
| `l2-capture` | 保留，用户手动触发的高优先级入口 |
| `conversation-distiller` | 保留，手动提炼 L3 文档的入口 |
| `memory-manager` | 增强：增加 staging/pending 查询 |
| `knowledge-search` | 不变 |
| Ghost Agent | 新增：记忆提取的核心执行者 |

手动入口（l2-capture、distiller）和自动提取**共存**。手动的优先级更高、置信度默认为 1.0。

## 开放问题

1. **提取 prompt 的语言**：当前对话是中文，提取 prompt 也用中文？还是用英文提取以保持条目格式统一？
2. **embedding 模型选择**：去重和 prefetch 需要 embedding，用 Ghost Agent 的模型还是单独一个 embedding 模型？
3. **隐私考虑**：原始快照包含完整对话，是否有敏感信息需要脱敏后再存储？
4. **跨 Agent 会话识别**：同一话题在 Hermes 和 Claude 上各聊了一次，如何识别为"同一次对话"？
