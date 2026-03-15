# Claude Code Setup

## Step 1: Copy the shared identity file

```bash
cp templates/AGENTS.md ~/AGENTS.md
# or symlink:
# ln -s /path/to/kitclaw/templates/AGENTS.md ~/AGENTS.md
```

Edit `~/AGENTS.md` to fill in your user profile.

## Step 2: Reference from CLAUDE.md

Add the following to your `~/.claude/CLAUDE.md`:

```markdown
# Shared Rules

For shared skills, memory routing, and user profile, follow `~/AGENTS.md`.
```

## Step 3: Verify

In a Claude Code session, ask:

> "Search my L2 whiteboard for recent decisions"

Claude should use `memory-manager` to search `~/.ai-memory/whiteboard.json`.
