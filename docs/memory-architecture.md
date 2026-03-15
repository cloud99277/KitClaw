---
title: "Memory Architecture"
tags: [memory, architecture, knowledge-base]
scope: dev
---

# Memory Architecture — 三层记忆模型

> **所属 Skill**：`memory-manager`
> **文档版本**：v2
> **目标**：解释 L1 / L2 / L3 分别在什么时候触发、适合放什么，以及它们如何和 OpenClaw、Obsidian、共享 skill runtime 协同工作。

---

## 一、总览

KitClaw 把 Agent 记忆拆成三层，不是为了“多存几份数据”，而是为了把不同时间尺度、不同稳定性的内容放到最合适的地方。

```text
L1 = 始终加载的身份与规则
L2 = 跨会话的短结论白板
L3 = 长期稳定的 Markdown 知识库
```

核心设计原则：

1. **规则和用户画像** 不应该和项目知识混在一起
2. **短结论** 不应该强行写成长文档
3. **稳定知识** 不应该只留在某个 Agent 的私有记忆里

---

## 二、三层记忆触发表

| 层级 | 触发时机 | 适合存放 | 不适合存放 | 主要工具 |
|------|---------|---------|-----------|---------|
| **L1 身份层** | Agent 启动时自动加载 | 用户画像、规则、长期偏好、行为边界 | 项目事实、临时 TODO、长文档 | `~/AGENTS.md`、agent 原生配置 |
| **L2 白板层** | 对话中出现值得跨会话保留的短结论 | decision / action / learning | SOP、研究文档、教程、长报告 | `memory-manager`、`l2-capture` |
| **L3 知识层** | 内容已经值得长期保留并支持检索 | 研究、SOP、架构文档、模板、提炼后的对话、Obsidian 笔记 | 太碎的临时想法、尚未定型的草稿 | `knowledge-search`、`conversation-distiller`、watcher/indexer |

---

## 三、L1 身份层

### 定义

L1 是 Agent 每次启动都应立即具备的上下文。

### 典型内容

- 用户画像
- 语言偏好
- 工作方式偏好
- 不要做的事
- 技术环境约束
- 跨项目长期有效的行为规则

### 典型路径

- `~/AGENTS.md`
- `~/.claude/CLAUDE.md`
- `~/.gemini/GEMINI.md`
- `~/.codex/AGENTS.md`

### 为什么它不是 L2 / L3

因为这些内容不是“某次会话的结论”，也不是“某个项目的知识文档”，而是 Agent 的默认运行条件。

---

## 四、L2 白板层

### 定义

L2 是跨会话的短结构化记忆，核心格式是：

- `decision`
- `action`
- `learning`

### 典型触发

- 对话中明确选了 A 而不是 B
- 形成了需要后续跟进的待办
- 实施中发现了以后还会复用的坑或规律

### 典型入口

- `l2-capture`
- `memory-manager/scripts/memory-update.py`

### 适合的内容粒度

L2 应该是**短结论**，不是长文档。

好的例子：

```text
[decision] L3 默认使用 Markdown + LanceDB，不把向量数据库引入 L2。
[action] 给 conversation-distiller 补通用路径配置和测试。
[learning] OpenClaw 私有记忆适合草稿，不适合直接作为共享知识源。
```

不好的例子：

- 一篇完整调研报告
- 一整段长对话原文
- 一篇教程

这些应该放到 L3。

---

## 五、L3 知识层

### 定义

L3 是长期稳定、可被多个 Agent 与人类共同维护的 Markdown 知识库。

### 典型来源

- Obsidian vault
- 项目文档目录
- 研究笔记
- SOP / 模板
- `conversation-distiller` 产出的对话摘要

### 典型入口

- `knowledge-search`
- `conversation-distiller`
- `watch-knowledge-base.py`
- `knowledge_index.py --update`

### 路由原则

当内容满足以下任一条件时，应优先进入 L3：

- 未来会被多次检索
- 需要人工长期维护
- 结构化程度高于 L2
- 已经从会话结论升级为正式知识

---

## 六、OpenClaw 与共享记忆的边界

OpenClaw 自己有私有长期记忆与工作区记忆，但它们不等于共享知识层。

| 存储 | 性质 | 建议用途 | 是否共享 |
|------|------|---------|---------|
| `~/.openclaw/workspace/MEMORY.md` | Agent 私有长期记忆 | Agent 自身偏好、渠道事实、工作习惯 | 否 |
| `~/.openclaw/workspace/memory/*.md` | Agent 私有原始上下文 | 草稿、当天记录、处理中间态 | 否 |
| `~/.ai-memory/whiteboard.json` | 共享 L2 | 短结论、待办、经验教训 | 是 |
| Obsidian / Markdown vault | 共享 L3 | 稳定知识、文档、研究、模板 | 是 |

边界规则：

1. OpenClaw 私有记忆可以先快写，但稳定内容应提升到 L2 或 L3
2. 私有草稿不是共享事实的唯一来源
3. 共享知识最终应该落在 `whiteboard.json` 或 Markdown 知识库中

---

## 七、Obsidian / Markdown 知识库联动

KitClaw 与 Obsidian 的关系，不是“替代编辑器”，而是“把 Markdown 变成共享知识层”。

典型链路：

```text
OpenClaw 私有记忆 / 对话结论
    ↓ 提炼
conversation-distiller 或手工整理
    ↓
Obsidian / Markdown 知识库
    ↓
ensure-knowledge-frontmatter.py
    ↓
knowledge_index.py --update
    ↓
knowledge-search / memory-manager
```

这条链路的好处：

- 人类仍然用 Obsidian 编辑
- Agent 不必全量读库，只做检索
- 多个 Agent 可以共享同一个 L3
- 文档仍然是 Git 文件，可审计、可同步

---

## 八、典型工作流

### 工作流 1：当前会话沉淀成 L2

```text
用户 / Agent 形成一个明确结论
    ↓
l2-capture
    ↓
~/.ai-memory/whiteboard.json
    ↓
后续会话 memory-manager 检索
```

### 工作流 2：当前会话升级成 L3 文档

```text
问题已解决，过程值得复用
    ↓
conversation-distiller
    ↓
写入 L3 Markdown 目录
    ↓
frontmatter + 增量索引
    ↓
knowledge-search 可检索
```

### 工作流 3：Obsidian 文档自动进入共享知识

```text
人在 Obsidian 中修改 Markdown
    ↓
watch-knowledge-base.py 发现变化
    ↓
自动补全 frontmatter
    ↓
增量更新 LanceDB 索引
    ↓
所有 Agent 都能搜到
```

---

## 九、为什么 L2 和 L3 要分开

因为它们解决的是不同问题：

- **L2** 优化的是“跨会话短结论复用”
- **L3** 优化的是“长期知识沉淀与检索”

如果把两者混成一个层：

- 要么短结论被淹没在长文档里
- 要么长文档被强行塞进结构化 JSON

分层之后：

- L2 保持短、快、可直接回读
- L3 保持人类可维护、Agent 可检索

---

## 十、路径与同步

### L2

- 数据目录：`~/.ai-memory/`
- 白板：`~/.ai-memory/whiteboard.json`
- 配置：`~/.ai-memory/config.json`

### L3

- 路径来源：`~/.ai-memory/config.json` 的 `l3_paths`
- 默认模板值：`~/knowledge-base`
- 可接 Obsidian、本地 Markdown 目录、项目 docs 目录

### 同步建议

- `~/.ai-memory/` 单独 Git 管理
- L3 Markdown 知识库单独 Git 管理
- skill 仓库与数据仓库分离

---

## 十一、设计约束

1. **数据与工具分离**：记忆数据不和 skill 仓库绑定
2. **L2 优先结构化短结论**：不把它变成 mini knowledge base
3. **L3 优先 Markdown**：保持人类可编辑、Git 友好
4. **按需加载，不全量加载**：Agent 主要通过 search/retrieval 使用 L2/L3
5. **共享知识优先提升**：稳定内容不要只留在某个 Agent 的私有记忆里
