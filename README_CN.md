[English](README.md) | [简体中文](README_CN.md)

> [!WARNING]
> **🔴 已废弃 (DEPRECATED): KitClaw 已全面升级为 Z-Core。**
> V2 版本的重构和重写已全部完成，所有的运行时底座与技能框架已经合并升级到了 **[Z-Core](https://github.com/cloud99277/Z-Core)** 项目中。请迁移到 Z-Core 以获取大一统 CLI、零依赖中间件、内置 RAG 以及全套 MCP 管理能力。当前仓库停止维护并正式归档。
> 详情请参阅 [迁移指南](https://github.com/cloud99277/Z-Core/blob/main/docs/migration-from-kitclaw.md)。

<div align="center">

# 🐾 KitClaw

**给你的 AI Agent 装上共享记忆、技能运行时与治理层。**

[![Author](https://img.shields.io/badge/Author-Cloud927-blue?style=flat-square)](https://github.com/cloud99277)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Core Skills](https://img.shields.io/badge/核心技能-17-blueviolet?style=flat-square)](#-内置技能)

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
- 🪶 **17 个平台核心 skill + 通过 AI Skills Hub 扩展**：核心开箱即用，生态按需安装

## Project Family：两个关联仓库

KitClaw 是整套体系中的核心平台：

| 仓库 | 角色 | 放什么 |
|---|---|---|
| [`KitClaw`](https://github.com/cloud99277/KitClaw) | 平台运行时 | 17 个核心 skill、RAG 引擎、记忆 runtime、治理、文档 |
| [`ai-skills-hub`](https://github.com/cloud99277/ai-skills-hub) | 公开 skill 集合 | 62 个精选 skill，涵盖编码、研究、发布、自动化 |

KitClaw 是自包含的平台——克隆下来你就拥有完整的运行时（记忆、skill、RAG、治理）。ai-skills-hub 是可选扩展，按需安装。

```text
KitClaw                 = 平台运行时 + 17 个核心 skill + RAG 引擎
ai-skills-hub（公开）    = 62 个额外 skill，按需挑选
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
4. 想要更多 skill？去 [AI Skills Hub](https://github.com/cloud99277/ai-skills-hub) 挑选

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

## Skill Runtime 架构

KitClaw 内置 17 个核心 skill，更大的生态在 AI Skills Hub。

```text
KitClaw/core-skills/       ── install.sh ──> ~/.ai-skills/
ai-skills-hub/             ── 用户选择 ──> ~/.ai-skills/
                                     ├─ ~/.claude/skills -> symlink
                                     ├─ ~/.codex/skills  -> symlink
                                     ├─ ~/.gemini/skills -> symlink
                                     └─ ~/.agents/skills -> symlink
```

### Skill 质量关口

所有进入 KitClaw 的核心 skill 都通过 **skill-admission** 质量关口：

- ✅ Lint 通过（frontmatter、命名、路由）
- ✅ 安全审计通过（无硬编码密钥、无危险命令）
- ✅ 无个人依赖（无硬编码路径或用户专属配置）
- ✅ Agent 无关（适配 Claude、Codex、Gemini 等所有 Agent）
- ✅ 自包含（所有引用文件在 skill 内部存在）
- ✅ 结构干净（无 README.md 或 banner 文件）

```bash
# 检查任意 skill 是否符合收编标准
python3 ~/.ai-skills/skill-admission/scripts/admission_check.py ~/.ai-skills/my-skill
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

## 📦 目录结构

```text
KitClaw/
├── install.sh
├── core-skills/
│   ├── memory-manager/         ← 跨层搜索
│   ├── l2-capture/             ← 会话结论 → L2
│   ├── knowledge-search/       ← L3 混合检索
│   ├── conversation-distiller/ ← 对话 → L3 笔记
│   ├── sync-to-brain/          ← 规则 → brain 注入
│   ├── skill-lint/             ← metadata + 路由质量检查
│   ├── skill-observability/    ← 执行日志
│   ├── skill-security-audit/   ← 静态安全扫描
│   ├── skill-admission/        ← 核心收编质量关口
│   ├── skill-stocktake/        ← 质量审计工作流
│   ├── continuous-learning-v2/ ← 从重复模式学习
│   ├── agent-orchestrator/     ← skill chain 验证
│   ├── runtime-doctor/         ← 跨 Agent 运行时验证
│   ├── runtime-bridge-sync/    ← 跨环境 bridge 同步
│   ├── scheduled-tasks/        ← cron 定时任务管理
│   ├── mcp-export/             ← MCP 兼容工具导出
│   └── l3-sync/                ← 知识库变更自动索引
├── rag-engine/
├── governance/
├── templates/
├── docs/
├── tests/
└── examples/
```

## 📖 内置技能（17 个）

### 记忆层

| Skill | 说明 |
|---|---|
| memory-manager | 一条命令统一搜索 L1、L2、L3 |
| l2-capture | 把对话结论转换成结构化 L2 白板条目 |
| knowledge-search | L3 知识库混合向量 + 全文检索 |
| conversation-distiller | 把对话提炼成可检索的 L3 Markdown 笔记 |
| sync-to-brain | 从对话中同步规则和模式到持久化 brain 注入 |

### Skill 管理

| Skill | 说明 |
|---|---|
| skill-lint | 仓库级 skill metadata、命名、路由质量检查 |
| skill-observability | 记录 skill 执行情况、频率、Agent 统计 |
| skill-security-audit | skill 目录静态安全分析 |
| skill-admission | 核心 skill 收编质量关口 |
| skill-stocktake | 质量审计工作流，含评分和建议 |

### 平台与自动化

| Skill | 说明 |
|---|---|
| continuous-learning-v2 | 从重复模式（≥3次）学习可复用行为 |
| agent-orchestrator | YAML skill chain 验证和规划 |
| runtime-doctor | 跨 Agent 共享运行时合约验证 |
| runtime-bridge-sync | 跨环境 bridge 软链接同步 |
| scheduled-tasks | cron 定时任务管理，支持输出投递 |
|| mcp-export | SKILL.md 元数据导出为 MCP-compatible tools/list JSON |
| l3-sync | 监控知识库目录变更，自动触发增量 RAG 索引 |

### 使用示例

```bash
# 跨层搜索
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词"

# 捕获决策到 L2
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project my-project \
  --from-text "[decision] 使用 JSON + grep 而非 chromadb" \
  --apply

# 提炼对话到 L3
python3 ~/.ai-skills/conversation-distiller/scripts/save_note.py \
  --json /tmp/distill.json --print-json

# 搜索 L3 知识库
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "查询内容" --preset coding

# 记录 skill 执行
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill memory-manager --agent codex --status success

# 导出 MCP 工具列表
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --pretty
```

## 生态：AI Skills Hub

除 17 个核心 skill 外，[AI Skills Hub](https://github.com/cloud99277/ai-skills-hub) 提供 62 个精选 skill：

- **编码**: code-review, python-patterns, golang-patterns, tdd-workflow, e2e-testing, security-scan
- **研究**: deep-research, market-research, project-audit, eval-harness
- **发布**: article-writing, baoyu-html-deck, baoyu-xhs-images, china-content-compliance
- **翻译**: translate, 927-translate-skill
- **自动化**: coding-agent, full-cycle-builder, deployment-patterns
- **更多**: find-skills, tacit-mining, regex-vs-llm-structured-text 等

从 AI Skills Hub 按需安装，不需要的不装。

## ⚙️ RAG 引擎

RAG 引擎是可选的，但它负责把 Markdown 文档变成可语义检索的 L3。

```bash
# 安装 RAG 引擎
bash install.sh --with-rag

# 配置知识库路径
cp rag-engine/config.example.json ~/.ai-memory/config.json
# 编辑 ~/.ai-memory/config.json → 设置 l3_paths

# 首次全量索引
python3 rag-engine/knowledge_index.py --full ~/knowledge-base

# 增量更新
python3 rag-engine/knowledge_index.py --update ~/knowledge-base

# 搜索
python3 rag-engine/knowledge_search.py "查询" --mode hybrid --top 5

# 知识库变更后自动索引（可选）
python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --watch
```

详见 [L3 快速上手](docs/l3-quickstart.md)。

## 文档

- [Memory Architecture](docs/memory-architecture.md)
- [Skill Runtime Architecture](docs/skill-runtime-architecture.md)
- [Skill Specification](docs/skill-specification.md)
- [L3 快速上手](docs/l3-quickstart.md)
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

## 📄 许可证

[MIT](LICENSE)

---

<div align="center">

**Made with ❤️ by [Cloud927](https://github.com/cloud99277)**

</div>
