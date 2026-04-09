# KitClaw v2 — Planning Hub

> **定位转型**：从 "共享 Skill 脚本集" → "有自己后台脑力的 Agent 运行时中间件"
> **架构突破**：Ghost Agent — 配属独立廉价小模型，实现全自动压缩/记忆提取闭环

## 目录结构

```
v2/
├── README.md              ← 你在这里
├── design/
│   ├── product-strategy.md                # 产品战略（诊断 + 定位 + Ghost Agent）
│   ├── architecture.md                    # 整体架构（6 引擎 + Ghost Agent 层）
│   ├── context-engine.md                  # 上下文引擎（Ghost Agent 压缩）
│   ├── memory-engine.md                   # 记忆引擎（Ghost Agent 提取）
│   ├── session-manager.md                 # 会话管理（跨 Agent 续接）
│   ├── skill-router.md                    # Skill 路由（三层路由 + 编排）
│   ├── governance.md                      # 治理引擎（权限 + hooks）
│   ├── cli.md                             # 统一 CLI 设计
│   ├── hermes-as-runtime.md               # Hermes 作为 KitClaw 最佳运行时载体
│   ├── ghost-agent-deep-review.md         # Ghost Agent 10 维深度审查
│   └── V2-AUDIT-REPORT.md                 # v2 全套文档架构审查报告
│
├── rfcs/
│   ├── 001-runtime-vs-scripts.md           # 轻量运行时 > 纯脚本 > daemon
│   ├── 002-ghost-agent-backend.md          # Ghost Agent 后台智能闭环方案
│   ├── 003-unified-persona-engine.md       # Z7 统一人格跨 Agent 同步
│   └── 004-memory-extraction-pipeline.md   # Ghost Agent 记忆自动提取管线
│
├── prototypes/            ← 快速验证原型
│   └── (实验性代码放这里)
│
└── references/            ← 外部参考资料
    └── claude-code-patterns.md  ← 从 Claude Code 提取的设计模式
```

## 与 v1 的关系

- v1 代码保持不动，继续可用
- v2 规划在 `v2/` 目录下进行
- 代码开发在 `feat/v2` Git 分支上进行
- v2 的实际代码最终会重组整个 repo 结构

## 目标里程碑

| Phase | 内容 | 产物 | 预计 |
|-------|------|------|------|
| 0 | 统一 CLI 入口 | `kitclaw` CLI 可用 | 1 周 |
| 1 | Context Engine + Session Manager | 对话压缩和会话管理可用 | 2 周 |
| 2 | Memory Engine 升级 | 自动记忆提取可用 | 2 周 |
| 3 | Skill Router + Governance Hooks | 智能路由和生命周期钩子 | 2 周 |
| 4 | 跨 Agent 协议 + Polish | 生产就绪 | 2 周 |

## 关键参考

- [v2 产品战略](../docs/kitclaw-v2-product-strategy.md)
- [Claude Code 提取方案](../docs/claude-code-extraction-plan.md)
- [v1 记忆架构](../docs/memory-architecture.md)
- [v1 Skill 规范](../docs/skill-specification.md)
