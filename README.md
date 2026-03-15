[English](README.md) | [简体中文](README_CN.md)

<div align="center">

# 🐾 KitClaw

**Power up your AI agents with shared memory, skills, and governance.**

[![Author](https://img.shields.io/badge/Author-Cloud927-blue?style=flat-square)](https://github.com/cloud99277)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

KitClaw is an open-source infrastructure toolkit that gives your existing CLI AI agents (Claude Code, Gemini CLI, Codex CLI, etc.) superpowers they don't have out of the box. It doesn't create or orchestrate agents — it **enhances** the ones you already use.

## ✨ Features

- 🧠 **Three-Layer Memory** — L1 (identity profile), L2 (session whiteboard), L3 (knowledge base with RAG)
- 🔧 **Unified Skill Framework** — Executable Python/Bash scripts with standardized `SKILL.md` contracts
- 📊 **Built-in Observability** — Automatic JSONL execution logs for every skill run, usage reports, unused skill detection
- 🏛️ **Governance Tools** — Pre-commit hooks, document auditing, and constitutional rules for your knowledge base
- 🪶 **Zero-Dependency Core** — L2 memory runs on pure Python stdlib; RAG engine is optional

## 🤔 How is KitClaw Different?

| | **AG2 (AutoGen)** | **AgentLoom** | **KitClaw** |
|---|---|---|---|
| **Purpose** | Create & orchestrate agents | Sync config across tools | Add memory & skills to existing agents |
| **Skills** | N/A | Markdown prompts | Executable Python/Bash scripts |
| **Memory** | None built-in | None | Three-layer model (L1/L2/L3) |
| **Observability** | None | Basic telemetry | Execution logs + usage reports |
| **Dependencies** | Heavy (Python framework) | Node.js | Zero for core, optional for RAG |

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/cloud99277/kitclaw.git
cd kitclaw

# Install core skills (zero dependencies)
bash install.sh

# Optional: Install RAG engine for semantic search
bash install.sh --with-rag
```

After installation:

1. Edit `~/.ai-memory/config.json` to set your knowledge base path
2. Copy `templates/AGENTS.md` to `~/AGENTS.md` and fill in your profile
3. Read `docs/memory-architecture.md` to understand the memory model

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                      KitClaw                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│  L1 Identity      ~/AGENTS.md (user profile + rules) │
│  ────────────────────────────────────────────────     │
│  L2 Session       ~/.ai-memory/whiteboard.json       │
│                   (decisions / actions / learnings)   │
│  ────────────────────────────────────────────────     │
│  L3 Knowledge     Your Markdown vault + LanceDB RAG  │
│  ────────────────────────────────────────────────     │
│  Skills           ~/.ai-skills/ (symlinked)           │
│  ────────────────────────────────────────────────     │
│  Observability    ~/.ai-skills/.logs/executions.jsonl │
│  ────────────────────────────────────────────────     │
│  Governance       Pre-commit hooks + Auditor          │
│                                                      │
│  Works with: Claude · Gemini · Codex · Any CLI AI    │
└──────────────────────────────────────────────────────┘
```

## 📦 Directory Structure

```
kitclaw/
├── install.sh                 # One-command installer
├── core-skills/               # Ships with KitClaw
│   ├── memory-manager/        # L1/L2/L3 search + L2 write + L3 watcher
│   ├── l2-capture/            # Convenient L2 write helper
│   ├── knowledge-search/      # L3 semantic search wrapper
│   └── skill-observability/   # Execution logging + usage reports
├── rag-engine/                # Optional: LanceDB vector + FTS engine
├── governance/                # Pre-commit hooks + document auditor
├── templates/                 # Starter files for new users
├── docs/                      # Architecture & specification docs
├── tests/                     # Test suite
└── examples/                  # Sample knowledge vault
```

## 📖 Core Skills

### memory-manager

Search across all three memory layers with a single command.

```bash
# Search everything
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "keyword"

# Search only L2 whiteboard
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "keyword" --layer=L2
```

### l2-capture

Extract decisions, actions, and learnings from conversations into the shared whiteboard.

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project my-project \
  --from-text "[decision] Use JSON + grep instead of chromadb" \
  --apply
```

### knowledge-search

Semantic search over your Markdown knowledge base using hybrid vector + full-text search.

```bash
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "query" --preset coding
```

### skill-observability

Track which skills are used, how often, and by which agent.

```bash
# Log an execution
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill memory-manager --agent gemini --status success

# Find unused skills
python3 ~/.ai-skills/skill-observability/scripts/find-unused.py

# Generate usage report
python3 ~/.ai-skills/skill-observability/scripts/report.py
```

## ⚙️ RAG Engine (Optional)

The RAG engine provides semantic search over Markdown knowledge bases using LanceDB vectors and Tantivy full-text search.

```bash
# Install with RAG support
bash install.sh --with-rag

# Build index
python3 rag-engine/knowledge_index.py --update ~/knowledge-base --db-path ~/.lancedb/knowledge

# Search
python3 rag-engine/knowledge_search.py "query" --mode hybrid --top 5
```

## 🛠️ Contributor Setup

```bash
# Create a local development environment
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Install the repo pre-commit hook
bash governance/hooks/install.sh

# Run the test suite
.venv/bin/python -m pytest tests
```

## 🔧 Writing Your Own Skills

See [docs/skill-specification.md](docs/skill-specification.md) for the full specification, or use `templates/SKILL.md.template` as a starting point.

A minimal skill is just 3 files:

```
my-skill/
├── SKILL.md           # YAML frontmatter + usage docs
└── scripts/
    └── my_script.py   # Entry point
```

## 📚 Agent Setup Guides

- [Claude Code](docs/agent-setup/claude.md)
- [Gemini CLI](docs/agent-setup/gemini.md)
- [Codex CLI](docs/agent-setup/codex.md)

## 📄 License

[MIT](LICENSE)

---

<div align="center">

**Made with ❤️ by [Cloud927](https://github.com/cloud99277)**

</div>
