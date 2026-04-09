---
title: "共享规则注入设计"
status: draft
created: 2026-04-09
depends_on: ["governance.md", "skill-router.md", "architecture.md"]
related_rfc: []
---

# 共享规则注入设计

## 1. 问题陈述

当前 KitClaw 多 Agent 体系（Hermes、Claude Code、Codex、Gemini、OpenClaw）各读各的配置文件：
- Hermes 读 `~/.hermes/SOUL.md`
- Claude 读 `~/.claude/CLAUDE.md`
- OpenClaw 读 `~/.openclaw/workspace/AGENTS.md`

共享行为规范写在 `~/AGENTS.md`，但只有 Hermes 明确引用，其他 Agent 要么间接关联要么完全没引用。
导致：skill 安装规范、安全规则等硬约束无法跨 Agent 一致执行。

## 2. 设计目标

| # | 目标 | 非目标 |
|---|------|--------|
| G1 | 所有 Agent 启动时获得一致的硬约束 | 不要求 Agent 理解 KitClaw 架构 |
| G2 | 注入内容最小化（<10 行） | 不注入完整用户画像和 skill 索引 |
| G3 | Router/Governance 在代码层执行校验，不占 prompt | 不替代 Agent 自身的 system prompt |

## 3. 分层架构

```
┌─────────────────────────────────────────────────┐
│               注入层（每次对话 ~10 行）           │
│                                                 │
│  • 硬约束清单（skill 安装规范、安全规则）         │
│  • 用户偏好摘要（语言、时区、沟通风格）           │
│  • 路由规则摘要（什么场景查哪个 skill）           │
└────────────────────┬────────────────────────────┘
                     │ agent 自行读取
┌────────────────────▼────────────────────────────┐
│               按需加载层（按需读文件）            │
│                                                 │
│  • 完整用户画像     → skill/工具用到时读          │
│  • Skill 索引       → 需要找 skill 时读           │
│  • L2/L3 路由详情   → 存取记忆时读               │
│  • 治理规则         → 开发决策时读               │
└────────────────────┬────────────────────────────┘
                     │ 零 token（代码层）
┌────────────────────▼────────────────────────────┐
│               校验层（代码逻辑）                  │
│                                                 │
│  • Skill Router：install 接口自动跑 lint         │
│  • Governance：行为清单硬校验                    │
│  • Pre-commit hook：提交前安全审计 + lint        │
└─────────────────────────────────────────────────┘
```

## 4. 注入层详细设计

### 4.1 注入内容（硬约束）

```yaml
# kitclaw/shared-rules.yaml — 注入层唯一数据源
version: 1

# 硬约束（每个 Agent 必须遵守）
constraints:
  - "安装外部 skill 必须走 kitclaw skill install，禁止 git clone 裸装"
  - "不要解释基础 Python/Git/Linux 概念"
  - "不要自动 commit 或 push，除非用户明确指示"
  - "不要引入重型框架（参考 governance 引力陷阱过滤器）"

# 用户偏好摘要
user_profile:
  language: "简体中文（技术术语保留英文）"
  timezone: "Asia/Shanghai"
  style: "先调研再动手，偏好渐进式实现，简短直接"

# 路由摘要
routing_hint:
  knowledge: "稳定文档/SOP/研究 → knowledge-search"
  memory: "近期决策/行动 → memory-manager"
  capture: "需要跨会话共享的结论 → l2-capture"
```

### 4.2 注入机制

KitClaw V2 启动 Agent 时，在 system prompt 最后追加注入内容：

```
[Agent 自身的 system prompt ...]

---
KITCLAW SHARED RULES (v1, do not edit):
[从 shared-rules.yaml 渲染的 ~10 行内容]
---
```

Agent 适配器负责追加，不依赖 Agent 自己读文件：
- **Hermes**：`hermes_config.system_prompt_suffix` 配置项
- **Claude Code**：通过 `CLAUDE.md` 的引用机制（`For shared rules, see kitclaw shared-rules.yaml`）
- **Codex/Gemini**：通过各自 config 注入
- **OpenClaw**：通过 workspace 配置注入

### 4.3 Token 成本

| 内容 | 当前 | V2 |
|------|------|----|
| 全量 AGENTS.md | ~115 行 / ~5K tokens | - |
| 注入层 | - | ~10 行 / ~300 tokens |
| 省 | - | **94% token 节省** |

## 5. 校验层详细设计

### 5.1 Skill Router 集成

```python
# kitclaw/engines/skill_router.py

class SkillRouter:
    def install(self, source: str, dest: str = None) -> InstallResult:
        """安装 skill — 内置校验"""
        # 1. 下载/clone
        skill_path = self._fetch(source, dest)

        # 2. 清理（删 README.md 等辅助文件）
        self._clean_auxiliary_files(skill_path)

        # 3. Lint 校验
        issues = self.lint(skill_path)
        if any(i.level == "ERROR" for i in issues):
            return InstallResult(ok=False, errors=issues)

        # 4. 记录安装日志
        self._log_install(skill_path)

        return InstallResult(ok=True, warnings=[i for i in issues if i.level == "WARN"])

    def lint(self, skill_path: Path) -> list[Issue]:
        """调用 skill-lint 校验"""
        # 直接调用 lint_skills.py，不走 shell
        from kitclaw.engines.lint import lint_skill
        return lint_skill(skill_path)
```

Agent 无法绕过 Router：如果 Agent 直接 `git clone`，pre-commit hook 会在提交时拦截 ERROR。

### 5.2 Governance 集成

Governance 定义「所有 Agent 必须遵守的行为清单」，Skill Router 调用 Governance 做校验：

```yaml
# kitclaw/governance/rules.yaml
skill_installation:
  forbidden_actions:
    - "git clone 直接安装到 skill 目录"
    - "跳过 lint 步骤"
  required_actions:
    - "通过 kitclaw skill install 安装"
    - "安装后跑 lint，ERROR 必须修复"
```

## 6. 数据流

```
用户说 "安装这个 skill: https://github.com/xxx/yyy"
  │
  │ Agent 调用
  ▼
kitclaw skill install <url>
  │
  ├─ Router.install()
  │   ├─ fetch（下载）
  │   ├─ clean（删辅助文件）
  │   ├─ lint（ERROR 阻止安装）
  │   └─ log（记录安装日志）
  │
  └─ 返回结果给 Agent
      ├─ ok=True → Agent 告知用户安装成功
      └─ ok=False → Agent 告知用户修复 lint 错误
```

```
Agent 直接 git clone（绕过 Router）
  │
  │ Agent 做 git commit
  ▼
Pre-commit hook 触发
  ├─ 安全审计（已有）
  ├─ Lint 检查（新增）
  │   └─ ERROR → 阻止提交
  └─ PASS → 放行
```

## 7. 实现阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| P1 | `shared-rules.yaml` + 注入机制 | 现有 Agent 适配器 |
| P2 | `SkillRouter.install()` 内置 lint | lint_skills.py（已有） |
| P3 | Governance 行为清单 + Router 集成 | governance engine |
| P4 | Agent 适配器统一注入接口 | Persona Engine |

## 8. 与其他引擎的交互

| 交互方向 | 说明 |
|----------|------|
| → Persona Engine | 注入层内容由 Persona Engine 渲染 |
| → Skill Router | 校验层的 install/lint 逻辑 |
| → Governance | 行为清单定义和校验 |
| → Context Engine | 注入内容计入 token 预算 |
| → Memory Engine | 用户偏好摘要从记忆系统同步 |
| ← Agent 适配器 | 各 Agent 接收注入内容并追加到 system prompt |
