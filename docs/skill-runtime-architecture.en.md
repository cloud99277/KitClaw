---
title: "Skill Runtime Architecture"
tags: [skills, runtime, architecture]
scope: dev
---

# Skill Runtime Architecture

> English companion to [`skill-runtime-architecture.md`](skill-runtime-architecture.md).
> Goal: explain how KitClaw relates to the private `927-ai-skills` repo and the
> private `agent-os-knowledge-base` upstream, and how a skill moves from
> repository layout to runtime execution and governance.

---

## 1. Why Treat Skills as Runtime Units

In KitClaw, a skill is not just a prompt and not just a loose script folder.

It is a reusable runtime unit with:

- routing metadata
- executable entry points
- optional reference material
- optional tests
- observability and governance integration

The goal is not merely to "hint the model". The goal is to let multiple agents
share one stable capability surface.

---

## 2. How the Three Related Repositories Divide Responsibilities

| Repository | Position | Main contents | External role |
| --- | --- | --- | --- |
| [`KitClaw`](https://github.com/cloud99277/KitClaw) | Platform runtime | 17 core skills, RAG engine, memory runtime, governance, docs | Public installation entry point |
| [`ai-skills-hub`](https://github.com/cloud99277/ai-skills-hub) | Public skill collection | 62 curated skills (coding, research, publishing, automation) | Public extension layer |
| `agent-os-knowledge-base` `(private)` | L3 engine upstream | Markdown chunking, indexing, retrieval, RAG evolution | Private engine upstream |

Useful mental model:

```text
KitClaw                  = platform runtime + 17 core skills
ai-skills-hub (public)   = broader skill ecosystem, pick what you need
agent-os-knowledge-base  = L3 engine upstream (core code synced to KitClaw/rag-engine/)
```

---

## 3. Why KitClaw Does Not Publish Every Skill

The public core and the private production repos serve different goals.

What fits KitClaw:

- general-purpose behavior
- portability
- low personalization
- low environment coupling
- clear docs and tests

What does not fit KitClaw directly:

- hard dependencies on private directory layouts
- hard dependencies on agent-specific private file formats
- personal workflows, accounts, platforms, or credentials
- skills meant for a very narrow personal scenario

This is why `conversation-distiller` belongs here after de-personalization,
while `history-reader` / `history-chat` still make more sense in the broader
ecosystem layer first.

---

## 4. Runtime Topology

KitClaw maintains its bundled skills in the repo and installs them into a shared
runtime directory on the local machine.

```text
KitClaw/core-skills/
    -> install.sh
    -> ~/.ai-skills/
        |- memory-manager/
        |- l2-capture/
        |- conversation-distiller/
        |- knowledge-search/
        |- skill-observability/
        |- mcp-export/
        `- skill-security-audit/
```

Then the shared runtime is exposed to different agents through symlinks:

```text
~/.claude/skills --\
~/.codex/skills  ---+--> ~/.ai-skills/
~/.gemini/skills --/
~/.agents/skills -/
```

Benefits:

- multiple agents share the same runtime
- only one skill directory needs maintenance
- updates, observability, and governance stay centralized

---

## 5. Standard Skill Structure

```text
<skill-name>/
|- SKILL.md
|- scripts/
|- references/      # optional
|- requirements.txt # optional
`- tests/           # optional
```

### `SKILL.md`

Responsible for:

- routing and trigger guidance
- input/output contract
- when to use and when not to use the skill
- copy-paste level usage examples

### `scripts/`

Responsible for actual behavior, such as:

- search
- writing
- transformation
- indexing
- report generation

### `references/`

Responsible for deeper constraints and background, so `SKILL.md` can stay
focused and readable.

### `tests/`

Responsible for regression-proofing the key behavior of the skill.

---

## 6. Execution Chain

The normal execution chain of a skill looks like this:

```text
user request
  -> agent matches the request against SKILL.md
  -> enters the skill directory and runs scripts/<entrypoint>
  -> produces output and/or reads/writes L2 or L3
  -> writes an observability log
  -> remains bounded by governance rules
```

This chain has four important layers:

1. **Routing**
   `SKILL.md` decides when the skill should be chosen.

2. **Execution**
   `scripts/` decides what the skill actually does.

3. **Observability**
   `skill-observability` records how the runtime is used.

4. **Governance**
   hooks, audits, lint, and security checks keep the quality boundary intact.

---

## 7. Bundled Core vs Public Ecosystem

### Bundled Core Skills (17)

KitClaw currently bundles 17 platform-essential skills:

**Memory**: `memory-manager`, `l2-capture`, `knowledge-search`, `conversation-distiller`, `sync-to-brain`

**Skill Management**: `skill-lint`, `skill-observability`, `skill-security-audit`, `skill-admission`, `skill-stocktake`

**Platform & Automation**: `continuous-learning-v2`, `agent-orchestrator`, `runtime-doctor`, `runtime-bridge-sync`, `scheduled-tasks`, `mcp-export`, `l3-sync`

Together they cover the complete platform runtime:

```text
Memory: L1/L2/L3 routing -> L2 writes -> L3 writes -> L3 retrieval -> brain injection
Indexing: RAG engine -> auto-index (l3-sync)
Governance: lint -> security -> admission -> stocktake -> observability
Platform: skill chain orchestration -> runtime diagnostics -> bridge sync -> cron -> MCP export
Learning: learn from repeated patterns (continuous-learning-v2)
```

### Public Ecosystem Skills

The broader skill ecosystem lives in the public [`ai-skills-hub`](https://github.com/cloud99277/ai-skills-hub) repository — 62 curated skills for coding, research, publishing, and automation. Install what you need.

---

## 8. Graduation Criteria for KitClaw Core

If a skill should graduate from the broader ecosystem into KitClaw core, it
should generally meet these conditions:

1. **General usefulness**: not tied to one private project only.
2. **Portability**: default paths, dependencies, and runtime assumptions work
   for other users too.
3. **Environment decoupling**: no hardcoded private paths, accounts, or repos.
4. **Verifiability**: at least a smoke test or regression test exists.
5. **Documentation quality**: `SKILL.md` is enough for an external user to run it.
6. **Controlled risk**: security boundaries and IO contracts are explicit.

---

## 9. How Governance Enters the Runtime

Once a skill runtime is shared, it needs governance.

KitClaw's governance capabilities:

- `governance/hooks/pre-commit`
  validates Markdown frontmatter (tiered: SKILL.md uses name+description, others use title)

- `skill-lint`
  repository-wide metadata and routing quality checks

- `skill-security-audit`
  runs repository-level static security scanning for shared skills

- `skill-admission`
  quality gate for core skill inclusion (7 checks: lint, security, no personal deps, agent-agnostic, self-contained, docs complete, clean structure)

- `skill-observability`
  records execution logs and shows what is actually used

- `skill-stocktake`
  quality audit workflow with scoring and recommendations

- `mcp-export`
  exports skill metadata for MCP-aware runtimes

---

## 10. Suggested Reading Order

If this is your first time reading KitClaw, this is a good order:

1. `README.md`
2. `docs/memory-architecture.en.md`
3. `docs/skill-runtime-architecture.en.md`
4. `docs/skill-specification.md`
5. `docs/l3-quickstart.md` (if you need L3 knowledge base)
6. the `SKILL.md` files of the bundled skills

That order gives you the system model first and the individual skills after.
