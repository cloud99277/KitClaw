---
name: hermes-agent-setup
title: Hermes Agent Setup Guide
type: doc
---
# Hermes Agent Setup

## Step 1: Copy the shared identity file

```bash
cp templates/AGENTS.md ~/AGENTS.md
# or symlink:
# ln -s /path/to/kitclaw/templates/AGENTS.md ~/AGENTS.md
```

Edit `~/AGENTS.md` to fill in your user profile.

## Step 2: Connect to shared skill repository

Edit `~/.hermes/config.yaml`, add the shared skills directory:

```yaml
skills:
  external_dirs:
    - /home/yangyy/.ai-skills
```

This lets Hermes load KitClaw skills alongside its own bundled skills.

## Step 3: Reference from SOUL.md (optional)

If you want Hermes to always follow the shared rules, add to `~/.hermes/SOUL.md`:

```markdown
For shared skills, memory routing, and user profile, follow `~/AGENTS.md`.
```

## Step 4: Verify

In a Hermes session, ask:

> "Search my L2 whiteboard for recent decisions"

Hermes should use `memory-manager` to search `~/.ai-memory/whiteboard.json`.

## Notes

- Hermes uses `skills.external_dirs` instead of symlinks (Claude/Codex/Gemini use symlinks)
- Hermes has its own bundled skills (~25 categories) that coexist with KitClaw shared skills
- Hermes agent identifier for observability logging: `hermes`
