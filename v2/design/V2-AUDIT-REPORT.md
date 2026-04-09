# KitClaw v2 架构规划 — 架构审查总结

> **审查视角**：顶级系统架构师
> **审查对象**：`v2/design/*.md` (全部 7 份设计文档)
> **审查日期**：2026-04-07

## 总评

**架构方向正确率估计：8/10**

**最大风险一句话**：CLI 工具的同步执行模式与 Agent 的异步大模型推理能力（如生成摘要、提取记忆）之间的握手协议设计存在明显断层，可能导致自动化失效。

## 🔴 结构性问题（2 个）

### 问题 1：CLI 与 Agent 模型推理的握手断层

**诊断**：
在 `memory-engine.md` 中写道：`kitclaw session end` 会“生成提取 prompt → 返回 prompt 给 Agent → Agent 执行 → 解析结果”。
但 `kitclaw` 是一个同步的 CLI 工具，它自己不能凭空调用 LLM（因为坚持了"Agent 无关"和"不绑定 SDK"的原则）。当 Agent 运行 `kitclaw session end` 时，CLI 打印了一段 Prompt 让 Agent 去执行，**但执行后 Agent 怎么把结果交回给 KitClaw 完成后续的"去重+写入"闭环？**目前设计中没有定义如何让单次 CLI 命令变成一个"分步握手流"。

**后果**：
`auto-compact` 和 `auto-extract` 无法达到真正的"一次命令，全自动完成"，必定需要 Agent 手动参与多轮交互，严重破坏了用户体验。

**建议**：
方案已被采纳：根据 `RFC-002`，引入 **影子 Agent (Ghost Agent) 模型**。
- KitClaw 在其 `config.toml` 中配属独立的轻量 API（如 Gemini 1.5 Flash）。
- 处于后台执行时，直接向后发包处理文本进行压缩推断。
- 彻底斩断对“前台 Agent ”的模型依赖，全量实现底层无感自动化闭环。

### 问题 2：并发读写的竞争条件（Race Conditions）

**诊断**：
KitClaw v2 没有常驻 daemon，完全依靠文件系统状态（如 `topics/*.md`、`sessions/index.json`）。当用户打开多个 IDE 窗口同时运行不同 Agent（例如 Cursor + Claude Code + Gemini），这些 Agent 如果同时触发 `l2-capture` 或 `session end`，同时写入 Markdown 文件和 JSON 索引，引发并发损坏风险。

**后果**：
记忆库索引 JSON 可能被覆盖写坏，导致严重的记忆丢失。

**建议**：
在 Storage Layer 中必须引入基于文件系统的**排他文件锁机制**（File Locking）。读取、去重、写入必须放入原子锁块（Atomic Lock Block）内。需要补充这部分的基础设施设计。

## 🟡 设计盲点（3 个）

### 盲点 1：模型跨度导致的 Token 估值不一致
**缺什么**：`context-engine` 中提到 `tiktoken` 默认用 `sonnet` 估算，但不同模型的分词器差异极大（比如 Gemini 2.5 vs GPT-4o）。
**为什么重要**：如果 Agent A（Gemini）和 Agent B（Claude）交接会话，用同样的 `BUFFER_TOKENS` 计算可能会因为估算偏差提前触发截断。
**建议**：在 `estimate_tokens` 中，如果无法找到对应模型的精确规则，应预留更大的安全 Buffer（如 20% 冗余）。

### 盲点 2：会话状态的过期自动清理机制触发点
**缺什么**：设计中提到 `cleanup` 淘汰 30 天前的快照，但没有定义**谁来触发**这个动作。
**为什么重要**：由于没有 daemon，没有人定期清理，硬盘会被 `context.json.gz` 慢慢塞满。
**建议**：把 `cleanup` 作为以 5% 的低概率植入到每次 `kitclaw session start` 时的前置副业，实现懒清理（Lazy Garbage Collection）。

### 盲点 3：Rule-Based Permission 的边界
**缺什么**：Governance 中的 `ask` 模式，如何中断 CLI 让 Agent 去询问人类？
**为什么重要**：如果是 Agent 在后台自动运行的 workflow（如 `auto-l2-capture` 被触发），遇到 `ask` 权限时，CLI 不能堵塞在 `input()` 上（Agent 通常无法处理交互式 TTY），会导致死锁。
**建议**：CLI 在非 TTY 模式下遇到 `ask`，应直接 `exit 1` 并输出带有固定格式的错误，要求 Agent 本身向用户询问，拿到批准后加上特定 `token/flag` 重新执行。

## 🟢 优化建议（2 个）

## 修改建议汇总表

| # | 类型 | 建议 | 影响范围 |
|---|------|------|---------|
| 1 | 🔴 | 明确 CLI 与 Agent 之间的"握手协议"（多轮任务接力） | Skill Router / Session Manager |
| 2 | 🔴 | 增加文件级锁机制防止多 Agent 并发写入损坏数据 | Architecture (Storage层) |
| 3 | 🟡 | 引入基于随机概率的垃圾回收机制（Lazy GC） | Session Manager |
| 4 | 🟡 | 定义 TTY 与非 TTY 下的权限询问行为 | Governance Engine / CLI |
| 5 | 🟢 | Token 估算引入针对特定模型的宽容度系数 | Context Engine |

## 结论

**需要修订后再审查**。
v2 整体的 "Middleware" 定位非常精准，六大引擎的拆分也很科学。但由于坚持无 Daemon、纯 CLI 的架构，部分**交互范式和并发保证**存在硬伤。修改时重点补充：**基于文件锁的并发控制** 和 **多轮 CLI 接力机制**。
