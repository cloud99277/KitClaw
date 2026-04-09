---
title: "统一 CLI 详细设计"
status: draft
created: 2026-04-07
engine: cli
---

# 统一 CLI 详细设计

## 1. 设计目标

```
v1: python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "query" --layer L2
v2: kitclaw memory search "query" --layer L2
```

一个入口。所有命令。自动 hooks。结构化输出。

## 2. 命令树

```
kitclaw
├── init                              # 初始化 KitClaw
├── status                            # 全局状态概览
├── doctor                            # 健康检查
├── migrate                           # v1 → v2 迁移
│
├── memory                            # 记忆引擎
│   ├── search <query>                # 检索记忆
│   ├── write <content>               # 写入记忆
│   ├── extract                       # 从对话提取记忆
│   ├── list                          # 列出记忆条目
│   ├── topics                        # 列出主题
│   ├── expire-check                  # 检查过期记忆
│   └── stats                         # 记忆统计
│
├── context                           # 上下文引擎
│   ├── analyze                       # 分析当前 token 使用
│   ├── compact                       # 执行压缩
│   ├── compact-prompt                # 生成压缩 prompt（给 Agent 用）
│   └── apply                         # 应用压缩结果
│
├── session                           # 会话管理
│   ├── start                         # 开始会话
│   ├── end                           # 结束会话
│   ├── pause                         # 暂停会话
│   ├── resume                        # 恢复会话
│   ├── list                          # 列出会话
│   ├── show <id>                     # 查看会话详情
│   ├── handoff <id> --to <agent>     # 交接会话
│   └── cleanup                       # 清理过期快照
│
├── run <skill> [args]                # 执行 skill（含 hooks）
│
├── skill                             # Skill 管理
│   ├── list                          # 列出所有 skill
│   ├── match <query>                 # 匹配 skill
│   ├── info <name>                   # 查看 skill 详情
│   ├── install <path|url>            # 安装 skill
│   └── validate <name>               # 校验 skill 规范
│
├── workflow                          # 编排
│   ├── list                          # 列出 workflows
│   ├── run <name>                    # 执行 workflow
│   └── validate <file>               # 校验 workflow 定义
│
├── governance                        # 治理
│   ├── rules                         # 查看权限规则
│   ├── allow <pattern>               # 添加允许规则
│   ├── deny <pattern>                # 添加拒绝规则
│   ├── check <action>                # 检查权限
│   ├── log                           # 审计日志
│   └── audit                         # 安全审计
│
├── config                            # 配置
│   ├── show                          # 显示当前配置
│   ├── set <key> <value>             # 设置配置项
│   └── reset                         # 重置为默认
│
└── setup <agent>                     # Agent 配置
    ├── claude                        # 配置 Claude Code 集成
    ├── gemini                        # 配置 Gemini 集成
    └── codex                         # 配置 Codex 集成
```

## 3. 实现框架

```python
# kitclaw/cli/main.py
import click

@click.group()
@click.version_option()
@click.option('--json', 'output_json', is_flag=True, help='JSON 输出')
@click.option('--quiet', is_flag=True, help='静默模式')
@click.pass_context
def cli(ctx, output_json, quiet):
    """KitClaw — Agent Runtime Middleware"""
    ctx.ensure_object(dict)
    ctx.obj['json'] = output_json
    ctx.obj['quiet'] = quiet

# ---- Memory 子命令组 ----
@cli.group()
def memory():
    """记忆管理"""
    pass

@memory.command()
@click.argument('query')
@click.option('--layer', type=click.Choice(['L1', 'L2', 'L3', 'all']), default='all')
@click.option('--project', default=None)
@click.option('--limit', default=10, type=int)
@click.pass_context
def search(ctx, query, layer, project, limit):
    """检索记忆"""
    from kitclaw.engines.memory import MemoryEngine
    engine = MemoryEngine()
    results = engine.search(query, project=project, limit=limit)

    if ctx.obj.get('json'):
        click.echo(json.dumps([r.to_dict() for r in results], ensure_ascii=False))
    else:
        for r in results:
            click.echo(f"  [{r.type}] {r.content}")
            click.echo(f"    topic: {r.topic} | {r.created.strftime('%Y-%m-%d')}")

# ---- Context 子命令组 ----
@cli.group()
def context():
    """上下文管理"""
    pass

@context.command()
@click.option('--model', default='sonnet')
@click.option('--input', 'input_file', type=click.Path(exists=True), required=True)
@click.pass_context
def analyze(ctx, model, input_file):
    """分析当前上下文 token 使用"""
    from kitclaw.engines.context import ContextEngine
    engine = ContextEngine()
    with open(input_file) as f:
        messages = json.load(f)
    result = engine.analyze(messages, model)

    if ctx.obj.get('json'):
        click.echo(json.dumps(result.__dict__))
    else:
        click.echo(f"Token 使用: {result.total_tokens:,} / {result.context_window:,} ({result.usage_pct:.0f}%)")
        click.echo(f"剩余空间: {result.tokens_remaining:,}")
        click.echo(f"建议压缩: {'是' if result.should_compact else '否'} ({result.urgency})")

# ---- Session 子命令组 ----
@cli.group()
def session():
    """会话管理"""
    pass

@session.command()
@click.option('--project', required=True)
@click.option('--agent', required=True, type=click.Choice(['claude', 'gemini', 'codex', 'other']))
@click.option('--resume-latest', is_flag=True)
@click.pass_context
def start(ctx, project, agent, resume_latest):
    """开始新会话"""
    from kitclaw.engines.session import SessionManager
    mgr = SessionManager()

    resume_from = None
    if resume_latest:
        latest = mgr.list(project=project, status='completed', limit=1)
        if latest:
            resume_from = latest[0].session_id

    session = mgr.start(project, agent, resume_from=resume_from)

    if ctx.obj.get('json'):
        click.echo(json.dumps(session.meta.__dict__, default=str))
    else:
        click.echo(f"Session started: {session.meta.session_id}")
        if resume_from:
            click.echo(f"  Resumed from: {resume_from}")
            click.echo(f"\n--- Context from previous session ---")
            click.echo(session.context_snapshot)

# ---- Status（全局状态）----
@cli.command()
@click.pass_context
def status(ctx):
    """全局状态概览"""
    from kitclaw.engines.memory import MemoryEngine
    from kitclaw.engines.session import SessionManager

    mem = MemoryEngine()
    ses = SessionManager()

    active_sessions = ses.list(status='active')
    mem_stats = mem.get_stats()

    click.echo("🐾 KitClaw Status")
    click.echo(f"  Version: 2.0")
    click.echo()
    click.echo(f"  📋 Active sessions: {len(active_sessions)}")
    for s in active_sessions:
        click.echo(f"     • {s.project} ({s.agent}) — since {s.started_at.strftime('%H:%M')}")
    click.echo()
    click.echo(f"  🧠 Memory entries: {mem_stats['total']}")
    click.echo(f"     preference: {mem_stats['by_type'].get('preference', 0)}")
    click.echo(f"     fact:       {mem_stats['by_type'].get('fact', 0)}")
    click.echo(f"     learning:   {mem_stats['by_type'].get('learning', 0)}")
    click.echo(f"     decision:   {mem_stats['by_type'].get('decision', 0)}")
    click.echo(f"  📚 Topics: {mem_stats['topic_count']}")
    click.echo(f"  🗂  Knowledge DB: {'connected' if mem_stats['rag_available'] else 'not configured'}")
```

## 4. 输出格式

所有命令支持两种输出：

### 人类可读（默认）
```
$ kitclaw status
🐾 KitClaw Status
  Version: 2.0

  📋 Active sessions: 1
     • kitclaw (claude) — since 14:30

  🧠 Memory entries: 47
     preference: 12
     fact:       15
     learning:   10
     decision:   10
  📚 Topics: 8
  🗂  Knowledge DB: connected
```

### JSON（`--json`）
```json
$ kitclaw status --json
{
  "version": "2.0",
  "active_sessions": 1,
  "memory_entries": 47,
  "topics": 8,
  "rag_available": true
}
```

Agent 应该始终使用 `--json` 模式来获取结构化输出。

## 5. `kitclaw init` 流程

```bash
$ kitclaw init

🐾 Initializing KitClaw v2...

  [1/5] Creating config directory (~/.kitclaw/)... ✓
  [2/5] Writing default config (~/.kitclaw/config.toml)... ✓
  [3/5] Detecting existing v1 installation...
        Found: ~/.ai-memory/ (47 entries in whiteboard.json)
        Found: ~/.ai-skills/ (7 core skills)
  [4/5] Creating session directory... ✓
  [5/5] Setting up agent symlinks...
        ~/.claude/skills → ~/.ai-skills/ ✓
        ~/.gemini/skills → ~/.ai-skills/ ✓
        ~/.codex/skills  → ~/.ai-skills/ ✓

✓ KitClaw v2 initialized!

Next steps:
  1. Review config: kitclaw config show
  2. Migrate v1 data: kitclaw migrate
  3. Check health: kitclaw doctor
  4. Set up agents: kitclaw setup claude
```

## 6. `kitclaw setup <agent>` 流程

```bash
$ kitclaw setup claude

🐾 Setting up KitClaw for Claude Code...

  [1/3] Checking Claude Code installation... ✓ (v2.1.87)
  [2/3] Updating ~/.claude/CLAUDE.md...
        Added: KitClaw session lifecycle instructions
        Added: kitclaw CLI reference
  [3/3] Symlink: ~/.claude/skills → ~/.ai-skills/ ✓

✓ Claude Code configured!

The following instructions were added to CLAUDE.md:
  • Start sessions with: kitclaw session start --project <project> --agent claude
  • End sessions with: kitclaw session end
  • Search memory with: kitclaw memory search "query" --json
```

## 7. 包分发

```toml
# pyproject.toml

[project]
name = "kitclaw"
version = "2.0.0"
description = "Agent Runtime Middleware — shared memory, context management, and orchestration for AI agents"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "Cloud927"}]

dependencies = [
    "click>=8.0",
    "tomli>=2.0; python_version < '3.11'",    # TOML parser (stdlib in 3.11+)
]

[project.optional-dependencies]
rag = ["lancedb>=0.4", "sentence-transformers>=2.0"]
tokens = ["tiktoken>=0.5"]
full = ["kitclaw[rag,tokens]"]

[project.scripts]
kitclaw = "kitclaw.cli.main:cli"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"
```

### 依赖策略

| 依赖 | 类型 | 说明 |
|------|------|------|
| `click` | 必须 | CLI 框架 |
| `tomli` | 必须 (< 3.11) | TOML 配置解析 |
| `tiktoken` | 可选 | 精确 token 估算 |
| `lancedb` | 可选 | 向量检索（RAG） |
| `sentence-transformers` | 可选 | 向量生成 |
| 其他 | 无 | 核心功能零额外依赖 |

## 8. Agent 集成协议

### AGENTS.md 模板注入内容

当 `kitclaw setup <agent>` 执行时，以下内容会追加到 Agent 的系统配置文件中：

```markdown
## KitClaw Runtime Integration

### 会话生命周期
- 开始新任务时：`kitclaw session start --project <project> --agent <agent-name> --json`
- 完成任务后：`kitclaw session end --json`
- 如果用户要切换 Agent：`kitclaw session handoff --to <target-agent> --json`

### 记忆检索
当需要了解项目背景、之前的决策或用户偏好时：
`kitclaw memory search "<query>" --project <project> --json`

### 上下文管理
当感觉对话变长（超过 50 条来回）时：
`kitclaw context analyze --model <model> --input <messages-file> --json`
如果输出 `should_compact: true`，执行压缩。

### 重要规则
- 所有 kitclaw 命令都加 `--json` 获取结构化输出
- 不要直接调用 `python3 ~/.ai-skills/xxx/scripts/yyy.py`，使用 `kitclaw` CLI
- 会话结束时的 `kitclaw session end` 会自动提取记忆和保存上下文，无需手动
```
