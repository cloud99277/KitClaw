# Gemini CLI / Antigravity Setup

## Step 1: Copy the shared identity file

```bash
cp templates/AGENTS.md ~/AGENTS.md
```

Edit `~/AGENTS.md` to fill in your user profile.

## Step 2: Create GEMINI.md

Create `~/GEMINI.md` with:

```markdown
# Gemini 配置

对共享知识与共享记忆遵循 `~/AGENTS.md` 的规则。
```

## Step 3: Verify

In a Gemini CLI session, ask:

> "Search my memory for recent decisions"

Gemini should use `memory-manager` to search across L1/L2/L3.
