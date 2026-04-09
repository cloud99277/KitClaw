---
name: remediation-guide
title: Remediation Guide
type: reference
---
# Skill 安全审计 — 修复指南

> **版本**：1.0
> **适用范围**：`audit.py` 扫描报告中的各类发现

---

## 凭据泄露（CRED-xxx）

### 问题
`scripts/` 中发现硬编码的 API Key、Token 或 Password。

### 修复方法

**1. 迁移到环境变量：**

```python
# ❌ 错误：硬编码
api_key = "sk-proj-abc123..."

# ✅ 正确：环境变量
import os
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY not set", file=sys.stderr)
    sys.exit(1)
```

**2. 使用 `.env` 文件（本地开发）：**

在 skill 目录下创建 `.env`（加入 `.gitignore`）：

```bash
# .env — 不要提交到 Git！
OPENAI_API_KEY=sk-proj-abc123...
```

脚本中加载：

```python
from pathlib import Path

def load_env(skill_dir):
    env_file = Path(skill_dir) / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())
```

**3. 确保 `.env` 不被提交：**

```gitignore
# .gitignore
.env
.env.*
```

---

## 数据外传（EXFIL-xxx）

### 问题
`scripts/` 中发现未声明的外部 HTTP 请求。

### 修复方法

**1. 在 SKILL.md 中声明网络访问：**

在 `description` 中明确提及网络行为：

```yaml
---
name: my-skill
description: >
  Fetches content from URLs and processes it locally.
  Downloads resources via HTTP for offline analysis.
---
```

**2. 如果有 IO 声明，添加 `url` 输入类型：**

```yaml
io:
  input:
    - type: url
      description: URL to fetch and process
```

**3. 如果网络请求是非必要的：**

考虑移除网络请求，改为接受文件输入。

---

## 网络越界（NET-xxx）

### 问题
`scripts/` 中有 HTTP 请求但 SKILL.md 的 `description` 和 `io` 声明中未提及网络访问。

### 修复方法

与数据外传修复相同——在 SKILL.md 的 `description` 中声明网络行为，或在 `io:` 中声明 `url` 输入类型。

---

## IO 越界（IO-xxx）

### IO-001：声明了 url 输入但无 HTTP 代码

### 问题
SKILL.md 的 `io:` 声明中有 `url` 类型输入，但 `scripts/` 中没有处理 URL 的代码。

### 修复方法
- 如果 URL 由 Agent 自身处理（不经过 scripts/）：这是正确的，可以通过 `.audit-ignore` 豁免
- 如果 URL 确实需要脚本处理：在 `scripts/` 中添加 URL 处理逻辑

### IO-002：脚本写文件但未声明文件输出

### 问题
`scripts/` 中有文件写入操作，但 `io:` 声明中没有文件类型的输出。

### 修复方法

在 `io:` 声明中添加对应的输出类型：

```yaml
io:
  output:
    - type: markdown_file
      path_pattern: "output/{name}.md"
```

---

## Consent 机制（CONS-xxx）

### CONS-001：使用逆向 API 但无 danger- 前缀

### 问题
SKILL.md 提到了逆向工程/非官方 API，但 skill 名称没有 `danger-` 前缀。

### 修复方法

重命名 skill 目录，添加 `danger-` 前缀：

```bash
mv ~/.ai-skills/my-x-scraper ~/.ai-skills/danger-my-x-scraper
```

同时更新 SKILL.md 的 `name` 字段和 frontmatter。

### CONS-002：有 danger- 前缀但无风险说明

### 问题
Skill 名称含 `danger-` 前缀，但 SKILL.md 中缺少风险说明段落。

### 修复方法

在 SKILL.md 中添加风险说明部分：

```markdown
## ⚠️ 风险说明

本 skill 使用非官方/逆向工程 API，存在以下风险：

- 接口可能随时失效
- 可能违反服务条款
- 不保证数据准确性

使用前请确认你了解并接受上述风险。
```

---

## 供应链（SUPPLY-xxx）

### 问题
Skill 包含外部依赖文件（requirements.txt、package.json 等）。

### 审视建议

1. **检查依赖数量**：尽量减少外部依赖，优先使用 Python stdlib
2. **锁定版本**：使用精确版本号而非范围

```txt
# ❌ 不推荐
requests>=2.0

# ✅ 推荐
requests==2.31.0
```

3. **定期更新**：检查是否有已知漏洞（`pip audit` 或 `npm audit`）

---

## 使用 .audit-ignore 豁免

对于已知的、预期的审计发现，可以在 skill 目录下创建 `.audit-ignore`：

```
# .audit-ignore — 列出不需要扫描的文件
# 格式：文件名或路径片段（包含匹配）
test_data.py
examples/
```
