[English](README.md) | [简体中文](README_CN.md)

<div align="center">

# 🐾 KitClaw

**Power up your AI agents with shared memory, skills, and governance.**

[![Author](https://img.shields.io/badge/Author-Cloud927-blue?style=flat-square)](https://github.com/cloud99277)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

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
- 🪶 **Curated Core**: a small public core, with a larger ecosystem living in the shared skills repo

## Project Family

KitClaw is one part of a larger system. The three related repositories have different responsibilities:

| Repository | Role | What lives there |
|---|---|---|
| [`KitClaw`](https://github.com/cloud99277/KitClaw) | Public curated runtime | portable core skills, memory runtime, governance, docs |
| `927-ai-skills` `(private)` | Full runtime skills catalog | broader production skill library used across agents, not publicly published as a repository |
| `agent-os-knowledge-base` `(private)` | L3 engine upstream | the knowledge indexing/search engine as an independently evolving private upstream |

Recommended mental model:

```text
927-ai-skills (private)        = broad skill ecosystem
agent-os-knowledge-base (private) = L3 search/indexing engine upstream
KitClaw              = stable public bundle that combines the core pieces
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

## OpenClaw + Obsidian Workflow

OpenClaw and Obsidian fit naturally into the KitClaw model, but they play different roles.

```text
OpenClaw private memory / workspace notes
    ↓ distill or formalize
Obsidian / Markdown knowledge vault
    ↓ frontmatter completion
KitClaw rag-engine incremental indexing
    ↓
knowledge-search / memory-manager
    ↓
Claude / Gemini / Codex / OpenClaw all query the same shared L3
```

Practical boundary:

- **OpenClaw private memory** is for drafts, day-level context, and agent-private working state.
- **Obsidian / L3** is for stable, shared, human-editable knowledge.
- **KitClaw** turns those Markdown documents into a cross-agent searchable layer.

## Skill Runtime Architecture

KitClaw ships a public core, but the runtime model is bigger than this repo.

```text
KitClaw/core-skills/      ── install.sh ──> ~/.ai-skills/
                                        ├─ ~/.claude/skills -> symlink
                                        ├─ ~/.codex/skills  -> symlink
                                        ├─ ~/.gemini/skills -> symlink
                                        └─ ~/.agents/skills -> symlink
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

This is why KitClaw skills are not just prompt snippets. A skill is a portable runtime unit with:

- metadata and routing in `SKILL.md`
- executable behavior in `scripts/`
- optional references/templates in `references/`
- optional tests

## 📦 Directory Structure

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

## 📖 Bundled Skills

KitClaw bundles both runtime memory skills and a small set of governance /
interoperability skills that are broadly useful when open sourcing a shared
agent runtime.

### Runtime Memory Skills

### memory-manager

Search across L1, L2, and L3 from one command.

```bash
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "keyword"
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "keyword" --layer=L2
```

### l2-capture

Convert raw conversation conclusions into structured L2 entries.

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project my-project \
  --from-text "[decision] Use JSON + grep instead of chromadb" \
  --apply
```

### conversation-distiller

Turn the just-finished conversation into a Markdown note in L3.

```bash
cat >/tmp/distill.json <<'JSON'
{
  "title": "[Dev] Port conflict debugging",
  "content": "## Background\n...\n\n## Final Fix\n..."
}
JSON

python3 ~/.ai-skills/conversation-distiller/scripts/save_note.py \
  --json /tmp/distill.json \
  --print-json
```

### knowledge-search

Search your L3 knowledge base using hybrid vector + full-text retrieval.

```bash
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "query" --preset coding
```

### skill-observability

Track which skills run, how often, and by which agent.

```bash
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill memory-manager --agent codex --status success
```

### Governance and Interoperability Skills

### mcp-export

Export KitClaw skill metadata as MCP-compatible `tools/list` JSON.

```bash
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py --pretty
python3 ~/.ai-skills/mcp-export/scripts/export-mcp.py \
  --skills-dir ~/.ai-skills \
  --output /tmp/tools.json
```

### skill-security-audit

Run static security checks against one skill or an entire shared skills repo.

```bash
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py --all
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py \
  ~/.ai-skills/conversation-distiller \
  --json
```

## Recommended Ecosystem Skills

KitClaw intentionally keeps the public core small. A larger private `927-ai-skills` repo continues to hold the broader ecosystem; KitClaw only publishes the portable subset.

Particularly relevant companion skills:

- `skill-lint`: repository-wide lint for skill metadata and routing quality
- `history-reader` / `history-chat`: agent-specific chat history adapters
- domain-specific research, publishing, and automation skills from the private `927-ai-skills` repo

These are good ecosystem skills, but they are not required for the KitClaw core runtime.

## ⚙️ RAG Engine

The RAG engine is optional, but it is what turns Markdown knowledge into semantic L3 retrieval.

```bash
# Install the runtime
bash install.sh --with-rag

# Build or update the index
python3 rag-engine/knowledge_index.py --update ~/knowledge-base --db-path ~/.lancedb/knowledge

# Query it directly
python3 rag-engine/knowledge_search.py "query" --mode hybrid --top 5
```

## Docs

- [Memory Architecture](docs/memory-architecture.en.md)
- [Skill Runtime Architecture](docs/skill-runtime-architecture.en.md)
- [Skill Specification](docs/skill-specification.md)
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
