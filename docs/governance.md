---
version: "1.0"
inherits: "~/.ai-skills/.system/GOVERNANCE.md"
last_updated: "2026-03-15"
scope: dev
title: "Agent-OS 知识库治理宪法"
tags: [governance, policy]
---

# Agent-Toolchain 知识库治理宪法（下位法）

> 本文档是 Agent-Toolchain Knowledge Base 项目的治理规则。
> 继承 `~/.ai-skills/.system/GOVERNANCE.md`（上位法 v1.0）的所有通用约束。
> 下位法不能违反上位法条款。如有冲突，以上位法为准。

---

## §0 继承声明

本文档继承上位法的以下条款（不重复定义）：
- **§一 红线规则**：7 条 Anti-Patterns 全部适用
- **§二 安全底线**：无网络端口、凭据不硬编码
- **§四 架构约束**：schema_version、零后端、单 Agent 假设
- **§五 引力陷阱过滤器**：只用 MD+JSON+Python 能做到 70% 以上就不引入新依赖

以下为知识库特有的补充治理规则。

---

## §1 文档质量标准

### 必须遵守

| 规则 | 严重度 | 执行方式 |
|------|--------|---------|
| frontmatter 必须含 `title` | Error | pre-commit hook |
| 文档必须有一级标题（`#`） | Error | Auditor 巡检 |
| frontmatter `expires` 超期的文档不可引用 | Error | Auditor 巡检 |

### 建议遵守

| 规则 | 严重度 | 执行方式 |
|------|--------|---------|
| frontmatter 含 `tags` | Warning | pre-commit hook |
| frontmatter 含 `scope` | Warning | Auditor 巡检 |
| 调研文档必须有来源引用 | Warning | Auditor 巡检 |

---

## §2 文档生命周期

```
草稿 (draft) → 生效 (active) → 过期 (stale) → 归档 (archived)
                    ↑                  │
                    └── 更新 ──────────┘
```

| 状态 | 判定条件 | frontmatter | Agent 行为 |
|------|---------|-------------|-----------|
| `draft` | 人工标记 或 无 title | `status: draft` | 不引用 |
| `active` | 通过 pre-commit + 有 title | `status: active`（默认） | 正常引用 |
| `stale` | 超过 90 天未更新 | Auditor 标记 `status: stale` | 引用时标注"可能过期" |
| `archived` | 人工归档 | `status: archived` | 不引用 |

---

## §3 scope 隔离规则

采用**目录级白名单**模式（明确列出可访问的目录）。

| scope | 目录 | 读 | 写 | 说明 |
|-------|------|---|---|------|
| `dev` | `docs/`, `src/`, `skills/` | Agent | Agent | 研发区域 |
| `archive` | `docs/architecture/` | Agent | 人类 | 原始架构文档（只读） |
| `personal` | （预留） | owner | owner | MVP 不实现 |

**执行方式**：`knowledge-search --scope dev` 限制搜索路径。
**治理原则**：scope 规则为白名单，未列出的目录默认不可 Agent 搜索。

---

## §4 审计日志

### 写操作审计

通过 `auto_commit.sh` 的规范化 commit message 自动记录：
```
[Agent] type: message
```
审计记录 = Git 历史。零额外成本。

### 读操作审计（可选）

搜索操作可记录到 `logs/search-audit.jsonl`：

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-03-15T15:00:00+08:00",
  "action": "search",
  "agent": "gemini",
  "query": "检索查询",
  "scope": "dev",
  "results_count": 3
}
```

---

## §5 Auditor 巡检规则

**工具**：`src/governance/knowledge_auditor.py`
**触发**：手动调用 或 cron 定期执行
**范围**：`docs/` 目录下所有 `.md` 文件

| 优先级 | 检查项 | 说明 |
|--------|--------|------|
| P0 | frontmatter 完整率 | title / tags / scope 覆盖率 |
| P0 | 过期文档检测 | 超过 90 天未更新 → 标记 stale |
| P1 | 无标题文档检测 | 缺少 `#` 一级标题 |
| P1 | 生命周期一致性 | status 与实际状态是否匹配 |

**产出**：Markdown 健康度报告（含评分 X/10）。

---

## §6 知识库特有约束（扩展上位法 §四）

| # | 约束 | 说明 |
|---|------|------|
| K1 | Git 仓库 = Single Source of Truth | 所有知识以 Git 文件为准 |
| K2 | Agent 不修改 `docs/architecture/` | 人类原始文档为只读 |
| K3 | 新数据格式必须带 schema_version | 继承上位法 §四 约束 6 |
| K4 | 禁止 git push --force | 防止覆盖协作者工作 |
| K5 | 提交前先 pull --rebase | 减少冲突窗口 |

---

> **修订历史**：v1.0 (2026-03-15) — 初版，继承上位法 v1.0
