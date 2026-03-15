---
title: "Skill Runtime Architecture"
tags: [skills, runtime, architecture]
scope: dev
---

# Skill Runtime Architecture — Skill 仓库与运行时架构

> **目标**：解释 KitClaw、`927-ai-skills`、`agent-os-knowledge-base` 三者的关系，以及一个 skill 从仓库到运行时、从执行到治理的完整链路。

---

## 一、为什么要把 Skill 当成运行时

在 KitClaw 里，skill 不是一段 prompt，也不是一堆零散脚本。

它是一个可复用的运行时单元，包含：

- 路由元数据
- 可执行入口
- 可选参考资料
- 可选测试
- 可观测和治理接口

这意味着 skill 的目标不是“给模型一点提示”，而是让多个 Agent 共用一套稳定能力。

---

## 二、三个相关仓库如何分工

| 仓库 | 定位 | 主要内容 | 对外角色 |
|------|------|---------|---------|
| `KitClaw` | 公开稳定发行版 | core skills、记忆 runtime、治理、文档 | 公开安装入口 |
| `927-ai-skills` | 更大的运行时 skill 仓库 | 更多生产技能、方法论 skill、平台 skill | 生态层 |
| `agent-os-knowledge-base` | L3 引擎上游 | Markdown 切分、索引、检索、RAG 相关演进 | 引擎层 |

简化理解：

```text
KitClaw                = public curated core
927-ai-skills          = full runtime catalog
agent-os-knowledge-base = L3 engine upstream
```

---

## 三、为什么 KitClaw 不直接打包全部 Skill

因为公开核心和个人生产仓库的目标不同。

### KitClaw 适合放什么

- 通用
- 可移植
- 低个人化
- 低环境耦合
- 有清晰文档与测试

### 不适合直接进 KitClaw core 的内容

- 强依赖某个私有目录结构
- 强依赖某个 agent 私有文件格式
- 强依赖个人工作流、账号、平台或凭据
- 面向非常窄的个人场景

这就是为什么 `conversation-distiller` 经过去个人化后适合进入 KitClaw，而 `history-reader` / `history-chat` 这类强 agent 格式绑定的 skill 更适合先留在生态层。

---

## 四、运行时拓扑

KitClaw 的核心 skill 在仓库里维护，在用户机器上安装到统一 runtime 目录。

```text
KitClaw/core-skills/
    ↓ install.sh
~/.ai-skills/
    ├── memory-manager/
    ├── l2-capture/
    ├── conversation-distiller/
    ├── knowledge-search/
    └── skill-observability/
```

再通过 symlink 暴露给不同 Agent：

```text
~/.claude/skills ─┐
~/.codex/skills  ─┼──> ~/.ai-skills/
~/.gemini/skills ─┤
~/.agents/skills ─┘
```

这样做的好处：

- 多个 Agent 共用同一套 skill runtime
- 只维护一个技能目录
- skill 的更新、观测、治理更集中

---

## 五、一个 Skill 的标准结构

```text
<skill-name>/
├── SKILL.md
├── scripts/
├── references/      # optional
├── requirements.txt # optional
└── tests/           # optional
```

### `SKILL.md`

负责：

- 路由与触发说明
- 输入输出契约
- 何时使用 / 何时不要使用
- copy-paste 级用法

### `scripts/`

负责真正执行能力，例如：

- 搜索
- 写入
- 转换
- 索引
- 报告生成

### `references/`

负责为 Agent 提供更细的背景约束，而不是把一切都堆进 `SKILL.md`。

### `tests/`

负责保证 skill 的关键行为可回归验证。

---

## 六、执行链路

一个 skill 的运行链路通常是：

```text
用户请求
  ↓
Agent 根据描述与触发词匹配 SKILL.md
  ↓
进入 skill 目录并执行 scripts/<entrypoint>
  ↓
产出结果 / 读写 L2/L3
  ↓
记录到 observability 日志
  ↓
受 governance 和仓库规则约束
```

这个链路有四个关键层次：

1. **Routing**
   `SKILL.md` 决定何时被命中

2. **Execution**
   `scripts/` 决定真正做什么

3. **Observability**
   `skill-observability` 决定怎么记录执行

4. **Governance**
   hook / audit / lint / security 约束质量边界

---

## 七、KitClaw Core 与 Ecosystem 的边界

### Core Skills

KitClaw 当前核心 skill：

- `memory-manager`
- `l2-capture`
- `conversation-distiller`
- `knowledge-search`
- `skill-observability`
- `mcp-export`
- `skill-security-audit`

它们覆盖的是最基础的共享能力闭环，以及开源后的治理 / 互操作基础能力：

```text
L1/L2/L3 路由
→ L2 写入
→ L3 写入
→ L3 检索
→ 执行观测
→ MCP 元数据导出
→ Skill 静态安全审计
```

### Ecosystem Skills

更大的 skill 生态可以继续放在 `927-ai-skills`，例如：

- `skill-lint`
- `history-reader`
- `history-chat`
- 各种内容生产、研究、发布 skill

---

## 八、Skill 进入 KitClaw Core 的建议标准

一个 skill 想从生态层毕业进入 KitClaw core，建议满足：

1. **通用性**：不是只适用于某个私有项目
2. **可移植性**：默认路径、依赖、运行方式对其他用户也成立
3. **环境解耦**：不硬编码个人目录、账号、私有仓库路径
4. **可验证性**：至少有 smoke test 或回归测试
5. **文档完整**：`SKILL.md` 足够让外部用户理解与运行
6. **风险可控**：安全边界、输入输出契约清晰

---

## 九、治理层怎么介入

Skill runtime 一旦共享，就需要治理。

KitClaw 目前的治理重点：

- `governance/hooks/pre-commit`
  校验关键 Markdown frontmatter

- `governance/knowledge_auditor.py`
  审计知识库文档质量

- `skill-observability`
  记录执行日志，识别真实使用情况

- `skill-security-audit`
  对共享 skill 做仓库级静态安全扫描

- `mcp-export`
  把 skill 元数据导出给 MCP-aware runtime 消费

在更大的生态层，可以进一步引入：

- `skill-lint`

其中 `skill-lint` 更像是 skill 仓库级别的 metadata / routing 质量门。

---

## 十、推荐阅读顺序

如果你第一次接触 KitClaw，建议按这个顺序理解：

1. `README.md`
2. `docs/memory-architecture.md`
3. 本文档 `docs/skill-runtime-architecture.md`
4. `docs/skill-specification.md`
5. 核心 skill 的 `SKILL.md`

这样会先理解体系，再看单个 skill 的细节。
