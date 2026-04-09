---
project: KitClaw-V2
stage: Phase 0 — 统一 CLI 入口
owner: yangyy
last_updated: 2026-04-07
status_source: single-source-of-truth
---

# Current State

## 当前阶段目标

建立统一的 `kitclaw` CLI 入口和 Python 包结构，替代 v1 中分散的 Python 脚本，完成基础设施搭建。

## 本阶段成功标准

- [ ] 可以通过 `pip install -e .` 安装套件。
- [ ] 运行 `kitclaw status` 可以看到基本的系统状态骨架。
- [ ] 运行 `kitclaw init` 能够完成基础配置文件 `~/.kitclaw/config.toml` 的初始化工作。

## 当前 P0

- [ ] 搭建 Python Package 工程结构（`kitclaw/`）和入口 `__main__.py`。
- [ ] 引入 Click 或 Typer 框架搭建 `kitclaw` CLI 路由机制。
- [ ] 实现 `kitclaw init` 引导命令。
- [ ] 实现 `kitclaw status` 命令骨架。

## 当前 P1

- [ ] 搭建 `engines/ghost_agent.py` 基础框架及 API 请求脱敏等前置结构（Privacy模块）。

## 已完成

- [x] v2 定位与产品战略确立（`product-strategy.md`）
- [x] v2 整体架构设计，六大引擎拆解（`architecture.md`）
- [x] Ghost Agent 安全与深度审查（`ghost-agent-deep-review.md`）
- [x] PM 文件体系初始化（`pm/` 6 文件）
- [x] **[触发优化-方向1]** `kit-start.py` — 新对话启动器，生成带上下文的起手式并复制到剪贴板
- [x] **[触发优化-方向2]** `project-manager/SKILL.md` v2 frontmatter — triggers / activation.paths / guardrails 三层激活规范（先行落地）
- [x] **[触发优化-方向3]** `stale-detector.py` — 数据驱动 Guardrail 检测器（停滞/堆积/悬挂分支检测）

## 阻塞点

[当前没有阻塞点]

## 当前最大风险

v2 的范围蔓延。各种 Engine 的需求庞大，如果在无可用骨架前就陷入细节实现，会导致长时间无法交付 MVP。

## 最新决策

- 走路线 B (Agent Runtime Middleware)，用路线 C (Agent OS) 的愿景设计。
- 引入 Ghost Agent 架构，不抢前台 Agent 算力，后台纯静默自动执行。
- 保证“零常驻进程”原则（No Daemon），通过 CLI 直接解决战斗。

## 明确延期

- Context Engine & Session Manager（Phase 1）
- Memory Engine 自动提取与去重（Phase 2）
- Skill Router 三层智能分配（Phase 3）
- 跨 Agent 续接等协议支持（Phase 4）
