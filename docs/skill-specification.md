# KitClaw Skill Specification v1.0

> This document defines the standard contract for KitClaw-compatible skills.

## 1. Directory Structure

Every skill must follow this structure:

```
<skill-name>/
├── SKILL.md              # Required: Skill definition and usage docs
├── scripts/              # Required: Executable entry points
│   └── <main-script>.py  # At least one entry point
├── references/           # Optional: Reference docs, templates
├── requirements.txt      # Optional: Python dependencies (if any)
└── tests/                # Recommended: Skill-specific tests
```

## 2. SKILL.md Standard

### YAML Frontmatter (Required)

```yaml
---
name: <skill-name>          # Required: kebab-case, unique
description: >              # Required: One paragraph, include trigger keywords
  <What it does. When to use it. When NOT to use it.
  Include Chinese trigger keywords for bilingual agent matching.>
io:                          # Recommended
  input:
    - type: text|file|json_data
      description: <what the skill accepts>
  output:
    - type: text|file|json_data|markdown_file
      description: <what the skill produces>
---
```

### Markdown Body

The body should include:
- **What It Does** — 2-3 sentence summary
- **Quick Start** — Copy-paste ready commands
- **Usage Examples** — At least 2 examples with different options
- **Design Constraints** — Dependencies, limitations, security notes

## 3. Script Conventions

### Entry Points

- All entry point scripts live in `scripts/`
- Must support `--help` (via `argparse`)
- Must support `--version` (recommended)
- Should support `--json` for structured JSON output
- Use `#!/usr/bin/env python3` shebang

### Dependencies

- **Default**: Zero external dependencies (pure Python stdlib)
- If dependencies are needed, list them in `requirements.txt` at skill root
- Never depend on system packages beyond Python 3.10+

### Output Format

When `--json` is specified, output must be valid JSON to stdout:

```json
{
  "schema_version": "1.0",
  "status": "ok",
  "results": [...]
}
```

Error output goes to stderr. Exit code 0 = success, non-zero = failure.

## 4. Observability Contract

After substantively executing a skill, agents must call:

```bash
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill <skill-name> \
  --agent <agent-name> \
  --status <success|failure|partial> \
  [--notes "optional context"]
```

Rules:
- `input_fields` only records field **names**, never values (prevent credential leaks)
- Log file permissions default to 600 (owner-only read/write)

## 5. Naming Conventions

| Component | Convention | Example |
|-----------|-----------|---------|
| Skill directory | `kebab-case` | `memory-manager` |
| Python scripts | `snake_case.py` | `memory_search.py` |
| Shell scripts | `kebab-case.sh` | `knowledge-search.sh` |
| SKILL.md `name` | matches directory name | `memory-manager` |

## 6. Example: Minimal Skill

```
hello-world/
├── SKILL.md
└── scripts/
    └── hello.py
```

**SKILL.md:**
```yaml
---
name: hello-world
description: A minimal example skill. Use for testing skill infrastructure.
---

# Hello World

Run: `python3 ~/.ai-skills/hello-world/scripts/hello.py "your name"`
```

**scripts/hello.py:**
```python
#!/usr/bin/env python3
import argparse, json

def main():
    parser = argparse.ArgumentParser(description="Hello World skill")
    parser.add_argument("name", help="Your name")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--version", action="version", version="hello 1.0.0")
    args = parser.parse_args()

    if args.as_json:
        print(json.dumps({"greeting": f"Hello, {args.name}!"}))
    else:
        print(f"Hello, {args.name}!")

if __name__ == "__main__":
    main()
```
