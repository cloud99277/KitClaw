---
name: skill-security-audit
description: >
  Perform static security analysis on AI skill directories — scan for
  hardcoded credentials, undeclared network requests, permission boundary
  violations, and IO contract inconsistencies. Use when the user asks to
  "audit skills", "scan for security issues", or "check skill safety".
  当用户提到"安全审计""扫描凭据""检查skill安全"时触发。
  Prefer this for skill-level security scanning; use security-review for
  general code security review, and security-scan for .claude/ config scanning.
io:
  input:
    - type: directory
      description: Skill 仓库目录路径（如 ~/.ai-skills/）
  output:
    - type: json_data
      description: 安全审计报告（含各维度扫描结果）
      path_pattern: "audit-report.json"
---

# Skill Security Audit — Skill 安全审计

## 定位

针对 `~/.ai-skills/` 中 skill 目录的安全静态分析工具。

**与其他安全 skill 的差异**：

| Skill | 扫描对象 | 用途 |
|-------|---------|------|
| **skill-security-audit** | skill 的 `scripts/` 目录 | 检测凭据泄露、未声明网络请求、权限越界 |
| `security-review` | 任意代码仓库 | 通用代码安全审查 |
| `security-scan` | `.claude/` 配置文件 | 配置安全扫描 |

## 使用方式

```bash
# 审计单个 skill
python3 scripts/audit.py ~/.ai-skills/translate

# 审计单个 skill，仅凭据扫描
python3 scripts/audit.py ~/.ai-skills/translate --dimension=credentials

# 审计全仓
python3 scripts/audit.py ~/.ai-skills --all

# 审计全仓，输出 JSON 报告
python3 scripts/audit.py ~/.ai-skills --all --output=report.json
```

## 审计维度

| 维度 | 严重度 | 说明 |
|------|--------|------|
| 凭据泄露 | 🔴 Critical | scripts/ 中硬编码的 API key/token/password |
| 数据外传 | 🔴 Critical | scripts/ 中未声明的外部 HTTP 请求 |
| 网络越界 | 🟡 High | scripts/ 有网络请求但 SKILL.md 未声明 |
| IO 越界 | 🟡 High | IO 契约声明与脚本实际行为不符 |
| Consent 机制 | 🟠 Medium | 使用逆向 API 的 skill 合规性检查 |
| 供应链 | 🟢 Low | 列出外部依赖文件 |

## 参考文档

- `references/audit-checklist.md` — 详细审计规则和排除策略
- `references/remediation-guide.md` — 各类问题的修复指南
