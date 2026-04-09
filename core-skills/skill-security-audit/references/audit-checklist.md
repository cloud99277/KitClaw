---
name: audit-checklist
title: Audit Checklist
type: reference
---
# Skill 安全审计清单

> **版本**：1.0
> **适用范围**：`~/.ai-skills/` 仓库中所有 skill 目录
> **工具**：`scripts/audit.py`

---

## 一、审计维度与规则

### 1.1 凭据泄露（Credential Leak）

**严重度**：🔴 Critical
**扫描范围**：仅 `scripts/` 目录下的所有文件
**规则 ID 前缀**：`CRED-`

**匹配模式**：

| 规则 ID | 模式 | 说明 |
|---------|------|------|
| CRED-001 | `(?i)(api[_-]?key\|apikey)\s*[=:]\s*["']?[a-zA-Z0-9_\-]{20,}` | 通用 API Key |
| CRED-002 | `sk-[a-zA-Z0-9]{20,}` | OpenAI API Key |
| CRED-003 | `sk-ant-[a-zA-Z0-9]{20,}` | Anthropic API Key |
| CRED-004 | `AIza[a-zA-Z0-9_\-]{35}` | Google API Key |
| CRED-005 | `(?i)(token\|secret)\s*[=:]\s*["']?[a-zA-Z0-9_\-]{20,}` | Token/Secret |
| CRED-006 | `(?i)password\s*[=:]\s*["']?[^\s"']{8,}` | Password |

**排除规则**：

| 排除 | 原因 |
|------|------|
| `os.environ` / `os.getenv` / `process.env` 引用 | 正确的凭据使用方式 |
| Shell 变量引用 `${VAR}` / `$VAR` | 正确的凭据使用方式 |
| 注释行（`#` / `//` 开头） | 说明文本，非实际代码 |
| `.audit-ignore` 中声明的文件/模式 | 显式白名单 |

---

### 1.2 数据外传（Data Exfiltration）

**严重度**：🔴 Critical
**扫描范围**：仅 `scripts/` 目录下的所有文件
**规则 ID 前缀**：`EXFIL-`

**匹配模式**：

| 规则 ID | 模式 | 说明 |
|---------|------|------|
| EXFIL-001 | `requests\.(get\|post\|put\|delete\|patch)` | Python requests 库 |
| EXFIL-002 | `httpx\.(get\|post\|put\|delete\|patch\|Client\|AsyncClient)` | Python httpx 库 |
| EXFIL-003 | `urllib\.request` | Python urllib |
| EXFIL-004 | `(?<!\w)curl\s+` | curl 命令 |
| EXFIL-005 | `(?<!\w)wget\s+` | wget 命令 |
| EXFIL-006 | `fetch\s*\(` | JavaScript fetch |
| EXFIL-007 | `http\.client` | Python http.client |
| EXFIL-008 | `aiohttp\.(ClientSession\|request)` | Python aiohttp |

**排除规则**：

| 排除 | 原因 |
|------|------|
| 注释行 | 说明文本 |
| SKILL.md description 中包含网络相关关键词（`url`, `http`, `fetch`, `download`, `api`）的 skill | 已声明网络访问 |

---

### 1.3 网络越界（Network Overreach）

**严重度**：🟡 High
**扫描范围**：`scripts/` vs `SKILL.md`
**规则 ID 前缀**：`NET-`

**检查逻辑**：
1. 先用 1.2 数据外传的模式扫描 `scripts/`，得到 HTTP 请求清单
2. 读取 SKILL.md 的 `description`（frontmatter）和 `io:` 声明
3. 如果 scripts/ 中有 HTTP 请求，但 SKILL.md description/io 中不包含网络相关关键词 → 报告 NET-001

| 规则 ID | 判定 | 说明 |
|---------|------|------|
| NET-001 | scripts/ 有 HTTP 请求 + SKILL.md 无网络关键词 | 未声明的网络访问 |

**网络关键词列表**：`url`, `http`, `https`, `fetch`, `download`, `api`, `request`, `网络`, `远程`, `在线`

---

### 1.4 IO 越界（IO Overreach）

**严重度**：🟡 High
**扫描范围**：`io:` frontmatter 声明 vs `scripts/` 行为
**规则 ID 前缀**：`IO-`
**前置条件**：仅适用于已有 `io:` 声明的 skill

| 规则 ID | 判定 | 说明 |
|---------|------|------|
| IO-001 | io 声明了 `url` 输入但 scripts/ 中无 HTTP 请求代码 | 声明与实现不符（虚假声明） |
| IO-002 | scripts/ 中有文件写入操作但 io output 中未包含 file 类型 | 未声明的文件输出 |

**文件写入检测模式**：`open\(.+['\"]w`, `with open`, `\.write\(`, `\.writelines\(`

---

### 1.5 Consent 机制（Consent Check）

**严重度**：🟠 Medium
**扫描范围**：skill 目录名 + SKILL.md 正文
**规则 ID 前缀**：`CONS-`

| 规则 ID | 判定 | 说明 |
|---------|------|------|
| CONS-001 | SKILL.md 中含 `逆向` / `unofficial` / `reverse` / `undocumented` 但目录名无 `danger-` 前缀 | 应标记为 danger skill |
| CONS-002 | 目录名含 `danger-` 但 SKILL.md 中无风险说明段落（含 `风险` / `risk` / `warning` / `注意`） | 有标记但缺风险说明 |

---

### 1.6 供应链（Supply Chain）

**严重度**：🟢 Low
**扫描范围**：skill 目录根
**规则 ID 前缀**：`SUPPLY-`

| 规则 ID | 判定 | 说明 |
|---------|------|------|
| SUPPLY-001 | 存在 `requirements.txt` | 列出内容 |
| SUPPLY-002 | 存在 `package.json` | 列出 dependencies |
| SUPPLY-003 | 存在 `Pipfile` | 列出内容 |
| SUPPLY-004 | 存在 `pyproject.toml` | 列出内容 |

> **v2→v3 变更**：新增 SUPPLY-004（pyproject.toml），与 audit.py 实现对齐。来源：综合审查 project-audit 🟢#3
>
> **注意**：Phase 2 MVP 仅列出依赖文件，不做漏洞匹配。

---

## 二、白名单机制

### 三层排除

```
Layer 1 — 内置排除（不可配置）
  ├── 仅扫描 scripts/ 目录
  ├── 排除 SKILL.md 正文
  └── 排除 references/ 目录

Layer 2 — 模式排除（内置但可扩展）
  ├── 排除环境变量引用
  ├── 排除注释行
  └── 排除 shell 变量引用

Layer 3 — 显式白名单（per-skill 配置）
  └── SKILL.md frontmatter 中可选声明：
      audit:
        ignore:
          - credential_leak
          - data_exfil
```

### .audit-ignore 文件（可选）

skill 可在目录下放置 `.audit-ignore` 文件，格式同 `.gitignore`，列出不需要扫描的文件或路径。

---

## 三、审计报告格式

### JSON Schema（v1.0）

```json
{
  "schema_version": "1.0",
  "scan_date": "ISO-8601",
  "scanner_version": "0.1.0",
  "mode": "single | all",
  "results": [
    {
      "skill_path": "/absolute/path/to/skill",
      "skill_name": "skill-name",
      "status": "PASS | WARNING | CRITICAL",
      "findings": [
        {
          "dimension": "credential_leak | data_exfil | network_overreach | io_overreach | consent | supply_chain",
          "severity": "critical | high | medium | low",
          "rule_id": "CRED-001",
          "file": "scripts/example.py",
          "line": 42,
          "matched_content": "truncated match...",
          "whitelisted": false,
          "message": "Hardcoded API key detected"
        }
      ],
      "summary": {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0
      }
    }
  ],
  "global_summary": {
    "total_skills": 0,
    "pass": 0,
    "warning": 0,
    "critical": 0
  }
}
```

### Status 判定规则

| Status | 条件 |
|--------|------|
| CRITICAL | 有任何 critical severity 发现（非白名单） |
| WARNING | 有 high/medium/low 发现但无 critical |
| PASS | 无任何发现，或所有发现均被白名单过滤 |

### 终端输出格式

```
[PASS] translate — 0 findings
[WARN] some-skill — 2 findings (1 high, 1 medium)
[CRIT] another-skill — 1 finding (1 critical)
  └── CRED-002: scripts/fetch.py:42 — OpenAI API key detected

═══════════════════════════════════
Total: 90 skills | PASS: 82 | WARN: 6 | CRIT: 2
═══════════════════════════════════
```
