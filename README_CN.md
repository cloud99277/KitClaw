[English](README.md) | [简体中文](README_CN.md)

<div align="center">

# 🐾 KitClaw

**给你的 AI Agent 装上共享记忆、技能运行时与治理层。**

[![Author](https://img.shields.io/badge/Author-Cloud927-blue?style=flat-square)](https://github.com/cloud99277)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

KitClaw 是一个面向现有 CLI Agent 的开源基础设施工具箱，适配 Claude Code、Gemini CLI、Codex CLI、OpenClaw 以及其他终端型 Agent。

它不负责创建 Agent，也不负责多 Agent 编排。它负责为你已经在用的 Agent 提供一套共享运行时：

- `L1 / L2 / L3` 三层记忆
- 可执行的统一 skill 体系
- Markdown 知识库的入库与检索
- skill 执行可观测性
- 仓库级治理与校验

## ✨ 特点

- 🧠 **三层记忆模型**：L1 身份层、L2 会话白板、L3 Markdown 知识库 + 可选 RAG
- 🔧 **统一 Skill Runtime**：`SKILL.md` 路由契约 + `scripts/` 可执行入口
- 📝 **对话沉淀到知识库**：把刚完成的对话提炼成 L3 文档并自动入库
- 📊 **内建可观测性**：JSONL 执行日志、使用统计与报告
- 🏛️ **治理能力**：frontmatter 校验、文档审计、仓库卫生检查
- 🪶 **核心精简，生态可扩展**：公开仓库只保留通用核心，更大的 skill 生态放在共享 skills 仓库

## Project Family：三个关联仓库怎么分工

KitClaw 只是整套体系中的一个公开内核。三个关联仓库各有职责：

| 仓库 | 角色 | 放什么 |
|---|---|---|
| [`KitClaw`](https://github.com/cloud99277/KitClaw) | 公开稳定发行版 | 核心 skill、记忆 runtime、治理、文档 |
| `927-ai-skills`（private） | 完整运行时 skill 仓库 | 更大的生产级 skill 目录，供多 Agent 共用，但仓库本身不公开 |
| `agent-os-knowledge-base`（private） | L3 检索引擎上游 | 知识索引/搜索引擎的私有上游演进仓库 |

推荐这样理解：

```text
927-ai-skills（private）           = 更大的 skill 生态
agent-os-knowledge-base（private） = L3 检索引擎上游
KitClaw                  = 面向公开分发的稳定核心组合
```

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/cloud99277/KitClaw.git
cd KitClaw

# 安装核心 runtime（零依赖核心）
bash install.sh

# 可选：安装 RAG 运行时
bash install.sh --with-rag
```

安装后：

1. 编辑 `~/.ai-memory/config.json`，把 `l3_paths` 指向你的 Markdown 知识库
2. 复制 `templates/AGENTS.md` 到 `~/AGENTS.md`，填写用户画像和路由规则
3. 阅读 [docs/memory-architecture.md](docs/memory-architecture.md) 和 [docs/skill-runtime-architecture.md](docs/skill-runtime-architecture.md)

## 三层记忆是怎么触发的

三层记忆不只是三个目录，而是三种不同的触发场景。

| 层级 | 触发时机 | 最适合放什么 | 主入口 |
|---|---|---|---|
| **L1 身份层** | Agent 会话启动时自动加载 | 用户画像、行为规则、长期偏好 | `~/AGENTS.md`、各 agent 原生配置 |
| **L2 白板层** | 需要把短结论跨会话保留时 | decision / action / learning | `memory-manager`、`l2-capture` |
| **L3 知识层** | 内容已经值得长期保留或检索时 | 研究、SOP、架构文档、提炼后的对话、Obsidian 笔记 | `knowledge-search`、`conversation-distiller`、watcher/indexer |

### 典型路由

1. **当前会话得出短结论 → L2**
   当你只是想记一个决策、待办或经验教训时，用 `l2-capture`。

2. **这段对话值得长期沉淀 → L3**
   当问题已经解决，且过程/结论值得以后复用时，用 `conversation-distiller`。

3. **Obsidian / Markdown 文档更新 → L3 索引**
   当知识库文档发生变化时，用 watcher 或增量索引把它们变成全局可检索知识。

## OpenClaw + Obsidian 是怎么联动的

OpenClaw 和 Obsidian 都很适合接到 KitClaw 里，但职责不同。

```text
OpenClaw 私有记忆 / 工作区草稿
    ↓ 提炼或正式化
Obsidian / Markdown 知识库
    ↓ 自动补 frontmatter
KitClaw rag-engine 增量索引
    ↓
knowledge-search / memory-manager
    ↓
Claude / Gemini / Codex / OpenClaw 统一检索共享 L3
```

边界建议：

- **OpenClaw 私有记忆**：放草稿、当天上下文、Agent 私有工作状态
- **Obsidian / L3**：放稳定、共享、可人工编辑的知识
- **KitClaw**：把这些 Markdown 文档转成所有 Agent 都能搜的共享知识层

## Skill Runtime 架构

KitClaw 的 skill 不是 prompt 文件，而是一套可执行 runtime。

```text
KitClaw/core-skills/  ── install.sh ──> ~/.ai-skills/
                                     ├─ ~/.claude/skills -> symlink
                                     ├─ ~/.codex/skills  -> symlink
                                     ├─ ~/.gemini/skills -> symlink
                                     └─ ~/.agents/skills -> symlink
```

执行链路：

```text
Agent 请求
  -> 根据 SKILL.md 路由
  -> 执行 scripts/<entrypoint>
  -> 按需读写 L2 / L3
  -> 写入 observability 日志
  -> 受 governance 规则约束
```

一个 skill 的最小单元通常包括：

- `SKILL.md`：路由元数据与使用说明
- `scripts/`：实际执行逻辑
- `references/`：可选参考文档/模板
- `tests/`：可选测试

## 📦 目录结构

```text
KitClaw/
├── install.sh
├── core-skills/
│   ├── memory-manager/
│   ├── l2-capture/
│   ├── conversation-distiller/
│   ├── knowledge-search/
│   ├── skill-observability/
│   ├── mcp-export/
│   └── skill-security-audit/
├── rag-engine/
├── governance/
├── templates/
├── docs/
├── tests/
└── examples/
```

## 📖 内置 Skill

KitClaw 不只内置运行时记忆 skill，也内置一小组适合开源共享仓库的治理 /
互操作 skill。

### 运行时记忆 Skill

### memory-manager

一条命令统一搜索 L1、L2、L3。

```bash
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词"
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --layer=L2
```

### l2-capture

把原始对话结论转换成结构化 L2 条目。

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project my-project \
  --from-text "[decision] 使用 JSON + grep 而非 chromadb" \
  --apply
```

### conversation-distiller

把刚完成的对话提炼成一份 L3 Markdown 笔记。

```bash
cat >/tmp/distill.json <<'JSON'
{
  "title": "[Dev] 端口冲突排查",
  "content": "## 背景与起因\n...\n\n## 最终方案\n..."
}
JSON

python3 ~/.ai-skills/conversation-distiller/scripts/save_note.py \
  --json /tmp/distill.json \
  --print-json
```

### knowledge-search

用向量 + 全文混合检索 L3 知识库。

```bash
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "查询内容" --preset coding
```

### skill-observability

记录 skill 执行情况，并统计使用情况。

```bash
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill memory-manager --agent codex --status success
```

### 治理与互操作 Skill

### mcp-export

把 KitClaw skill 元数据导出成 MCP-compatible `tools/list` JSON。

```bash
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --pretty
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py \
  --skills-dir ~/.ai-skills \
  --output /tmp/tools.json
```

### skill-security-audit

对单个 skill 或整个共享 skill 仓库做静态安全检查。

```bash
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py --all
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py \
  ~/.ai-skills/conversation-distiller \
  --json
```

## 值得搭配的生态 Skill

KitClaw 故意把公开核心保持得比较小。更大的 skill 生态目前继续放在 private 的 `927-ai-skills` 仓库里，KitClaw 只公开其中可移植、可共享的子集。

尤其值得搭配的生态 skill：

- `skill-lint`：对共享 skill 仓库做 metadata / routing 级 lint
- `history-reader` / `history-chat`：各 agent 的历史对话 adapter
- private 的 `927-ai-skills` 中更丰富的研究、内容生产、发布与自动化 skill

这些 skill 很有价值，但不是 KitClaw 核心 runtime 的硬依赖。

## ⚙️ RAG 引擎

RAG 引擎是可选的，但它负责把 Markdown 文档变成可语义检索的 L3。

```bash
# 安装运行时
bash install.sh --with-rag

# 构建或更新索引
python3 rag-engine/knowledge_index.py --update ~/knowledge-base --db-path ~/.lancedb/knowledge

# 直接查询
python3 rag-engine/knowledge_search.py "查询" --mode hybrid --top 5
```

## 文档

- [Memory Architecture](docs/memory-architecture.md)
- [Skill Runtime Architecture](docs/skill-runtime-architecture.md)
- [Skill Specification](docs/skill-specification.md)
- [Governance](docs/governance.md)

## 🛠️ 贡献者环境

```bash
# 创建开发环境
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 安装仓库 hook
bash governance/hooks/install.sh

# 跑验证
.venv/bin/python -m pytest tests
.venv/bin/ruff check .
.venv/bin/pyright
```

## 📚 Agent 配置指南

- [Claude Code](docs/agent-setup/claude.md)
- [Gemini CLI](docs/agent-setup/gemini.md)
- [Codex CLI](docs/agent-setup/codex.md)

## 📄 License

[MIT](LICENSE)

---

<div align="center">

**Made with ❤️ by [Cloud927](https://github.com/cloud99277)**

</div>
