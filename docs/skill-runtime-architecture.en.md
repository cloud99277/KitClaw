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
| `KitClaw` | public stable distribution | bundled core skills, memory runtime, governance, docs | public installation entry point |
| `927-ai-skills` `(private)` | larger runtime skills repo | broader production skills, methodology skills, platform skills | private ecosystem layer |
| `agent-os-knowledge-base` `(private)` | L3 engine upstream | Markdown chunking, indexing, retrieval, RAG evolution | private engine upstream |

Useful mental model:

```text
KitClaw = public curated core
927-ai-skills (private) = full runtime catalog
agent-os-knowledge-base (private) = L3 engine upstream
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

## 7. Bundled Core vs Private Ecosystem

### Bundled Core Skills

KitClaw currently bundles:

- `memory-manager`
- `l2-capture`
- `conversation-distiller`
- `knowledge-search`
- `skill-observability`
- `mcp-export`
- `skill-security-audit`

Together they cover the minimum shared loop plus open-source-ready governance
and interoperability:

```text
L1/L2/L3 routing
-> L2 writes
-> L3 writes
-> L3 retrieval
-> execution observability
-> MCP metadata export
-> static skill security audit
```

### Private Ecosystem Skills

The broader ecosystem can continue to live in the private `927-ai-skills` repo,
for example:

- `skill-lint`
- `history-reader`
- `history-chat`
- content production, research, and publishing skills

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

KitClaw currently focuses on:

- `governance/hooks/pre-commit`
  validates critical Markdown frontmatter

- `governance/knowledge_auditor.py`
  audits knowledge document quality

- `skill-observability`
  records execution logs and shows what is actually used

- `skill-security-audit`
  runs repository-level static security scanning for shared skills

- `mcp-export`
  exports skill metadata for MCP-aware runtimes

In the larger private ecosystem, extra tooling such as `skill-lint` can be
added as a repository-wide metadata and routing quality gate.

---

## 10. Suggested Reading Order

If this is your first time reading KitClaw, this is a good order:

1. `README.md`
2. `docs/memory-architecture.en.md`
3. `docs/skill-runtime-architecture.en.md`
4. `docs/skill-specification.md`
5. the `SKILL.md` files of the bundled skills

That order gives you the system model first and the individual skills after.
