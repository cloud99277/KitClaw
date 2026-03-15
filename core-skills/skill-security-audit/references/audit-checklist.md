---
title: "Skill Audit Checklist"
tags: [skills, security, audit]
scope: dev
---

# Audit Checklist

`skill-security-audit` focuses on repository-level static checks that are cheap,
repeatable, and useful before open sourcing a shared skill set.

## Current Checks

- `credentials`
  Detect likely hardcoded API keys, tokens, passwords, and access keys.

- `exfil` / `network`
  Detect outbound HTTP code paths and compare them with what `SKILL.md`
  declares.

- `io`
  Detect obvious file writes when the declared outputs do not mention file-like
  artifacts.

- `consent`
  Detect reverse or unofficial API wording that should usually be labeled with
  a `danger-` style name or explicit risk section.

- `supply_chain`
  List dependency manifests for manual inspection.

## Scope Limits

- Static only. No sandbox execution or taint tracking.
- Heuristic only. False positives and false negatives are both possible.
- Best used as a first pass before manual audit.
