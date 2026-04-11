[English](README.md) | [简体中文](README_CN.md)

> [!WARNING]
> **🔴 DEPRECATED: KitClaw has been superseded by Z-Core.**
> The V2 iteration has been successfully completed and the entire runtime + skill framework has been unified into **[Z-Core](https://github.com/cloud99277/Z-Core)**. Please migrate to Z-Core for an all-in-one CLI, zero-dependency middleware, integrated RAG, and MCP management. This repository will receive no further updates.
> See [Migration Guide](https://github.com/cloud99277/Z-Core/blob/main/docs/migration-from-kitclaw.md) for upgrade instructions.

<div align="center">

# 🐾 KitClaw

**Power up your AI agents with shared memory, skills, and governance.**

[![Author](https://img.shields.io/badge/Author-Cloud927-blue?style=flat-square)](https://github.com/cloud99277)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Core Skills](https://img.shields.io/badge/Core_Skills-17-blueviolet?style=flat-square)](#-bundled-skills)

</div>

KitClaw is an open-source infrastructure toolkit for existing CLI agents such as Claude Code, Gemini CLI, Codex CLI, OpenClaw, and similar terminal-native assistants.

It does not create or orchestrate agents. It gives the agents you already use a shared runtime for:

- `L1 / L2 / L3` memory
- portable executable skills
- knowledge-base ingestion and retrieval
- execution observability
- repository-level governance

## ✨ Features

- 🧠 **Three-Layer Memory**: L1 identity, L2 session whiteboard, L3 Markdown knowledge base with optional RAG
- 🔧 **Unified Skill Runtime**: `SKILL.md` contracts plus executable `scripts/` entry points
- 📝 **Conversation-to-Knowledge Distillation**: save the current conversation into L3 and auto-ingest it
- 📊 **Built-in Observability**: JSONL execution logs and usage reports
- 🏛️ **Governance**: frontmatter validation, document auditing, and repo hygiene checks
- 🪶 **Curated Core**: 17 platform-essential skills included, plus a larger ecosystem via [AI Skills Hub](https://github.com/cloud99277/ai-skills-hub)

## Project Family

KitClaw is one part of a larger system:

| Repository | Role | What lives there |
|---|---|---|
| [`KitClaw`](https://github.com/cloud99277/KitClaw) | Platform runtime | 17 core skills, RAG engine, memory runtime, governance, docs |
| [`ai-skills-hub`](https://github.com/cloud99277/ai-skills-hub) | Public skill collection | 62 curated skills for coding, research, publishing, automation |

KitClaw is the self-contained platform — clone it and you have everything you need (memory, skills, RAG, governance). ai-skills-hub is optional extras, pick what you need.

```text
KitClaw                 = platform runtime + 17 core skills + RAG engine
ai-skills-hub (public)  = 62 extra skills, pick what you need
```

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/cloud99277/KitClaw.git
cd KitClaw

# Install core skills (zero-dependency core runtime)
bash install.sh

# Optional: install the RAG engine runtime
bash install.sh --with-rag
```

After installation:

1. Edit `~/.ai-memory/config.json` and point `l3_paths` to your Markdown knowledge base.
2. Copy `templates/AGENTS.md` to `~/AGENTS.md` and fill in your profile and routing rules.
3. Read [docs/memory-architecture.en.md](docs/memory-architecture.en.md) and [docs/skill-runtime-architecture.en.md](docs/skill-runtime-architecture.en.md).
4. Want more skills? Browse [AI Skills Hub](https://github.com/cloud99277/ai-skills-hub) and install what you need.

## How Three-Layer Memory Works

The three layers are not just storage locations. They are triggered by different situations.

| Layer | Trigger | Best for | Main tools |
|---|---|---|---|
| **L1 Identity** | Loaded when the agent session starts | profile, rules, preferences, behavior defaults | `~/AGENTS.md`, agent-native config |
| **L2 Whiteboard** | Triggered when you want to keep a short reusable conclusion across sessions | decisions, actions, learnings | `memory-manager`, `l2-capture` |
| **L3 Knowledge** | Triggered when content should become stable documentation or searchable notes | research, SOPs, architecture docs, distilled conversations, Obsidian notes | `knowledge-search`, `conversation-distiller`, watcher/indexer |

### Typical Memory Routes

1. **Session conclusion → L2**
   Use `l2-capture` when a conversation produces a clear decision, next action, or reusable lesson.

2. **Solved conversation → L3**
   Use `conversation-distiller` when the result deserves a structured Markdown note that should remain searchable later.

3. **Markdown vault / Obsidian update → L3 index**
   Use the watcher or run incremental indexing when notes change in your knowledge base.

## Skill Runtime Architecture

KitClaw ships 17 core skills. The broader ecosystem lives in AI Skills Hub.

```text
KitClaw/core-skills/       ── install.sh ──> ~/.ai-skills/
ai-skills-hub/             ── user selects ──> ~/.ai-skills/
                                         ├─ ~/.claude/skills -> symlink
                                         ├─ ~/.codex/skills  -> symlink
                                         ├─ ~/.gemini/skills -> symlink
                                         └─ ~/.agents/skills -> symlink
```

### Skill Quality Gate

All skills bundled in KitClaw pass the **skill-admission** quality gate:

- ✅ Lint passed (frontmatter, naming, routing)
- ✅ Security audit passed (no hardcoded secrets, no dangerous commands)
- ✅ No personal dependencies (no hardcoded paths or user-specific config)
- ✅ Agent-agnostic (works across Claude, Codex, Gemini, etc.)
- ✅ Self-contained (all referenced files exist within the skill)
- ✅ Clean structure (no README.md or banner files)

```bash
# Check any skill against admission standards
python3 ~/.ai-skills/skill-admission/scripts/admission_check.py ~/.ai-skills/my-skill
```

At execution time:

```text
Agent request
  -> route to a skill via SKILL.md
  -> run scripts/<entrypoint>
  -> optionally read/write L2 or L3
  -> write observability log
  -> stay inside governance constraints
```

## 📦 Directory Structure

```text
KitClaw/
├── install.sh
├── core-skills/
│   ├── memory-manager/         ← cross-layer search
│   ├── l2-capture/             ← session conclusion → L2
│   ├── knowledge-search/       ← L3 hybrid retrieval
│   ├── conversation-distiller/ ← conversation → L3 note
│   ├── sync-to-brain/          ← rules → brain injection
│   ├── skill-lint/             ← metadata + routing quality
│   ├── skill-observability/    ← execution logging
│   ├── skill-security-audit/   ← static security checks
│   ├── skill-admission/        ← quality gate for core inclusion
│   ├── skill-stocktake/        ← quality audit workflow
│   ├── continuous-learning-v2/ ← learn from repeated patterns
│   ├── agent-orchestrator/     ← skill chain validation
│   ├── runtime-doctor/         ← cross-agent runtime validation
│   ├── runtime-bridge-sync/    ← bridge environment sync
│   ├── scheduled-tasks/        ← cron job management
│   ├── mcp-export/             ← MCP-compatible tool export
│   └── l3-sync/                ← auto-index L3 on file changes
├── rag-engine/
├── governance/
├── templates/
├── docs/
├── tests/
└── examples/
```

## 📖 Bundled Skills

KitClaw bundles 17 platform-essential skills, organized by function.

### Memory Layer

| Skill | Description |
|---|---|
| memory-manager | Cross-layer search across L1, L2, L3 from one command |
| l2-capture | Convert conversation conclusions into structured L2 whiteboard entries |
| knowledge-search | Hybrid vector + full-text retrieval for L3 knowledge base |
| conversation-distiller | Turn finished conversations into searchable L3 Markdown notes |
| sync-to-brain | Sync rules and patterns from conversations into persistent brain injection |

### Skill Management

| Skill | Description |
|---|---|
| skill-lint | Repository-wide lint for skill metadata, naming, and routing quality |
| skill-observability | Track which skills run, how often, and by which agent |
| skill-security-audit | Static security analysis against skill directories |
| skill-admission | Quality gate for skills to be included in core |
| skill-stocktake | Quality audit workflow with scoring and recommendations |

### Platform & Automation

| Skill | Description |
|---|---|
| continuous-learning-v2 | Learn reusable behaviors from repeated patterns (3+ occurrences) |
| agent-orchestrator | Validate and plan linear skill chains defined in YAML |
| runtime-doctor | Validate shared runtime contract across agents (WSL, CLI, desktop) |
| runtime-bridge-sync | Sync curated bridge symlinks for cross-environment access |
| scheduled-tasks | Manage periodic tasks using cron with output delivery |
| mcp-export | Export SKILL.md frontmatter to MCP-compatible tools/list JSON |
| l3-sync | Watch knowledge base dirs and auto-trigger incremental RAG indexing |

### Usage Examples

```bash
# Search across all memory layers
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "keyword"

# Capture a decision to L2
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project my-project \
  --from-text "[decision] Use JSON + grep instead of chromadb" \
  --apply

# Distill a conversation to L3
python3 ~/.ai-skills/conversation-distiller/scripts/save_note.py \
  --json /tmp/distill.json --print-json

# Search L3 knowledge base
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "query" --preset coding

# Log skill execution
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill memory-manager --agent codex --status success

# Export MCP-compatible tool list
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --pretty
```

## Ecosystem: AI Skills Hub

Beyond the 17 core skills, [AI Skills Hub](https://github.com/cloud99277/ai-skills-hub) provides 62 additional curated skills across categories:

- **Coding**: code-review, python-patterns, golang-patterns, tdd-workflow, e2e-testing, security-scan
- **Research**: deep-research, market-research, project-audit, eval-harness
- **Publishing**: article-writing, baoyu-html-deck, baoyu-xhs-images, china-content-compliance
- **Translation**: translate, 927-translate-skill
- **Automation**: coding-agent, full-cycle-builder, deployment-patterns
- **And more**: find-skills, tacit-mining, regex-vs-llm-structured-text, etc.

Install skills from AI Skills Hub selectively — only what you need.

## ⚙️ RAG Engine

The RAG engine is optional, but it is what turns Markdown knowledge into semantic L3 retrieval.

```bash
# Install the RAG engine
bash install.sh --with-rag

# Configure your knowledge base paths
cp rag-engine/config.example.json ~/.ai-memory/config.json
# Edit ~/.ai-memory/config.json → set l3_paths

# First-time full index
python3 rag-engine/knowledge_index.py --full ~/knowledge-base

# Incremental update
python3 rag-engine/knowledge_index.py --update ~/knowledge-base

# Search
python3 rag-engine/knowledge_search.py "query" --mode hybrid --top 5

# Auto-index on file changes (optional)
python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --watch
```

See [L3 Quick Start](docs/l3-quickstart.md) for the complete 30-minute walkthrough.

## Docs

- [Memory Architecture](docs/memory-architecture.en.md)
- [Skill Runtime Architecture](docs/skill-runtime-architecture.en.md)
- [Skill Specification](docs/skill-specification.md)
- [L3 Quick Start](docs/l3-quickstart.md)
- [Governance](docs/governance.md)

## 🛠️ Contributor Setup

```bash
# Create a local development environment
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Install the repository hook
bash governance/hooks/install.sh

# Run verification
.venv/bin/python -m pytest tests
.venv/bin/ruff check .
.venv/bin/pyright
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
