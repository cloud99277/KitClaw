---
name: runtime-bridge-sync
tags: [runtime, bridge, governance]
scope: dev
description: >
  Sync the curated Windows Codex Desktop bridge symlinks from the shared
  runtime manifest. Use when you want to materialize or validate the Windows
  Codex skill bridge set against the WSL source of truth. Do not use it for
  L2/L3 memory writes or OpenClaw-private skills. 当用户提到"bridge sync"
  "runtime bridge""同步技能""Codex bridge""Windows 技能桥接"时触发。
io:
  input:
    - type: text
      description: Optional manifest path or selector
      required: false
  output:
    - type: json_data
      description: Dry-run plan or applied bridge sync report
      path_pattern: "runtime-bridge-sync-report.json"
---

# Runtime Bridge Sync

`runtime-bridge-sync` keeps the Windows Codex Desktop bridge in sync with the
canonical WSL runtime manifest.

It is intentionally narrow:

- it manages only the curated Codex skill symlinks
- it does not touch L2 whiteboard data
- it does not touch OpenClaw-private skills

## Quick Start

```bash
python3 ~/.ai-skills/runtime-bridge-sync/scripts/bridge_sync.py
python3 ~/.ai-skills/runtime-bridge-sync/scripts/bridge_sync.py --json
python3 ~/.ai-skills/runtime-bridge-sync/scripts/bridge_sync.py --apply
```

## What It Manages

- `~/.codex/skills/<skill>`
- target symlink sources under `~/.agents/skills/<skill>`
- idempotent reapplication of the curated bridge list from the manifest

## Design Constraints

- dry-run by default
- stdlib only
- refuse to silently overwrite non-symlink files
- report exact link targets and planned changes
