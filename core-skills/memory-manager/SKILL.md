---
name: memory-manager
description: Manage cross-agent persistent memory using a three-layer model (Identity/Session/Knowledge). Use when you need to search past decisions, actions, or learnings across conversations, or when you need to persist important information for future sessions. 当用户提到"记忆""memory""whiteboard""历史决策""跨会话""保存决策""查找历史"时触发。Prefer this for cross-session memory persistence; use brain-link or conversation-distiller for single-conversation distillation.
io:
  input:
    - type: text
      description: 检索关键词或要持久化的记忆文本
  output:
    - type: json_data
      description: 检索结果（含 L1/L2/L3 匹配条目）或写入确认
---

# memory-manager

跨 Agent 持久记忆管理 Skill，基于三层记忆模型（身份层 / 会话层 / 知识层）。

## 快速开始

### 检索记忆

```bash
# 全层检索
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词"

# 仅检索 L2 会话层（Whiteboard）
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --layer=L2

# 按项目过滤
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --project=agent-os

# 按领域搜索（仅限 L3，覆盖 config.json）
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --scope=dev       # 研发领域
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --scope=content   # 内容/社交
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --scope=personal  # 个人领域

# 组合使用
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --scope=dev --layer=L3 --json

# 输出 JSON（供其他 skill 机器消费）
python3 ~/.ai-skills/memory-manager/scripts/memory-search.py "关键词" --json
```

### 更新记忆

```bash
# 从文字中直接写入
python3 ~/.ai-skills/memory-manager/scripts/memory-update.py --from-text "决定使用 JSON 而非 chromadb" --type=decision --project=agent-os

# 从文件中提取（Agent-guided：脚本展示文件内容和提取指令，由 Agent 逐条调用 --from-text 写入）
python3 ~/.ai-skills/memory-manager/scripts/memory-update.py --from-file conversation.md --project=agent-os

# 查看当前 Whiteboard
python3 ~/.ai-skills/memory-manager/scripts/memory-update.py --list
```

如果你要更方便地把当前任务/对话提炼成 1-3 条 L2 条目，优先用：

```bash
python3 ~/.ai-skills/l2-capture/scripts/l2_capture.py \
  --project agent-toolchain \
  --from-text "[decision] 共享稳定知识统一落到 20_Knowledge_Base" \
  --apply
```

`memory-update.py` 仍然是底层入口；`l2-capture` 是更适合日常写入的上层封装。

### 监听知识库目录

```bash
# 安装稳定版 systemd 用户服务（推荐）
bash ~/.ai-skills/memory-manager/scripts/install-knowledge-watch-service.sh

# 启动目录监听
bash ~/.ai-skills/memory-manager/scripts/start-knowledge-watch.sh

# 查看状态
bash ~/.ai-skills/memory-manager/scripts/status-knowledge-watch.sh

# 停止监听
bash ~/.ai-skills/memory-manager/scripts/stop-knowledge-watch.sh

# 卸载稳定版服务
bash ~/.ai-skills/memory-manager/scripts/uninstall-knowledge-watch-service.sh
```

默认监听目录：

```text
~/knowledge-base (configure in ~/.ai-memory/config.json)
```

稳定版行为：

- 使用 `systemd --user` 托管，登录后自动拉起
- 失败自动重启
- `start/stop/status` 脚本优先走 systemd 服务
- 发现 `.md` 新增 / 修改 / 删除后，等待短暂 debounce
- 自动补全缺失 frontmatter
- 自动执行 `knowledge-search` 增量索引
- 文件日志写入 `~/.ai-memory/logs/obsidian-l3-watch.log`
- Journal 日志可用：`journalctl --user -u obsidian-l3-watch.service -n 50 --no-pager`

## 三层记忆模型

| 层级 | 内容 | 存储 | 检索策略 |
|------|------|------|---------|
| **L1 身份层** | 人格、用户画像、行为规则 | `CLAUDE.md` / 各 Agent 配置 | 始终加载 |
| **L2 会话层** | Decisions / Actions / Learnings | `~/.ai-memory/whiteboard.json` | 按需检索 |
| **L3 知识层** | 笔记、研究素材、项目资料 | Obsidian / 本地 Markdown | grep 检索 |

> L3 路径在 `~/.ai-memory/config.json` 中配置。

## 什么是 Whiteboard Memory

L2 的核心机制，从对话中提取三类条目：

- **Decision（决策）**：两个以上方案之间做了明确选择
- **Action（行动）**：承诺要做但尚未完成的任务
- **Learning（学习）**：实施中发现的规律或反模式

提取指南见 `references/whiteboard-template.md`。

## 数据存储

- **L2 数据目录**：`~/.ai-memory/`
- **Whiteboard**：`~/.ai-memory/whiteboard.json`
- **配置文件**：`~/.ai-memory/config.json`（配置 L3 路径）

首次运行时自动初始化，无需手动创建目录。

## 设计约束

- 零外部依赖（纯 Python stdlib）
- 不引入向量数据库，用 grep 覆盖 80% 检索场景
- L2/L3 数据与 skill 仓库完全分离（存放在 `~/.ai-memory/`）
- 所有数据格式含 `schema_version` 字段（对标 Phase 1 IO 契约约束）

## 参考文档

- `references/memory-architecture.md` — 三层模型详细设计
- `references/whiteboard-template.md` — Whiteboard 提取指南
