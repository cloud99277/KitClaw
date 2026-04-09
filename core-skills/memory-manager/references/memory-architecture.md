---
name: memory-architecture
---

# Memory Architecture Reference

> Short reference for the `memory-manager` skill.
> Full design doc: `docs/memory-architecture.md`

## Three Layers

| Layer | Purpose | Storage | Write policy |
|------|---------|---------|--------------|
| L1 | Identity, user profile, shared rules | `~/AGENTS.md`, agent-specific config files | Manual only |
| L2 | Cross-session decisions / actions / learnings | `~/.ai-memory/whiteboard.json` | `memory-update.py` or `l2-capture.py` |
| L3 | Stable Markdown knowledge and research | User-configured Markdown paths + LanceDB index | User or other skills |

## Boundaries

- Put reusable short conclusions in L2.
- Put stable documents, SOPs, reports, and research in L3.
- Keep agent-private scratch memory out of the shared store.

## Storage Paths

- L2 data: `~/.ai-memory/`
- L2 whiteboard: `~/.ai-memory/whiteboard.json`
- L3 config: `~/.ai-memory/config.json`
- Installed skills: `~/.ai-skills/`

## Sync Strategy

- Sync `~/.ai-memory/` with Git if you want cross-machine L2 state.
- Keep `~/.ai-skills/` and `~/.ai-memory/` as separate repos so tool updates do not touch data.