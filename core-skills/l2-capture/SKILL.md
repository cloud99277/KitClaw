---
name: l2-capture
description: Capture concise L2 Whiteboard memory entries on top of memory-manager. Use when the user says "记到L2", "写入白板", "提炼成 L2 记忆", "记下这个决策", or wants 1-3 shared decision/action/learning entries extracted from the current task or conversation. Prefer this over calling memory-update.py directly for normal L2 writes.
io:
  input:
    - type: text
      description: 原始对话结论、文本片段，或已经标注为 [decision]/[action]/[learning] 的候选条目
  output:
    - type: json_data
      description: 候选条目、去重结果、写入结果与 whiteboard entry id
---

# l2-capture

为共享 L2 Whiteboard 提供一个薄封装写入入口。

它做四件事：

1. 接收原始文本或已经标注好的候选条目
2. 规范成 `decision` / `action` / `learning`
3. 先做去重和质量检查
4. 串行调用 `memory-manager` 完成最终写入

不要用它写 L3 文档；稳定文档仍然进入 Obsidian 知识库。

## 什么时候用

- 用户明确说“记到 L2 / 写入白板 / 记下这个决策 / 记下这个待办”
- 要从当前任务或对话中提炼 1-3 条共享记忆
- 需要避免直接调用 `memory-update.py` 时的并发与重复问题

## 快速开始

先 dry-run 看候选条目：

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project agent-toolchain \
  --from-text "[decision] 共享稳定知识统一落到 20_Knowledge_Base"
```

第二版也支持从原始总结里自动提炼：

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project agent-toolchain \
  --from-text "我们决定把共享稳定知识统一放到 20_Knowledge_Base。后续需要单独评估 Git 化方案。实测下来 L3 更适合目录监听自动入库。"
```

确认后写入：

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project agent-toolchain \
  --from-text "[decision] 共享稳定知识统一落到 20_Knowledge_Base" \
  --apply
```

支持多条：

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project agent-toolchain \
  --from-text "
[decision] OpenClaw 私有记忆不覆盖共享事实
[action] 单独评估 20_Knowledge_Base 的 Git 化方案
[learning] L3 适合目录监听自动入库
" \
  --apply
```

如果原始文本只对应一条，给定类型即可：

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project agent-toolchain \
  --type learning \
  --from-text "L3 适合目录监听自动入库；L2 更适合结构化短条目写入。" \
  --apply
```

## 输入规则

- 优先使用显式标记：
  - `[decision] ...`
  - `[action] ...`
  - `[learning] ...`
- 也支持：
  - `decision: ...`
  - `action: ...`
  - `learning: ...`
- 如果只有一条内容，可以配合 `--type`
- 如果没有显式标记，也会尝试自动提炼 1-3 条候选

## 自动提炼规则

- 优先从一句话里识别 `decision / action / learning`
- 会按关键词和句首信号做启发式分类
- 返回 `source_mode=auto` 和命中的 `signals`
- 如果内容太泛、太长，仍然会被过滤或要求你显式标注

## 默认行为

- 默认是 `dry-run`
- 只有加 `--apply` 才真正写入 `~/.ai-memory/whiteboard.json`
- 写入前会读取现有 whiteboard 做重复检查
- 真正落盘时会串行写入，避免多条并发写 whiteboard 失败

## 和 memory-manager 的分工

- `memory-manager`：底层读写与检索统一入口
- `l2-capture`：更方便的 L2 写入入口

需要了解 L2 规则时，读取：

- `~/.ai-skills/memory-manager/references/whiteboard-template.md`
