---
title: "KitClaw v2 产品战略：从 Skill 脚本集到 Agent 运行时"
tags: [strategy, product, architecture, v2]
scope: dev
status: draft
---

# KitClaw v2 产品战略

> 一份顶级 PM 的诊断书：KitClaw 当前的根本问题不是"缺功能"，而是"没有生命"。

---

## 第一部分：残酷的现状诊断

### 1.1 KitClaw 目前到底是什么

说白了，KitClaw 现在是 **7 个 Python 脚本 + 一堆 Markdown 文档**。

```
用户对 Agent 说话
    ↓
Agent 可能想到调用某个 skill（也可能不会）
    ↓
python3 ~/.ai-skills/xxx/scripts/yyy.py --args
    ↓
输出到 stdout
    ↓
结束。没有后续。
```

没有运行时。没有生命周期。没有主动行为。
Agent 不调用它，它就是一堆死文件。

### 1.2 与 Claude Code 的本质差距

这不是"缺某个 feature"的问题。是**整个架构层次**的差距：

| 维度 | Claude Code | KitClaw 现状 | 差距性质 |
|------|-------------|-------------|----------|
| **运行时** | 持续运行的 Agent 循环，实时感知上下文 | 无运行时，被动等待调用 | **架构性** |
| **记忆** | 自动提取 + 自动写入 + 自动去重 | 手动调用 `l2-capture` | **自动化差距** |
| **上下文管理** | autoCompact 实时监控 token → 自动压缩 | 不存在 | **能力空白** |
| **Skill 路由** | 根据文件路径自动激活条件 Skill | Agent 靠描述文字猜测匹配 | **智能差距** |
| **工具生命周期** | pre-hook → 执行 → post-hook → 观测 | 执行完就结束 | **流程差距** |
| **子代理** | AgentTool fork 独立子进程 | 不存在 | **能力空白** |
| **权限** | rule-based 精细权限 + YOLO 分类器 | governance 只有 pre-commit | **安全差距** |
| **协调** | Coordinator Mode 多 Agent 编排 | 不存在 | **能力空白** |

### 1.3 更深层的问题

**KitClaw 的真正问题是：它不知道自己该成为什么。**

- 说它是"Skill 库"——但 7 个 skill 不够成为平台
- 说它是"记忆层"——但记忆全靠 Agent 自觉调用
- 说它是"治理框架"——但只有一个 pre-commit hook
- 说它是"Agent OS"——但没有任何运行时

它处在一个**尴尬的中间态**：

```
太薄 → 不够成为产品
太厚 → 不是简单脚本了
太被动 → 没有自己的"生命"
太依赖文档 → 纸上架构
```

---

## 第二部分：产品定位决策

### 2.1 三条路，必须选一条

| 路线 | 定位 | 类比 | 复杂度 | 护城河 |
|------|------|------|--------|--------|
| **A. 增强 Skill 平台** | 更好的 skill 注册/路由/观测 | npm registry | 低 | 弱 |
| **B. Agent 运行时层** | 包裹任何 Agent 的中间件 | Docker / systemd | 中 | 中 |
| **C. Agent 操作系统** | 完整的 Agent 开发框架 | Linux kernel | 极高 | 强 |

**我的建议：走 B 路线，但用 C 的愿景来设计。**

理由：
- A 路线（更好的 npm）没有差异化，别人也能做
- C 路线（操作系统）太重，一个人做不完
- B 路线让 KitClaw 成为 **"Agent 的中间件"**——不替代 Agent，而是给任何 Agent 加上生产级基础设施

### 2.2 新的一句话定位

> **KitClaw：The runtime middleware that gives any AI agent production-grade memory, context management, and orchestration — powered by its own Ghost Agent brain.**

不是 "shared skills"。是**有自己后台脑力的 runtime middleware**。

### 2.3 Ghost Agent：突破性架构决策（RFC-002）

在设计 v2 的自动压缩和记忆提取时，暴露了一个致命问题：KitClaw 是 CLI 工具，自身没有 LLM 能力。如果让前台 Agent（如 Claude Code）替它执行压缩的 prompt，CLI 和 Agent 之间会出现"握手断层"——CLI 进程已退出，结果无法回传。

**解决方案：Ghost Agent（影子 Agent）模型**

```
KitClaw 不做全职 Agent（不抢 Claude Code 的活）
而是在 config.toml 中配置一个独立的廉价小模型 API

前台大脑：Claude Sonnet / Opus（写代码，你用的前台 Agent）
后台小脑：Gemini Flash / Haiku / DeepSeek（KitClaw 自己的"小脑"）

当 Agent 调用 kitclaw session end 时：
  KitClaw 内部直接调自己的小模型
  → 压缩对话
  → 提取记忆
  → 写入磁盘
  → 全自动闭环，不求人
```

**关键安全设计**（详见 `ghost-agent-deep-review.md`）：
- 🔒 隐私：数据默认脱敏再外发 + 支持 Ollama 纯本地模型
- 🛡️ 降级：Ghost Agent 不可用时不瘫痪，三级降级保证数据不丢失
- 💰 成本：Flash 默认 ~$0.01/次 + 月度预算上限
- 🔑 安全：API Key 环境变量优先，不鼓励明文落盘

---

## 第三部分：v2 架构设计

### 3.1 架构全景

```
┌─────────────────────────────────────────────────────────────┐
│                      用户 / IDE                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    任意 AI Agent                              │
│              (Claude Code / Gemini / Codex)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    Agent 调用 KitClaw
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                                                              │
│                   KitClaw Runtime Layer                       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Context     │  │  Memory      │  │  Skill Router      │  │
│  │  Engine      │  │  Engine      │  │  & Orchestrator    │  │
│  │ • 对话压缩   │  │ • 自动提取   │  │ • 条件激活         │  │
│  │ • Token 监控 │  │ • L1/L2/L3   │  │ • 依赖解析         │  │
│  │ • 快照恢复   │  │ • 去重合并   │  │ • 编排链           │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Governance  │  │  Observ-     │  │  Session           │  │
│  │  Engine      │  │  ability     │  │  Manager           │  │
│  │ • 权限规则   │  │ • 执行日志   │  │ • 会话持久化       │  │
│  │ • 安全审计   │  │ • 成本追踪   │  │ • 跨 Agent 续接    │  │
│  │ • Hook 链    │  │ • 健康报告   │  │ • 交接文档生成     │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  🧠 Ghost Agent Layer（后台小脑）                    │    │
│  │  • 配属独立廉价模型（Flash/Haiku/DeepSeek/Ollama）   │    │
│  │  • 自动执行压缩、记忆提取等 LLM 任务                 │    │
│  │  • 发送前自动脱敏（[privacy] 规则）                  │    │
│  │  • 三级降级：LLM → 提取式 → 原始快照                 │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Skill Ecosystem                            │
│   core-skills/     927-ai-skills/     community-skills/      │
│   (7 → 15+)       (80+ private)      (future)               │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 六大引擎详解

#### 引擎 1：Context Engine（上下文引擎）

**这是 KitClaw 最大的能力空白。** Claude Code 的核心竞争力很大程度上来自它。

```python
class ContextEngine:
    """管理对话上下文的生命周期——内部通过 Ghost Agent 实现 LLM 推理"""

    def estimate_tokens(self, messages: list[dict]) -> int:
        """估算当前上下文 token 数（tiktoken + 字数 fallback）"""

    def should_compact(self, messages, model: str) -> bool:
        """判断是否需要压缩（基于模型的上下文窗口）"""

    def compact(self, messages) -> CompactResult:
        """执行压缩：内部调用 Ghost Agent 生成摘要 + 保留关键消息
        无需前台 Agent 参与，全自动闭环"""

    def snapshot(self, session_id: str) -> None:
        """保存会话快照（断点续接用）"""
```

**关键设计借鉴自 Claude Code**：
- **阈值公式**：`context_window - max_output_tokens - buffer(13k)` 时触发（来自 `autoCompact.ts`）
- **熔断器**：连续 3 次压缩失败后停止重试（来自 `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES`）
- **压缩 prompt** 保留：主要请求、关键技术细节、进度、当前状态、下一步（来自 `compact/prompt.ts`）
- **Ghost Agent 执行**：压缩由 KitClaw 内置的廉价小模型完成，不消耗前台 Agent 的算力和注意力

#### 引擎 2：Memory Engine（记忆引擎）— 升级现有

现有 memory-manager 的问题：**完全被动，只在 Agent 想起来时才工作。**

升级方向：

| 现状 | v2 目标 |
|------|---------|
| 手动 `l2-capture --apply` | Agent 对话结束时**自动提取** |
| 只写 `whiteboard.json` | 按主题**独立文件** + 索引 |
| 无去重 | 写入前**语义去重**（编辑距离 + 关键词） |
| grep 检索 | grep + **向量混合检索**（RAG engine 已有） |
| 无过期机制 | 自动标记 stale → archive |
| 无记忆分类 | 4 类分类法：`preference / fact / learning / decision` |

**核心新增：Ghost Agent 驱动的自动记忆提取**

```bash
# Agent 只需简单调一条命令
kitclaw session end

# KitClaw 内部（Ghost Agent）自动完成：
# 1. 对话数据脱敏（[privacy] 规则）
# 2. 发送给后台小模型提取 preference/fact/learning/decision
# 3. 与已有记忆去重（编辑距离 + 关键词匹配）
# 4. 加文件锁 → 写入 topics/*.md → 释放锁
# 全程无需前台 Agent 参与
```

**与 Claude Code 的对比**：
- Claude Code 用 `runForkedAgent` 分叉自己的进程 → 昂贵（用同一个大模型）
- KitClaw 用独立配置的廉价小模型 → 成本几乎为零（~$0.01/次）

#### 引擎 3：Skill Router & Orchestrator（路由与编排引擎）

现状问题：Agent 只能靠 `SKILL.md` 的 description 文字来猜测该调用哪个 skill。

v2 增加三层路由：

```
Layer 1: 关键词匹配（现有的 description + triggers）
Layer 2: 路径条件激活（借鉴 Claude Code 的 paths frontmatter）
Layer 3: 上下文感知（根据当前文件类型/项目类型推荐 skill）
```

**编排能力**（借鉴 Agent Toolchain 的 `agent-orchestrator`）：

```yaml
# workflows/code-review.yaml
name: code-review
steps:
  - skill: knowledge-search
    args: { query: "项目代码规范", mode: "hybrid" }
    output_as: standards

  - skill: context-engine
    action: snapshot
    note: "保存审查前的上下文"

  - skill: security-audit
    args: { target: "${file_path}" }
    output_as: security_report
    parallel: true

  - skill: l2-capture
    args:
      project: "${project}"
      from_text: "审查结论: ${security_report.summary}"
    condition: "${security_report.issues_count > 0}"
```

#### 引擎 4：Governance Engine（治理引擎）— 升级现有

现状：只有一个 pre-commit hook + 一个 auditor 脚本。

v2 升级为**全生命周期治理**：

```
Skill 生命周期钩子：
  pre-install   → 安全扫描（skill-security-audit）
  pre-execute   → 权限检查 + 输入校验
  post-execute  → 输出审计 + 自动 L2 + 观测记录
  on-error      → 错误收集 + 重试策略
  on-uninstall  → 清理检查

权限模型（借鉴 Claude Code 的 PermissionRule）：
  allow: FileRead(*)           # 允许所有文件读取
  allow: BashTool(npm *)       # 允许 npm 命令
  deny:  BashTool(rm -rf *)   # 禁止危险删除
  ask:   FileWrite(src/**)     # 写 src 目录前询问
```

#### 引擎 5：Observability Engine（观测引擎）— 升级现有

现状：`skill-observability` 只做 JSONL 日志。

v2 升级：

```
执行日志 → 已有 ✅
成本追踪 → 新增（记录每次 API 调用的 token/cost）
会话报告 → 新增（每个会话结束时生成摘要报告）
健康仪表盘 → 新增（哪些 skill 最常用、失败率、平均耗时）
趋势分析 → 新增（记忆增长趋势、知识库覆盖度）
```

#### 引擎 6：Session Manager（会话管理器）

**全新能力**，没有现有对应物。

```python
class SessionManager:
    """跨 Agent 的会话状态管理"""

    def start_session(self, agent: str, project: str) -> Session:
        """开始新会话，加载 L1 + 相关 L2 + L3 检索"""

    def resume_session(self, session_id: str) -> Session:
        """从快照恢复会话（支持换 Agent 续接）"""

    def end_session(self, session: Session) -> SessionReport:
        """结束会话（Ghost Agent 全自动闭环）：
        1. 如果超阈值 → Ghost Agent 压缩上下文
        2. Ghost Agent 提取记忆 → 文件锁 → 写入 topics/
        3. 保存会话快照
        4. 生成交接文档（供下一个 Agent 使用）
        5. 降级保护：Ghost Agent 不可用时保存原始快照"""

    def handoff(self, from_agent: str, to_agent: str, session_id: str):
        """Agent 间会话交接（Ghost Agent 生成交接文档）"""
```

**杀手功能：跨 Agent 会话续接**

```
场景：用 Claude Code 写了半天代码，切换到 Gemini 继续

1. Claude Code 会话结束 → SessionManager.end_session()
   → 自动 compact
   → 自动提取 L2 记忆
   → 保存会话快照

2. Gemini 开始 → SessionManager.resume_session()
   → 加载压缩后的上下文摘要
   → 加载相关 L2/L3 记忆
   → Gemini 完全了解之前的进度
```

这是 KitClaw 独有的价值主张——**Claude Code 永远不会帮你续接到 Gemini**。

---

## 第四部分：Skill 体系升级

### 4.1 SKILL.md v2 规范

```yaml
---
name: context-engine
version: "2.0"
description: >
  智能上下文管理：token 估算、自动压缩、会话快照。
  当对话过长、需要压缩、或需要保存/恢复会话时使用。

# ===== v2 新增字段 =====

activation:
  paths:                          # 路径条件激活
    - "**/*.ts"
    - "**/*.py"
  triggers:                       # 关键词触发
    - "压缩对话"
    - "上下文太长"
    - "compact"
  context:                        # 上下文条件
    min_tokens: 50000             # token 超过此值时推荐
    file_types: ["ts", "py"]      # 操作这些文件类型时推荐

lifecycle:
  pre_execute:                    # 执行前钩子
    - "validate-input"
  post_execute:                   # 执行后钩子
    - "log-execution"
    - "auto-l2-capture"

dependencies:                     # 依赖的其他 skill
  required:
    - memory-manager
  optional:
    - knowledge-search

permissions:
  reads:                          # 需要读取的路径
    - "~/.ai-memory/"
  writes:                         # 需要写入的路径
    - "~/.ai-memory/sessions/"
  network: false                  # 是否需要网络

io:
  input:
    - type: json_data
      schema: "schemas/compact-input.json"
  output:
    - type: json_data
      schema: "schemas/compact-output.json"
---
```

### 4.2 Core Skills v2 清单

| # | Skill | 现有 | v2 状态 | 核心变化 |
|---|-------|------|---------|----------|
| 1 | `memory-manager` | ✅ | **重构** | 增加自动提取、语义去重、按主题存储 |
| 2 | `l2-capture` | ✅ | **增强** | 增加自动模式（会话结束时自动调用） |
| 3 | `conversation-distiller` | ✅ | **增强** | 增加增量模式、自动触发 |
| 4 | `knowledge-search` | ✅ | **增强** | 混合检索默认启用、缓存机制 |
| 5 | `skill-observability` | ✅ | **扩展** | 成本追踪、健康报告、趋势分析 |
| 6 | `mcp-export` | ✅ | 保持 | — |
| 7 | `skill-security-audit` | ✅ | **扩展** | 支持运行时权限检查 |
| 8 | `context-engine` | ❌ | **新增** | 对话压缩、token 监控、快照 |
| 9 | `session-manager` | ❌ | **新增** | 会话持久化、跨 Agent 续接 |
| 10 | `skill-router` | ❌ | **新增** | 条件激活、上下文路由、编排 |
| 11 | `auto-memory-extract` | ❌ | **新增** | 异步/自动记忆提取（从 Claude Code 学到的） |
| 12 | `plan-mode` | ❌ | **新增** | 结构化计划创建与验证 |
| 13 | `cost-tracker` | ❌ | **新增** | API 调用成本累积追踪 |
| 14 | `session-handoff` | ❌ | **新增** | Agent 间会话交接协议 |
| 15 | `governance-hooks` | ❌ | **新增** | 全生命周期钩子框架 |

---

## 第五部分：KitClaw 的差异化壁垒

### Claude Code 做不到、但 KitClaw 能做到的事

1. **跨 Agent 记忆共享** — Claude Code 的记忆永远锁在 `~/.claude/` 里。KitClaw 的 L2/L3 是跨 Agent 的。

2. **跨 Agent 会话续接** — 在 Claude Code 里工作到一半，切换到 Gemini 继续。只有 Agent-agnostic 的中间件才能做到。

3. **统一治理** — 一套权限规则、审计日志、质量门控，覆盖所有 Agent。不是每个 Agent 各搞一套。

4. **Skill 可移植性** — 写一次 skill，所有 Agent 都能用。不是 Claude Code 的 TypeScript 工具，也不是 Cursor 的 rules。

5. **人类可编辑的知识层** — L3 就是 Markdown 文件。人可以在 Obsidian 里编辑，Agent 可以检索。Claude Code 的 memdir 是 Agent 私有的。

### 这些壁垒的商业含义

```
用户选择 KitClaw 的理由不是"它比 Claude Code 更好"
而是"它让我不被任何一个 Agent 锁定"

KitClaw = Agent 世界的中间件层
就像 Docker 不替代操作系统，但你离不开它
```

---

## 第六部分：实施路线图

### Phase 0：基础设施 + Ghost Agent 核心（1 周）

> 目标：让 KitClaw 从"脚本集合"变成"有后台脑力的可安装运行时"

- [ ] 统一入口 CLI：`kitclaw <command>` 替代分散的 `python3 ~/.ai-skills/xxx/scripts/yyy.py`
- [ ] `kitclaw init` — 初始化工作区（创建配置、symlinks、引导 Ghost Agent API key）
- [ ] `kitclaw status` — 显示当前状态（记忆数、Ghost Agent 可用性、成本）
- [ ] `kitclaw doctor` — 健康检查（依赖、路径、API key、config.toml 权限）
- [ ] 包结构重组：从 flat scripts → Python package（`pip install kitclaw`）
- [ ] Ghost Agent 核心模块：`engines/ghost_agent.py`（纯 stdlib urllib API 调用）
- [ ] Privacy 模块：`utils/privacy.py`（发送前脱敏）
- [ ] FileLock 模块：`utils/filelock.py`（基于 lockfile 的并发控制）

### Phase 1：Context Engine + Session Manager（2 周）

> 目标：解决最大的能力空白

- [ ] `kitclaw compact` — 对话压缩（带 prompt 模板）
- [ ] `kitclaw session start/end/resume/list`
- [ ] Token 估算器（tiktoken 或字数估算 fallback）
- [ ] 会话快照持久化（JSON + 压缩摘要）
- [ ] 在 AGENTS.md 模板中注入"会话结束时自动调用"的指令

> 🟡 **先行实现**：`~/.ai-skills/project-manager/scripts/kit-start.py`
> 已实现"新对话前自动注入项目简报到剪贴板"的手动版本。
> 等 `kitclaw session start` CLI 完成后，将其内化为 `session start` 的一步，自动完成上下文注入。


### Phase 2：Memory Engine 升级（2 周）

> 目标：让记忆从"被动"变"主动"

- [ ] `kitclaw memory extract` — 从对话自动提取记忆
- [ ] 自动去重（编辑距离 + 关键词匹配）
- [ ] 按主题独立文件存储（替代单一 whiteboard.json）
- [ ] 记忆过期/归档机制
- [ ] 4 类分类法实现

### Phase 3：Skill Router + Governance Hooks（2 周）

> 目标：让 skill 路由从"猜测"变"智能"

- [x] **SKILL.md v2 规范（activation 字段）** ← ✅ 已在 `project-manager/SKILL.md` 中先行落地（`triggers` / `activation.paths` / `activation.context` / `guardrails` 四段）
- [ ] 条件激活引擎（paths + triggers + context）— 规范已定义，执行引擎待实现
- [ ] 全生命周期 hooks 框架
- [ ] `kitclaw run <skill>` — 统一 skill 执行入口（含 hooks）
- [ ] 编排 YAML 执行器

> 🟡 **先行原型**：`~/.ai-skills/project-manager/scripts/stale-detector.py`
> 已实现数据驱动的 Guardrail 检测（代码停滞 / 变更堆积 / 未完成指令 / 悬挂分支），输出风险等级并建议触发 project-manager。
> 待 `kitclaw run` 和 hooks 框架完成后，将其接入为内置 `pre-execute guardrail hook`。


### Phase 4：Polish + 跨 Agent 协议（2 周）

> 目标：让 KitClaw 真正可用于生产

- [ ] Agent Setup 自动化：`kitclaw setup claude/gemini/codex`
- [ ] 跨 Agent 会话交接（session-handoff）
- [ ] 成本追踪集成
- [ ] 健康仪表盘（CLI 报告）
- [ ] 文档重写、README 重写

---

## 第七部分：成败判断标准

### KitClaw v2 成功的标志

1. **用户能说出一句话**："我用 KitClaw 管理我的所有 Agent"——而不是"我有一些共享 skill"
2. **切换 Agent 时零摩擦**——上下文、记忆、进度全部自动带过去
3. **记忆自动沉淀**——用户不需要手动说"记到 L2"，系统自己提取
4. **上下文永远不会爆**——自动压缩在后台默默工作
5. **一个命令了解全局**——`kitclaw status` 就能看到所有 Agent 的活动、记忆、成本

### 失败的标志

1. 还是需要用户手动 `python3 ~/.ai-skills/xxx/scripts/yyy.py`
2. 记忆仍然只在某个 Agent 里
3. 换 Agent 时要从头解释上下文
4. 文档很多但没人用

---

## 第八部分：与 Claude Code 的关系

KitClaw v2 不是要"克隆 Claude Code"。三者关系是：

```
Claude Code  = 一辆跑车（功能强大但只能跑一个赛道）
KitClaw v2   = 赛道的基础设施（加油站、维修站、赛道监控——适用于任何车）
Ghost Agent  = 基础设施里的维修机器人（有自己的小脑，不替代跑车但自动干脏活）
```

从 Claude Code 学到的 + KitClaw 的超越：

| Claude Code 机制 | 学到了什么 | KitClaw 如何超越 |
|------------------|-----------|------------------|
| `autoCompact.ts` | 阈值公式 + prompt 模板 | Ghost Agent 自动执行，不消耗前台算力 |
| `extractMemories.ts` | 4 类分类法 + 去重逻辑 | 按主题独立文件 + 跨 Agent 共享 |
| `loadSkillsDir.ts` | paths 条件激活 | 三层路由（关键词 + 路径 + 上下文） |
| `useCanUseTool.tsx` | 工具 hooks 设计模式 | 全生命周期钩子 + YAML 编排 |
| `runForkedAgent()` | 分叉子进程模式 | Ghost Agent = 独立廉价小模型，成本 <1% |
| `sessionStorage.ts` | 会话持久化 | 跨 Agent 续接（Claude Code 做不到） |
| `memdir/` | 目录化记忆 | L3 = Obsidian 人类可编辑 |

不从 Claude Code 学的：
- ❌ TypeScript 单体架构（KitClaw 保持 Python + 模块化 + 零外部依赖）
- ❌ 私有 Agent 绑定（KitClaw 保持 Agent 无关）
- ❌ Feature Flag / A/B 测试（过重）
- ❌ 商业功能（OAuth、计费、远程桥接）
- ❌ Ink/React TUI（KitClaw 不做前端交互）

---

## 附：技术选型建议

| 组件 | 推荐 | 理由 |
|------|------|------|
| CLI 框架 | `click` 或 `typer` | Python 标准、零学习曲线 |
| Token 估算 | `tiktoken` + 字数 fallback | 精确 + 零依赖降级 |
| 向量检索 | LanceDB（现有） | 已集成，够用 |
| 会话存储 | JSON 文件 + gzip | 零依赖，Git 友好 |
| 编排引擎 | YAML + Python eval | 声明式，可审计 |
| 项目配置 | `~/.kitclaw/config.toml` | 比 JSON 更人类友好 |
| 包分发 | PyPI (`pip install kitclaw`) | Python 标准分发 |
