---
name: skill-security-audit
title: "Skill Security Audit Skill"
tags: [skills, security, governance]
scope: dev
description: >
  Perform static security analysis on AI skill directories. Scan for hardcoded
  credentials, undeclared network requests, basic IO overreach, and risky
  reverse-API labeling issues. Use when the user wants to audit a shared skill
  repository or check whether a skill is safe to open source.
io:
  input:
    - type: directory
      description: Skill directory or skills root. Defaults to KitClaw core-skills.
      required: false
  output:
    - type: json_data
      description: Security audit report
      path_pattern: "skill-audit-report.json"
---

# Skill Security Audit

Run static security checks against one skill or an entire shared skills repo.

## What It Looks For

- hardcoded credentials or tokens
- undeclared network requests
- file writes without matching output declarations
- reverse or unofficial API wording without `danger-` naming
- dependency manifests worth manual review

## Common Commands

```bash
# Audit the bundled KitClaw core-skills
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py --all

# Audit a single skill
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py \
  ~/.ai-skills/conversation-distiller

# Audit another shared skill repository
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py \
  ~/.ai-skills \
  --all \
  --json

# Only run credential checks
python3 ~/.ai-skills/skill-security-audit/scripts/audit.py \
  ~/.ai-skills/mcp-export \
  --dimension credentials
```

## Notes

- Default target is this KitClaw repo's `core-skills/`
- The audit is intentionally static and conservative
- A `PASS` result does not replace human review
- The script uses Python stdlib only
