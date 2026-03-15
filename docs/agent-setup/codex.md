# Codex CLI Setup

## Step 1: Copy the shared identity file

Codex CLI natively reads `~/AGENTS.md`:

```bash
cp templates/AGENTS.md ~/AGENTS.md
```

Edit `~/AGENTS.md` to fill in your user profile. Codex will automatically load it.

## Step 2: Verify

In a Codex session, ask:

> "List available skills"

Codex should run `ls ~/.ai-skills/` and show the KitClaw core skills.
