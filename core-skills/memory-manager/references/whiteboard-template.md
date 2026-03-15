---
title: "Whiteboard Memory Reference"
tags: [memory, whiteboard, reference]
scope: dev
---

# Whiteboard Memory Reference

> Short extraction guide for L2 Whiteboard entries.
> Full guide: `docs/whiteboard-template.md`

## Entry Types

### Decision

- A real choice between alternatives.
- The reason should be worth reusing later.
- Do not store temporary one-off preferences.

Example:

```text
[decision] Use JSON + grep for memory search because it keeps the core zero-dependency.
```

### Action

- A concrete follow-up that is not done yet.
- It should be specific enough to revisit in a later session.
- Do not store vague aspirations.

Example:

```text
[action] Add regression tests for write → search → cleanup in memory-manager.
```

### Learning

- A reusable lesson from implementation, debugging, or validation.
- It should help avoid future mistakes.
- Do not store generic textbook knowledge.

Example:

```text
[learning] Limit static analysis scope before adding allowlists, otherwise the rule loses signal.
```

## Extraction Checklist

- Keep each entry short and explicit.
- Prefer one sentence per entry.
- Include a `project` tag when writing.
- Skip items that are already completed or already documented in L3.
- Deduplicate against existing whiteboard content before writing.
