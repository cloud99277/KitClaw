---
title: "Claude Code → KitClaw 架构融合方案"
tags: [claude-code, kitclaw, architecture, extraction]
scope: dev
---

# Claude Code → KitClaw 架构融合方案

> **目标**：从 Claude Code 源码中提取有价值的设计模式和机制，融合到 KitClaw 体系中，增强 KitClaw 的能力而不破坏其轻量、跨 Agent 的核心定位。

---

## 一、两者定位差异（决定融合策略）

| 维度 | Claude Code | KitClaw |
|------|-------------|---------|
| 本质 | 单体 Agent 产品（TypeScript/Bun） | 跨 Agent 能力运行时（Python + Markdown） |
| 记忆 | memdir（自动记忆提取 + 文件系统） | 三层记忆模型（L1/L2/L3） |
| Skill | SKILL.md + frontmatter 路由 + 条件激活 | SKILL.md + scripts/ + 观测性 |
| 工具 | 40+ 内置工具（TypeScript class） | 通过 scripts/ 暴露的 CLI 工具 |
| 压缩 | autoCompact（token 阈值自动压缩） | 无等价物 |
| 权限 | 精细的 rule-based 权限系统 | governance hooks |
| 子代理 | AgentTool（fork 子代理） | 无 |
| 协调 | Coordinator Mode（多 Agent 编排） | 无 |

**融合原则**：不搬运 Claude Code 的 TypeScript 实现，而是提取其**设计模式**，用 KitClaw 的 Python/Markdown 体系重新实现。

---

## 二、值得提取的 7 个核心机制

### 机制 1：自动上下文压缩（autoCompact）

**Claude Code 实现**：
- `services/compact/autoCompact.ts` — 基于 token 阈值自动触发
- `services/compact/compact.ts` — 核心压缩逻辑
- 用 forked agent 生成对话摘要，替换旧消息
- 有 `AUTOCOMPACT_BUFFER_TOKENS = 13,000` 等精确阈值
- 支持环境变量覆盖（`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`）
- 有熔断器：连续失败 3 次后停止重试

**KitClaw 融合方案**：
```
core-skills/
  context-compact/
    SKILL.md
    scripts/
      compact-conversation.py    # 核心压缩逻辑
      estimate-tokens.py         # token 计数
    references/
      compact-prompt-template.md # 压缩 prompt 模板
```

**关键设计点**：
- 不做实时 autoCompact（KitClaw 不控制 Agent 循环），做**按需触发**
- 当 Agent 检测到上下文过长时调用 `compact-conversation.py`
- 输入：当前对话的 JSON/文本导出
- 输出：压缩后的摘要 + 关键决策保留
- 压缩 prompt 直接参考 Claude Code 的 `prompt.ts`

**优先级**：⭐⭐⭐⭐⭐（最高）— 所有长对话 Agent 都需要

---

### 机制 2：自动记忆提取（extractMemories）

**Claude Code 实现**：
- `services/extractMemories/extractMemories.ts`
- 每个 query 循环结束时，用 forked agent 异步提取记忆
- 记忆写入 `~/.claude/projects/<path>/memory/` 的独立文件
- 4 类记忆分类法（frontmatter + 文件系统）
- 有 MEMORY.md 索引文件（限 200 字符/行）
- 先检查已有记忆再写新的（去重）

**KitClaw 融合方案**：
增强现有 `memory-manager` 和 `l2-capture`：

```
core-skills/
  auto-memory-extract/
    SKILL.md
    scripts/
      extract-from-conversation.py  # 从对话中自动提取
      dedup-memories.py              # 去重/合并
    references/
      extraction-prompt.md           # 提取 prompt 模板
      memory-taxonomy.md             # 4 类分类法说明
```

**与现有 KitClaw 的区别**：
- 当前 `l2-capture` 需要手动触发 → 新增**自动触发**能力
- 当前只写 `whiteboard.json` → 增加**按主题独立文件**
- 借鉴 Claude Code 的 "先扫描已有 → 再决定是否新写" 逻辑

**优先级**：⭐⭐⭐⭐⭐ — 直接升级 KitClaw 记忆层

---

### 机制 3：Skill 条件激活（Conditional Skills）

**Claude Code 实现**：
- `skills/loadSkillsDir.ts` — 动态 Skill 加载
- 支持 SKILL.md frontmatter 中的 `paths` 字段
- 使用 gitignore 风格匹配：当操作匹配路径时自动激活 Skill
- `activateConditionalSkillsForPaths()` — 文件操作触发
- `${CLAUDE_SKILL_DIR}` 变量替换
- 支持 `effort` 级别（quick/thorough 等）

**KitClaw 融合方案**：
扩展 `skill-specification.md`，增加条件激活协议：

```yaml
# SKILL.md frontmatter 扩展
---
name: react-component-creator
description: ...
activation:
  paths:                          # gitignore 风格路径匹配
    - "src/components/**/*.tsx"
    - "src/pages/**/*.tsx"
  triggers:                       # 关键词触发
    - "创建组件"
    - "新建页面"
  effort: quick                   # quick | thorough | exhaustive
---
```

**关键价值**：让 Skill 从"Agent 手动匹配描述"升级为"根据工作上下文自动激活"。

**优先级**：⭐⭐⭐⭐ — KitClaw Skill 路由的显著升级

---

### 机制 4：工具执行 Hooks 体系

**Claude Code 实现**：
- `utils/hooks/` — pre/post tool use hooks
- `hooks/useCanUseTool.tsx` — 工具权限判断
- `services/toolHooks.ts` — 工具生命周期钩子
- pre-hook：执行前校验/转换输入
- post-hook：执行后处理输出/记录

**KitClaw 融合方案**：
在 `governance/` 下新增 Skill 执行钩子协议：

```
governance/
  hooks/
    pre-skill.sh        # Skill 执行前校验
    post-skill.sh       # Skill 执行后处理
    skill-hooks.md      # 钩子协议文档
```

**具体钩子**：
1. **pre-skill**：校验输入安全性、检查依赖、日志记录
2. **post-skill**：输出校验、自动 L2 capture、观测记录
3. **on-error**：错误收集、重试策略

**与现有 governance 的关系**：当前 governance 只有 pre-commit hook，这相当于把治理延伸到 Skill 运行时。

**优先级**：⭐⭐⭐ — 治理层自然延伸

---

### 机制 5：Session Memory（会话记忆流式提取）

**Claude Code 实现**：
- `services/SessionMemory/sessionMemoryUtils.ts`
- 阈值驱动：`minimumMessageTokensToInit: 10000`
- 增量提取：每 `5000 tokens` 或 `3 次工具调用`后更新
- 防抖：15 秒超时 + 1 分钟过期检测
- 与 autoCompact 共享 token 计数

**KitClaw 融合方案**：
增强 `conversation-distiller`，增加**流式/增量模式**：

```
core-skills/
  conversation-distiller/
    scripts/
      distill.py                      # 现有：全量蒸馏
      distill-incremental.py          # 新增：增量蒸馏
    references/
      incremental-thresholds.md       # 阈值配置
```

**设计**：
- Agent 每 N 轮对话后调用 `distill-incremental.py`
- 输入：上次蒸馏后的新消息
- 输出：追加到 session memory 文件
- 与 `l2-capture` 联动：蒸馏结果中的结论自动写入 L2

**优先级**：⭐⭐⭐⭐ — 长会话体验关键

---

### 机制 6：计划模式（Plan Mode）

**Claude Code 实现**：
- `tools/EnterPlanModeTool/` — 进入计划模式
- `tools/ExitPlanModeTool/` — 退出计划模式
- `tools/VerifyPlanExecutionTool/` — 验证计划执行
- 计划文件持久化到 `utils/plans.ts`
- 计划在 compact 时被特殊保留

**KitClaw 融合方案**：
```
core-skills/
  plan-mode/
    SKILL.md
    scripts/
      create-plan.py          # 创建结构化计划
      verify-plan.py          # 验证执行进度
      plan-to-l2.py           # 计划结论沉淀到 L2
    references/
      plan-template.md        # 计划文档模板
```

**关键设计**：
- 计划文件作为 Markdown 存储，人类可读可编辑
- 执行时各步骤自动与 L2 `[action]` 关联
- 验证时对比计划 vs 实际执行

**优先级**：⭐⭐⭐ — 复杂任务管理能力

---

### 机制 7：File State Cache（文件状态缓存）

**Claude Code 实现**：
- `utils/fileStateCache.ts` — 文件读取缓存
- 记录已读文件的内容/hash，避免重复读取
- 支持 `FILE_UNCHANGED_STUB`（文件未变化时用存根替代）
- 子代理继承父代理的缓存

**KitClaw 融合方案**：
```
core-skills/
  knowledge-search/
    scripts/
      file-state-cache.py    # 文件状态缓存管理
```

**设计**：
- 每次 `knowledge-search` 执行时维护一个 `.file-cache.json`
- 记录文件 hash + 最后读取时间
- RAG 增量索引时利用缓存跳过未变化的文件

**优先级**：⭐⭐ — 性能优化

---

## 三、立即可做的快速融合（Quick Wins）

### 3.1 借鉴 Claude Code 的 compact prompt 模板

直接把 `services/compact/prompt.ts` 的压缩 prompt 翻译成 KitClaw 的 `references/` 文件：

```markdown
<!-- references/compact-prompt-template.md -->
Your task is to create a detailed summary of the conversation so far,
paying close attention to the user's explicit requests and preferences.

Your summary should include:
1. **Primary Request**: The main task or objective
2. **Key Technical Details**: Specific files, errors, constraints
3. **Progress Made**: What was completed, what's pending
4. **Current State**: Where the conversation left off
5. **Next Steps**: What should happen next (with direct quotes)
```

### 3.2 在 SKILL.md spec 中增加 activation 字段

在 `docs/skill-specification.md` 的 YAML frontmatter 标准中增加：

```yaml
activation:
  paths: []           # gitignore 风格路径匹配
  triggers: []        # 关键词触发列表
  effort: quick       # quick | thorough | exhaustive
  min_context: 0      # 最小上下文 token 数
```

### 3.3 自动 L2 提取 prompt 模板

把 Claude Code 的 `extractMemories/prompts.ts` 转化为：

```
core-skills/memory-manager/references/auto-extract-prompt.md
```

4 类分类法：
- `user_preference` — 用户偏好和工作方式
- `project_fact` — 项目事实和约束
- `learning` — 发现的规律和陷阱  
- `decision` — 做出的选择及原因

---

## 四、实施路线图

### Phase 1：Prompt 模板移植（1-2 天）
- [ ] 提取 compact prompt → `context-compact/references/`
- [ ] 提取 memory extraction prompt → `memory-manager/references/`
- [ ] 更新 `skill-specification.md` 增加 `activation` 字段

### Phase 2：核心 Skill 开发（3-5 天）
- [ ] 开发 `context-compact` skill（含 token 估算）
- [ ] 开发 `auto-memory-extract` skill
- [ ] 增强 `conversation-distiller` 增量模式

### Phase 3：治理与高级功能（5-7 天）
- [ ] 实现 Skill 执行 hooks（pre/post）
- [ ] 开发 `plan-mode` skill
- [ ] 条件 Skill 激活路由实现

### Phase 4：优化（按需）
- [ ] File state cache 集成到 RAG
- [ ] Session memory 增量提取
- [ ] 多 Agent 协调模式探索

---

## 五、关键参考文件索引

| 用途 | Claude Code 源文件 |
|------|-------------------|
| 压缩 prompt | `src/services/compact/prompt.ts` |
| 自动压缩逻辑 | `src/services/compact/autoCompact.ts` |
| 压缩核心 | `src/services/compact/compact.ts` |
| 记忆提取 | `src/services/extractMemories/extractMemories.ts` |
| 记忆提取 prompt | `src/services/extractMemories/prompts.ts` |
| Session Memory | `src/services/SessionMemory/sessionMemoryUtils.ts` |
| Skill 加载 | `src/skills/loadSkillsDir.ts` |
| 记忆目录系统 | `src/memdir/memdir.ts`, `paths.ts`, `memoryScan.ts` |
| 权限规则 | `src/utils/permissions/permissionRuleParser.ts` |
| 工具接口 | `src/Tool.ts` |
| 协调器模式 | `src/coordinator/coordinatorMode.ts` |
| AgentTool | `src/tools/AgentTool/runAgent.ts` |
| 计划模式 | `src/tools/EnterPlanModeTool/`, `VerifyPlanExecutionTool/` |
| 工具钩子 | `src/hooks/useCanUseTool.tsx` |
| 上下文分析 | `src/utils/contextAnalysis.ts` |

---

## 六、不建议融合的部分

| Claude Code 机制 | 不融合原因 |
|-------------------|-----------|
| TypeScript 工具实现 | KitClaw 用 Python，直接搬不现实 |
| Ink/React 终端 UI | KitClaw 是 headless，无需 TUI |
| Anthropic SDK 绑定 | KitClaw 是 Agent 无关的 |
| Feature Flag 系统 | 内部 A/B 测试机制，KitClaw 不需要 |
| Bridge/远程桥接 | 过重，不符合 KitClaw 轻量定位 |
| Daemon/守护进程 | 过重，不符合 skill-based 架构 |
| OAuth/认证流程 | 绑定 Anthropic 账号体系 |
