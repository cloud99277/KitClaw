[English](README.md) | [简体中文](README_CN.md)

<div align="center">

# 🐾 KitClaw

**给你的 AI Agent 装上记忆、技能和治理的全套装备**

[![Author](https://img.shields.io/badge/Author-Cloud927-blue?style=flat-square)](https://github.com/cloud99277)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

KitClaw 是一个开源基础设施工具箱，为你已有的 CLI AI 工具（Claude Code、Gemini CLI、Codex CLI 等）提供它们原本没有的超能力。KitClaw 不创建也不编排 Agent —— 它**增强**你正在使用的 Agent。

## ✨ 特点

- 🧠 **三层记忆模型** — L1（身份画像）、L2（会话白板）、L3（知识库 + RAG 向量检索）
- 🔧 **统一 Skill 框架** — 可执行的 Python/Bash 脚本，配合标准化的 `SKILL.md` 契约
- 📊 **内建可观测性** — 每次 Skill 执行自动记录 JSONL 日志，支持使用统计和未使用 Skill 检测
- 🏛️ **治理工具** — Pre-commit 钩子、文档审计器、知识库宪法规则
- 🪶 **零依赖核心** — L2 记忆基于纯 Python 标准库；RAG 引擎为可选安装

## 🤔 KitClaw 与其他项目的区别

| | **AG2 (AutoGen)** | **AgentLoom** | **KitClaw** |
|---|---|---|---|
| **定位** | 创建和编排 Agent | 跨工具配置同步 | 给已有 Agent 加记忆和技能 |
| **Skill 形态** | 不适用 | Markdown 提示词 | 可执行的 Python/Bash 脚本 |
| **记忆能力** | 无 | 无 | 三层模型（L1/L2/L3） |
| **可观测性** | 无 | 基础遥测 | 执行日志 + 使用报告 |
| **依赖重量** | 重（Python 框架） | Node.js | 核心零依赖，RAG 可选 |

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/cloud99277/kitclaw.git
cd kitclaw

# 安装核心 Skill（零依赖）
bash install.sh

# 可选：安装 RAG 引擎以支持语义搜索
bash install.sh --with-rag
```

安装完成后：

1. 编辑 `~/.ai-memory/config.json` 设置你的知识库路径
2. 复制 `templates/AGENTS.md` 到 `~/AGENTS.md` 并填入你的个人画像
3. 阅读 `docs/memory-architecture.md` 了解三层记忆模型

## 🏗️ 架构

```
┌──────────────────────────────────────────────────────┐
│                      KitClaw                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│  L1 身份层        ~/AGENTS.md（用户画像 + 行为规则）    │
│  ────────────────────────────────────────────────     │
│  L2 会话层        ~/.ai-memory/whiteboard.json       │
│                   （决策 / 行动 / 经验教训）             │
│  ────────────────────────────────────────────────     │
│  L3 知识层        你的 Markdown 知识库 + LanceDB RAG  │
│  ────────────────────────────────────────────────     │
│  技能层           ~/.ai-skills/（软链接）               │
│  ────────────────────────────────────────────────     │
│  可观测层         ~/.ai-skills/.logs/executions.jsonl │
│  ────────────────────────────────────────────────     │
│  治理层           Pre-commit 钩子 + 审计器             │
│                                                      │
│  适配：Claude · Gemini · Codex · 任意 CLI AI          │
└──────────────────────────────────────────────────────┘
```

## 📦 目录结构

```
kitclaw/
├── install.sh                 # 一键安装脚本
├── core-skills/               # 出厂自带的核心 Skill
│   ├── memory-manager/        # L1/L2/L3 检索 + L2 写入 + L3 目录监听
│   ├── l2-capture/            # L2 便捷写入助手
│   ├── knowledge-search/      # L3 语义搜索封装
│   └── skill-observability/   # 执行日志 + 使用报告
├── rag-engine/                # 可选：LanceDB 向量 + FTS 引擎
├── governance/                # Pre-commit 钩子 + 文档审计器
├── templates/                 # 新用户初始化模板
├── docs/                      # 架构和规范文档
├── tests/                     # 测试套件
└── examples/                  # 示例知识库
```

## 📖 核心 Skill

### memory-manager

一条命令搜索全部三层记忆。

```bash
# 搜索所有层
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词"

# 仅搜索 L2 白板
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --layer=L2
```

### l2-capture

从对话中提取决策、行动和经验教训，写入共享白板。

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project my-project \
  --from-text "[decision] 使用 JSON + grep 而非 chromadb" \
  --apply
```

### knowledge-search

基于 LanceDB 向量 + 全文检索的混合语义搜索。

```bash
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "查询内容" --preset coding
```

### skill-observability

追踪哪些 Skill 被使用、使用频率和调用来源。

```bash
# 记录一次执行
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill memory-manager --agent gemini --status success

# 查找未使用的 Skill
python3 ~/.ai-skills/skill-observability/scripts/find-unused.py

# 生成使用报告
python3 ~/.ai-skills/skill-observability/scripts/report.py
```

## ⚙️ RAG 引擎（可选）

RAG 引擎基于 LanceDB 向量和 Tantivy 全文搜索，提供 Markdown 知识库的语义检索能力。

```bash
# 安装 RAG 支持
bash install.sh --with-rag

# 构建索引
python3 rag-engine/knowledge_index.py --update ~/knowledge-base --db-path ~/.lancedb/knowledge

# 搜索
python3 rag-engine/knowledge_search.py "查询" --mode hybrid --top 5
```

## 🔧 编写你自己的 Skill

查看 [docs/skill-specification.md](docs/skill-specification.md) 获取完整规范，或直接用 `templates/SKILL.md.template` 作为起点。

最简单的 Skill 只需 3 个文件：

```
my-skill/
├── SKILL.md           # YAML frontmatter + 使用文档
└── scripts/
    └── my_script.py   # 入口脚本
```

## 📚 各 Agent 配置指南

- [Claude Code](docs/agent-setup/claude.md)
- [Gemini CLI](docs/agent-setup/gemini.md)
- [Codex CLI](docs/agent-setup/codex.md)

## 📄 许可证

[MIT](LICENSE)

---

<div align="center">

**Made with ❤️ by [Cloud927](https://github.com/cloud99277)**

</div>
