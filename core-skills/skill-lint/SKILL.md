---
name: skill-lint
description: Repository-wide lint workflow for skill frontmatter, description routing quality, and high-risk body inconsistencies. Use when the user wants to lint a shared skills repository, enforce skill metadata conventions, or review skills after a bulk refactor or cleanup.
io:
  input:
    - type: directory
      description: Skills 仓库根目录路径
      required: false
  output:
    - type: json_data
      description: Lint 检查报告（包含 OK/WARN/ERROR 状态）
    - type: text
      description: 人类可读的 lint 结果摘要
---

# Skill Lint

Run deterministic lint checks across a centralized skills repository.

This skill wraps the repository-wide `lint_skills.py` checker and gives agents a stable entry point for validating skill frontmatter, routing metadata, and a small set of high-risk body inconsistencies.

## When to Use

- After editing many skills in one pass
- Before committing or reviewing changes in a shared skills repo
- When checking whether `SKILL.md` frontmatter follows repository conventions
- When checking whether `description` lines still match the routing template
- When you want a machine-readable lint report for CI or batch cleanup

## Script Directory

Use the wrapper script in this skill:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py" [path] [options]
```

The wrapper delegates to the repository-level checker at:

```bash
.system/skill-creator/scripts/lint_skills.py
```

## Common Commands

Run across the whole centralized repository:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py"
```

Run in strict mode:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py" --strict
```

Get JSON output:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py" --format json
```

Fail on warnings:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py" --fail-on-warnings
```

Only show structural errors:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py" --errors-only
```

Lint a specific root:

```bash
python3 "${SKILL_DIR}/scripts/run_lint.py" "/path/to/skills/root"
```

## What It Checks

- Frontmatter structure and required keys
- `name` format and length
- `description` shape, old phrases, and routing-template drift
- Known high-risk body inconsistencies such as legacy commands or outdated trigger wording

## Output Interpretation

- `OK`: no issues found for that skill
- `WARN`: semantic or routing-quality issues
- `ERROR`: structural issues that should block acceptance

## Default Behavior

- Default mode is compatibility mode
- Body checks are enabled by default
- `--strict` is best for newly-created or fully normalized skill repos
- `--format json` is best for CI or batch post-processing