## User Profile

### Basic Info
- Name: <your-name>
- Language: <your-preferred-language>
- Timezone: <your-timezone>

### Technical Background
- <your-role-and-stack>
- Primary languages: <languages>
- Familiar with: <technologies>
- Current focus: <focus-area>

### Development Environment
- OS: <your-os>
- Editor: <your-editor>
- Terminal: <your-terminal>

### Active Projects
- **<project-1>**: <description> (`<path>`)
- **<project-2>**: <description> (`<path>`)

### Work Style Preferences
- <preference-1>
- <preference-2>

### Don'ts
- Don't explain basic concepts you already know
- Don't auto-commit or push without explicit instruction

---

## Skills System

All CLI tools (Claude Code, Codex, Gemini, Antigravity) share a unified skill repository:

- **CLI Agent Skill Directory**: `~/.ai-skills/`
- **Unified Observability Log**: `~/.ai-skills/.logs/executions.jsonl` (all agents write to the same file)

### Usage Rules

1. **At task start**, if the task may match a skill, run `ls ~/.ai-skills/` to check available skills
2. **When a match is found**, read `~/.ai-skills/<skill-name>/SKILL.md` for usage
3. **Follow the SKILL.md instructions strictly**, including command formats, defaults, and caveats
4. **Script paths**: `~/.ai-skills/<skill-name>/scripts/xxx.py`

### Skill Execution Logging

After **substantively executing any skill**, automatically call `log-execution.py`:

```bash
python3 ~/.ai-skills/skill-observability/scripts/log-execution.py \
  --skill <skill-name> --agent <gemini|claude|codex|unknown> --status <success|failure|partial> \
  [--notes "failure reason"]
```

## L2 / L3 Routing

- `L2`: `~/.ai-memory/whiteboard.json`
  - Only shared `decision / action / learning` entries
  - Query with `memory-manager`
  - Write with `l2-capture`
- `L3`: `<your-knowledge-base-path>` (configure in `~/.ai-memory/config.json`)
  - Stable documents, SOPs, reports, templates, research
  - Query with `knowledge-search`

### When to use `l2-capture`

- User says "write to L2 / whiteboard / capture this decision"
- Need to extract 1-3 shared memory entries from current task/conversation
- Not worth a full document, but needed for future cross-session reference

Recommended command:

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project <project> \
  --from-text "raw conclusion or conversation summary" \
  --apply
```

If the content is a full document or long-term knowledge, don't write to L2 — use L3 instead.
