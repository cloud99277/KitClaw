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

All CLI tools (Claude Code, Codex, Gemini, Hermes Agent, Antigravity) share a unified skill repository:

- **CLI Agent Skill Directory**: `~/.ai-skills/`
- **Symlinks**: `~/.claude/skills`, `~/.codex/skills`, `~/.gemini/skills`, `~/.agents/skills` all point to `~/.ai-skills/`
- **Hermes Agent**: Load via `skills.external_dirs: [/home/yangyy/.ai-skills]` in `~/.hermes/config.yaml` (Hermes uses bundled + external skills)
- **OpenClaw Skill Directory**: `~/.openclaw/skills/` (independent repo, different interface)
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
  --skill <skill-name> --agent <gemini|claude|codex|hermes|unknown> --status <success|failure|partial> \
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

## Agent Operations Guidelines (Kitclaw L1 Core)

- **动作前置 (Action-First)**: Lead with the answer or action, not the reasoning. Skip filler words, preamble, and unnecessary transitions. Do not restate the user's instructions.
- **爆炸半径控制 (Careful Actions)**: Treat destructive operations (e.g., `rm -rf`, force-pushing, overwriting uncommitted changes) with extreme caution. Investigate root causes (e.g., lock files, merge conflicts) rather than bypassing safety checks. Ask for confirmation before risky actions.
- **代码极致克制 (No Gold-Plating)**: Do not add features, refactor code, or make improvements beyond what was asked. Do not add error handling for impossible scenarios.
- **不碰未读代码 (Read First)**: In general, do not propose changes to code you haven't read. If asked to modify a file, read it first.
- **自测闭环 (Verify Before Completion)**: Before reporting a coding task complete, verify it actually works. Run tests, check outputs, and do not falsely claim success if errors persist.
