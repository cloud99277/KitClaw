---
title: "Memory Architecture"
tags: [memory, architecture, knowledge-base]
scope: dev
---

# Memory Architecture

> English companion to [`memory-architecture.md`](memory-architecture.md).
> Goal: explain when L1 / L2 / L3 are triggered, what belongs in each layer,
> and how they work with OpenClaw, Obsidian, and the shared skill runtime.

---

## 1. Overview

KitClaw splits agent memory into three layers, not to duplicate data, but to
match different time horizons and stability levels with the right storage model.

```text
L1 = always-loaded identity and rules
L2 = short cross-session whiteboard conclusions
L3 = long-lived Markdown knowledge base
```

Core design rules:

1. Identity and behavior defaults should not be mixed with project knowledge.
2. Short conclusions should not be forced into long-form documents.
3. Stable knowledge should not remain trapped in one agent's private memory.

---

## 2. Trigger Table

| Layer | Trigger | Good fit | Bad fit | Main tools |
| --- | --- | --- | --- | --- |
| **L1 Identity** | loaded automatically when an agent session starts | profile, rules, long-term preferences, operating boundaries | project facts, temporary TODOs, long docs | `~/AGENTS.md`, agent-native config |
| **L2 Whiteboard** | a short conclusion should survive across sessions | decisions, actions, learnings | SOPs, research docs, tutorials, long reports | `memory-manager`, `l2-capture` |
| **L3 Knowledge** | content is now stable enough to preserve and search | research, SOPs, architecture docs, templates, distilled conversations, Obsidian notes | tiny temporary thoughts, unfinished drafts | `knowledge-search`, `conversation-distiller`, watcher/indexer |

---

## 3. L1 Identity

L1 is the context an agent should always have at startup.

Typical content:

- user profile
- language preference
- working style preferences
- things the agent should not do
- environment constraints
- long-lived behavior rules that apply across projects

Typical paths:

- `~/AGENTS.md`
- `~/.claude/CLAUDE.md`
- `~/.gemini/GEMINI.md`
- `~/.codex/AGENTS.md`

This is not L2 or L3 because it is neither a per-session conclusion nor a
project-specific knowledge document. It is the default operating context.

---

## 4. L2 Whiteboard

L2 is a cross-session layer for short structured memory. The core shapes are:

- `decision`
- `action`
- `learning`

Typical triggers:

- the conversation explicitly chose A instead of B
- a next step should be carried into later sessions
- implementation exposed a reusable pitfall or pattern

Typical entry points:

- `l2-capture`
- `memory-manager/scripts/memory-update.py`

L2 should stay short. It is for concise conclusions, not documents.

Good examples:

```text
[decision] Use Markdown + LanceDB for L3 and keep vectors out of L2.
[action] Add generic path configuration and tests to conversation-distiller.
[learning] OpenClaw private memory is fine for drafts, but not as a shared source of truth.
```

Bad examples:

- a full research report
- a full raw conversation transcript
- a tutorial

Those should move to L3.

---

## 5. L3 Knowledge

L3 is the long-lived Markdown knowledge base that can be maintained by both
humans and multiple agents.

Typical sources:

- an Obsidian vault
- project documentation folders
- research notes
- SOPs and templates
- notes produced by `conversation-distiller`

Typical entry points:

- `knowledge-search`
- `conversation-distiller`
- `watch-knowledge-base.py`
- `knowledge_index.py --update`

Route content to L3 when any of these is true:

- it will likely be searched again later
- humans should maintain it over time
- it is more structured than an L2 note
- it has graduated from a conversation conclusion into stable knowledge

---

## 6. Boundary Between OpenClaw and Shared Memory

OpenClaw has its own private long-term memory and workspace memory, but that is
not the same thing as the shared knowledge layer.

| Storage | Nature | Best use | Shared? |
| --- | --- | --- | --- |
| `~/.openclaw/workspace/MEMORY.md` | agent-private long-term memory | agent preferences, channel facts, work habits | no |
| `~/.openclaw/workspace/memory/*.md` | private raw context | drafts, day-level notes, in-progress state | no |
| `~/.ai-memory/whiteboard.json` | shared L2 | short conclusions, TODOs, lessons learned | yes |
| Obsidian / Markdown vault | shared L3 | stable knowledge, docs, research, templates | yes |

Boundary rules:

1. OpenClaw private memory is fine for quick capture, but stable content should
   be promoted into L2 or L3.
2. Private drafts should never be the only source of shared facts.
3. Shared knowledge should eventually live in `whiteboard.json` or the Markdown
   knowledge base.

---

## 7. Obsidian / Markdown Integration

KitClaw does not replace Obsidian. It turns Markdown into a shared knowledge
layer that multiple agents can search.

Typical flow:

```text
OpenClaw private memory / conversation conclusions
    -> distilled manually or by conversation-distiller
    -> Obsidian / Markdown knowledge base
    -> ensure-knowledge-frontmatter.py
    -> knowledge_index.py --update
    -> knowledge-search / memory-manager
```

Why this works well:

- humans keep editing in Obsidian
- agents search instead of loading the whole vault
- multiple agents share one L3
- documents remain Git-friendly files

---

## 8. Typical Workflows

### Workflow 1: current session -> L2

```text
user or agent reaches a clear conclusion
    -> l2-capture
    -> ~/.ai-memory/whiteboard.json
    -> future sessions retrieve it via memory-manager
```

### Workflow 2: current session -> L3 document

```text
problem is solved and worth reusing later
    -> conversation-distiller
    -> write Markdown into L3
    -> frontmatter completion + incremental indexing
    -> searchable via knowledge-search
```

### Workflow 3: Obsidian edits -> shared knowledge

```text
human edits Markdown in Obsidian
    -> watch-knowledge-base.py notices the change
    -> frontmatter is completed automatically
    -> LanceDB index is updated incrementally
    -> all agents can search the result
```

---

## 9. Why L2 and L3 Are Separate

They solve different problems:

- **L2** optimizes for short reusable conclusions across sessions
- **L3** optimizes for long-term knowledge accumulation and retrieval

If they are merged into one layer:

- short conclusions get buried in long documents
- long documents get awkwardly forced into a JSON-like structure

With separation:

- L2 stays short and fast to read back
- L3 stays human-maintainable and agent-searchable

---

## 10. Paths and Sync

### L2

- data root: `~/.ai-memory/`
- whiteboard: `~/.ai-memory/whiteboard.json`
- config: `~/.ai-memory/config.json`

### L3

- path source: `l3_paths` from `~/.ai-memory/config.json`
- default template value: `~/knowledge-base`
- may point to Obsidian vaults, local Markdown folders, or project docs

### Sync guidance

- keep `~/.ai-memory/` in its own Git repo if needed
- keep the L3 Markdown knowledge base in its own Git repo
- keep the skill repo and the memory data repos separate

---

## 11. Design Constraints

1. **Separate data from tools**: memory data should not be tightly coupled to
   the skill repo.
2. **Keep L2 short and structured**: do not turn it into a mini knowledge base.
3. **Prefer Markdown for L3**: keep it human-editable and Git-friendly.
4. **Load on demand, not all at once**: agents should use retrieval instead of
   loading the whole memory space.
5. **Promote shared knowledge upward**: stable content should not remain stuck
   inside one agent's private memory.
