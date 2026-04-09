---
title: "Skill Router & Orchestrator 详细设计"
status: draft
created: 2026-04-07
engine: skill-router
claude_code_refs:
  - "src/skills/loadSkillsDir.ts"
  - "src/skills/bundledSkills.ts"
  - "src/tools/SkillTool/"
  - "src/tools/AgentTool/loadAgentsDir.ts"
---

# Skill Router & Orchestrator 详细设计

## 1. 问题陈述

v1 的 Skill 路由完全依赖 Agent 自己：
- Agent 读 SKILL.md 的 description → 猜测哪个 skill 适用
- 没有上下文条件 → 无法根据当前工作自动推荐
- 没有编排 → 多步骤任务需要 Agent 手动逐个调用
- 没有依赖管理 → skill A 需要 skill B 的输出，但没有声明

## 2. 三层路由

```
用户请求
    ↓
Layer 1: 关键词匹配
  → SKILL.md 的 description + triggers 字段
  → 匹配 → 直接路由
    ↓ 未匹配
Layer 2: 路径条件激活
  → SKILL.md 的 activation.paths 字段
  → 当前操作的文件路径匹配 gitignore 模式
  → 匹配 → 激活并路由
    ↓ 未匹配
Layer 3: 上下文推荐
  → 基于当前 token 数、项目类型、最近使用的 skill
  → 推荐列表（不自动执行）
```

## 3. SKILL.md v2 扩展字段

```yaml
---
name: context-engine
version: "2.0"
description: >
  智能上下文管理。当对话过长需要压缩时使用。

# v2 新增
activation:
  triggers:                       # 关键词触发
    - "压缩对话"
    - "上下文太长"
    - "compact"
    - "token limit"
  paths:                          # 路径条件（gitignore 风格）
    - "**/*.ts"                   # 操作 TS 文件时可能需要
  context:                        # 上下文条件
    min_tokens: 50000             # 超过此 token 数时推荐
    max_tokens: null              # 低于此 token 数时推荐（null=不限制）
    project_types: []             # 特定项目类型
  effort: quick                   # quick | thorough | exhaustive

dependencies:
  required:
    - memory-manager              # 必须可用
  optional:
    - knowledge-search            # 可用则增强

lifecycle:
  pre_execute:
    - validate-input              # 内置 hook
    - check-permissions           # 内置 hook
  post_execute:
    - log-execution               # 内置 hook（自动）
    - auto-l2-capture             # 如果配置了自动 L2

permissions:
  reads: ["~/.ai-memory/", "~/.kitclaw/sessions/"]
  writes: ["~/.kitclaw/sessions/", "~/.ai-memory/topics/"]
  shell: false                    # 是否需要 shell 执行权限
  network: false                  # 是否需要网络

io:
  input:
    - type: json_data
      schema: schemas/compact-input.json
  output:
    - type: json_data
      schema: schemas/compact-output.json
---
```

## 4. Skill 注册与发现

```python
@dataclass
class SkillManifest:
    """Skill 清单（从 SKILL.md frontmatter 解析）"""
    name: str
    version: str
    description: str
    scripts: list[str]              # scripts/ 下的入口文件
    activation: ActivationConfig
    dependencies: DependencyConfig
    lifecycle: LifecycleConfig
    permissions: PermissionConfig
    io: IOConfig
    source_path: str                # SKILL.md 所在路径
    source_type: str                # "core" | "ecosystem" | "project"

class SkillRouter:

    def discover(self, search_paths: list[str] | None = None) -> list[SkillManifest]:
        """发现所有可用 skill
        搜索路径优先级：
        1. ~/.ai-skills/ (core + installed)
        2. ./.skills/ (项目级)
        3. 自定义路径"""

    def match(self, query: str, *,
              file_paths: list[str] | None = None,
              token_count: int | None = None,
              project: str | None = None) -> list[SkillMatch]:
        """匹配最合适的 skill（返回排序后的候选列表）"""

    def activate_conditional(self, file_paths: list[str], cwd: str) -> list[str]:
        """根据文件路径条件激活 skill
        借鉴 Claude Code 的 activateConditionalSkillsForPaths()"""

    def resolve_dependencies(self, skill: SkillManifest) -> list[SkillManifest]:
        """解析 skill 依赖链"""

    def execute(self, skill_name: str, args: dict, *,
                session_id: str | None = None) -> SkillResult:
        """执行 skill（含完整生命周期）
        1. resolve dependencies
        2. run pre-hooks
        3. execute skill script
        4. run post-hooks
        5. log execution"""
```

## 5. 编排引擎

### 5.1 Workflow 定义

```yaml
# ~/.kitclaw/workflows/end-of-session.yaml
name: end-of-session
description: 会话结束时的标准流程
triggers:
  - "kitclaw session end"

steps:
  - name: compact-if-needed
    skill: context-engine
    action: analyze
    args:
      model: "${model}"
    condition: "${result.should_compact}"
    on_true:
      skill: context-engine
      action: compact
      output_as: compact_result

  - name: extract-memories
    skill: auto-memory-extract
    args:
      project: "${project}"
      agent: "${agent}"
    output_as: memories

  - name: save-session
    skill: session-manager
    action: snapshot
    args:
      context: "${compact_result.summary}"
      memories: "${memories.entries}"

  - name: log-summary
    skill: observability
    action: log
    args:
      event: "session_end"
      data:
        tokens_saved: "${compact_result.tokens_saved}"
        memories_extracted: "${memories.count}"
```

### 5.2 编排执行器

```python
class Orchestrator:

    def load_workflow(self, path: str) -> Workflow:
        """加载 YAML workflow 定义"""

    def execute_workflow(self, workflow: Workflow, context: dict) -> WorkflowResult:
        """执行 workflow
        - 串行执行 steps
        - 支持 condition 和 on_true/on_false 分支
        - 支持 output_as 变量传递
        - 支持 parallel 并行步骤（future）"""

    def get_builtin_workflows(self) -> list[Workflow]:
        """内置 workflows:
        - end-of-session
        - start-of-session
        - daily-report
        """
```

## 6. CLI 命令

```bash
# 列出所有可用 skill
kitclaw skill list

# 搜索匹配的 skill
kitclaw skill match "压缩对话" --token-count 150000

# 执行 skill（含生命周期 hooks）
kitclaw run context-engine compact --model sonnet

# 执行 workflow
kitclaw workflow run end-of-session --project kitclaw

# 列出 workflows
kitclaw workflow list
```

## 7. 条件激活实现（参考 Claude Code）

```python
def activate_conditional(self, file_paths: list[str], cwd: str) -> list[str]:
    """
    借鉴 Claude Code 的 activateConditionalSkillsForPaths()
    使用 pathspec 库（gitignore 兼容）匹配文件路径
    """
    import pathspec

    activated = []
    for skill in self._conditional_skills:
        if not skill.activation.paths:
            continue

        spec = pathspec.PathSpec.from_lines("gitwildmatch", skill.activation.paths)
        for fp in file_paths:
            rel = os.path.relpath(fp, cwd)
            if spec.match_file(rel):
                self._active_skills[skill.name] = skill
                activated.append(skill.name)
                break

    return activated
```

## 8. 与其他引擎的交互

| 方向 | 交互 |
|------|------|
| → Context Engine | 当 token 超限时推荐 compact skill |
| → Memory Engine | 执行后自动提取记忆 |
| → Governance | 执行前检查权限 |
| → Observability | 记录每次路由决策和执行结果 |
| ← Session Manager | 会话开始/结束时触发内置 workflow |
