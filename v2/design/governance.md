---
title: "Governance Engine 详细设计"
status: draft
created: 2026-04-07
engine: governance
claude_code_refs:
  - "src/utils/permissions/permissionRuleParser.ts"
  - "src/utils/permissions/permissions.ts"
  - "src/utils/permissions/PermissionMode.ts"
  - "src/utils/permissions/dangerousPatterns.ts"
  - "src/utils/permissions/bashClassifier.ts"
  - "src/utils/permissions/yoloClassifier.ts"
  - "src/hooks/useCanUseTool.tsx"
  - "src/utils/hooks/postSamplingHooks.ts"
---

# Governance Engine 详细设计

## 1. v1 → v2 变化总结

| 能力 | v1 | v2 |
|------|-----|-----|
| 范围 | pre-commit hook + auditor 脚本 | **全生命周期治理** |
| 权限 | 无 | Rule-based 权限系统 |
| Hooks | pre-commit 只检查 frontmatter | pre/post skill 执行 + 自定义 |
| 审计 | Git 历史 + 可选 JSONL | 结构化执行日志 + 决策追踪 |
| 安全 | skill-security-audit（静态） | 静态 + **运行时**安全检查 |
| 危险检测 | 无 | bash 命令分类器 |

## 2. 权限模型

### 2.1 三种模式

借鉴 Claude Code 的 `PermissionMode`：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `ask` | 每次需要写入/执行时询问用户 | 默认、教学环境 |
| `auto` | 根据规则自动判断，匹配则允许 | 生产环境 |
| `yolo` | 全部允许（无确认） | 信任环境、速测 |

### 2.2 权限规则

```toml
# ~/.kitclaw/config.toml

[governance]
permission_mode = "auto"

[governance.rules]
# 格式：action(pattern) = allow | deny | ask

# 文件操作
"file.read(*)" = "allow"                      # 读取任何文件
"file.write(~/.ai-memory/**)" = "allow"       # 写入记忆目录
"file.write(src/**)" = "ask"                  # 写 src 前询问
"file.delete(*)" = "deny"                     # 禁止删除

# Shell 命令
"shell(npm *)" = "allow"                      # npm 命令允许
"shell(git *)" = "allow"                      # git 命令允许
"shell(rm -rf *)" = "deny"                    # 禁止 rm -rf
"shell(curl *)" = "ask"                       # 网络请求询问

# Skill 执行
"skill.run(memory-*)" = "allow"               # 记忆相关 skill 自动允许
"skill.run(security-*)" = "allow"
"skill.run(*)" = "ask"                        # 其他 skill 询问
```

### 2.3 权限解析器

```python
@dataclass
class PermissionRule:
    action: str               # "file.read", "file.write", "shell", "skill.run"
    pattern: str              # glob 模式
    decision: str             # "allow" | "deny" | "ask"
    source: str               # "global" | "project" | "session"

class PermissionEngine:

    def check(self, action: str, target: str) -> PermissionDecision:
        """检查权限
        优先级：deny > ask > allow
        范围：session rules > project rules > global rules"""

    def load_rules(self) -> list[PermissionRule]:
        """加载规则（global + project-level）"""

    def add_session_rule(self, rule: PermissionRule) -> None:
        """会话内临时添加规则（不持久化）"""
```

## 3. 生命周期 Hooks

### 3.1 Hook 链

```
Skill 执行请求
    │
    ▼
┌──────────────┐     失败 → 中止执行，返回错误
│ pre-execute  │────────────────────────────────→ 错误报告
│ hooks        │
└──────┬───────┘
       │ 全部通过
       ▼
┌──────────────┐
│ 执行 Skill   │
│ script       │
└──────┬───────┘
       │
       ▼
┌──────────────┐     不阻塞执行结果
│ post-execute │────────────────────────────────→ 后台处理
│ hooks        │
└──────┬───────┘
       │
       ▼
    返回结果
```

### 3.2 内置 Hooks

```python
# kitclaw/hooks/builtin.py

BUILTIN_PRE_HOOKS = [
    "validate-input",       # 校验输入参数类型和范围
    "check-permissions",    # 权限规则检查
    "check-dependencies",   # 依赖 skill 是否可用
    "dangerous-pattern",    # 危险模式检测（shell 命令）
    "stale-guardrail",      # 🟡 项目停滞/过度工程检测（待接入）
]

BUILTIN_POST_HOOKS = [
    "log-execution",        # 记录到 executions.jsonl
    "auto-l2-capture",      # 如果结果包含 decision/learning，自动写 L2
    "cost-track",           # 记录 API 成本（如果有）
    "notify-session",       # 通知 Session Manager 更新状态
]
```

> 🟡 **先行原型（`stale-guardrail`）**：
> `~/.ai-skills/project-manager/scripts/stale-detector.py` 已实现 `stale-guardrail` hook 的完整检测逻辑：
> - 代码停滞检测（N 天无 commit）
> - 变更堆积检测（未提交文件数 > 阈值）
> - 未完成行动指令搁置检测（sprint-status.md ❓ 超期）
> - 悬挂分支检测
>
> 接入方式（待 hooks 框架完成后）：将其注册到 `BUILTIN_PRE_HOOKS["stale-guardrail"]`，在每次 Agent 启动编码前自动运行，`trigger_mode: suggest` 时仅输出建议不阻塞。


### 3.3 自定义 Hooks

```bash
# 用户自定义 hook：放到 ~/.kitclaw/hooks/ 下
# 文件名格式：<priority>-<name>.sh 或 .py

~/.kitclaw/hooks/
├── pre-execute.d/
│   ├── 10-my-custom-check.sh     # 自定义前置检查
│   └── 20-notify-slack.py        # 执行前通知
└── post-execute.d/
    └── 10-push-to-obsidian.py    # 执行后同步到 Obsidian
```

Hook 脚本的接口约定：

```bash
#!/usr/bin/env bash
# 接收 JSON 格式的 context（stdin 或参数）
# exit 0 = 通过
# exit 1 = 阻塞（仅 pre-hook）
# stdout = 消息（显示给用户/Agent）

# 环境变量：
# KITCLAW_SKILL_NAME   — 当前 skill 名
# KITCLAW_SESSION_ID   — 当前会话 ID
# KITCLAW_PROJECT      — 当前项目
# KITCLAW_AGENT        — 当前 Agent
```

## 4. 危险模式检测

借鉴 Claude Code 的 `dangerousPatterns.ts` 和 `bashClassifier.ts`：

```python
# kitclaw/engines/governance.py

DANGEROUS_PATTERNS = [
    # 文件系统破坏
    r"rm\s+-rf\s+[/~]",             # rm -rf / or ~
    r"rm\s+-rf\s+\*",               # rm -rf *
    r">\s*/dev/sd[a-z]",            # 写入磁盘设备
    r"mkfs\.",                       # 格式化磁盘
    r"dd\s+if=.+of=/dev/",          # dd 写入设备

    # 系统修改
    r"chmod\s+-R\s+777",            # 全局可写
    r"chown\s+-R\s+root",           # 改变所有权到 root
    r"sudo\s+",                      # sudo 命令

    # 网络风险
    r"curl\s+.*\|\s*sh",            # pipe curl to sh
    r"wget\s+.*\|\s*sh",
    r"eval\s+\$\(",                  # eval 远程命令

    # 数据泄露
    r"cat\s+.*\.env",               # 读取 .env 文件
    r"echo\s+.*API_KEY",            # 输出 API key
    r"export\s+.*SECRET",           # 设置 secret 变量
]

def classify_shell_command(cmd: str) -> str:
    """分类 shell 命令的风险等级
    返回：'safe' | 'risky' | 'dangerous'"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return "dangerous"
    # 更多启发式规则...
    return "safe"
```

## 5. 审计日志

```json
// ~/.kitclaw/logs/executions.jsonl（每行一条）
{
  "schema_version": "2.0",
  "timestamp": "2026-04-07T14:30:00+08:00",
  "event": "skill_execute",
  "skill": "context-engine",
  "action": "compact",
  "agent": "claude",
  "session_id": "abc-123",
  "project": "kitclaw",
  "permission_check": "auto_allowed",
  "pre_hooks": ["validate-input:pass", "check-permissions:pass"],
  "post_hooks": ["log-execution:done", "auto-l2-capture:skipped"],
  "duration_ms": 2340,
  "input_summary": "150k tokens, model=sonnet",
  "output_summary": "compressed to 8k tokens",
  "status": "success",
  "error": null
}
```

## 6. CLI 命令

```bash
# 查看当前权限规则
kitclaw governance rules

# 添加权限规则
kitclaw governance allow "shell(npm test)"
kitclaw governance deny "file.delete(src/**)"

# 检查某个操作是否允许
kitclaw governance check "shell(rm -rf node_modules)"
# → ALLOWED (rule: shell(rm *) in project config)

# 查看审计日志
kitclaw governance log --last 20
kitclaw governance log --skill context-engine --since 2026-04-01

# 运行安全审计（增强版 skill-security-audit）
kitclaw governance audit --skill-dir ~/.ai-skills/
```

## 7. 与其他引擎的交互

| 方向 | 交互 |
|------|------|
| ← Skill Router | 每次 skill 执行前调用 `check()` |
| → Observability | 权限决策和 hook 结果写入审计日志 |
| ← Session Manager | 会话级临时规则 |
| ← CLI | 用户管理权限规则 |
