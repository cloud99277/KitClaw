---
name: runtime-doctor
tags: [runtime, governance, diagnostics]
scope: dev
description: >
  Validate the shared KitClaw runtime contract across WSL, Windows Codex
  Desktop, shared L2/L3 memory, and OpenClaw bridge links. Use when you need a
  fast health check for the shared agent runtime or want to detect drift in
  paths, symlinks, config values, or bridge targets. 当用户提到"runtime doctor"
  "健康检查""诊断""bridge""path check""运行时检查"时触发。
io:
  input:
    - type: text
      description: Optional manifest path or CLI check selector
      required: false
  output:
    - type: json_data
      description: Health check report with per-check status and summary
      path_pattern: "runtime-doctor-report.json"
---

# Runtime Doctor

`runtime-doctor` checks whether the shared runtime contract is still true.

It validates the machine-readable manifest, the WSL memory layout, the Windows
Codex bridge, and the OpenClaw shared-skill link.

## Quick Start

```bash
python3 ~/.ai-skills/runtime-doctor/scripts/runtime_doctor.py
python3 ~/.ai-skills/runtime-doctor/scripts/runtime_doctor.py --json
python3 ~/.ai-skills/runtime-doctor/scripts/runtime_doctor.py \
  --manifest ~/.ai-skills/.system/runtime-manifest.json
```

## What It Checks

- canonical skills, memory, and L3 paths
- whiteboard and memory config readability
- Windows Codex WSL-mode config and env vars
- Codex bridge symlinks for the curated shared skill set
- OpenClaw shared link resolution

## Design Constraints

- stdlib only
- read-only diagnostics by default
- explicit machine-readable JSON output for automation
- failures should name the exact path or config value that drifted
