---
name: conversation-distiller
title: "Conversation Distiller Skill"
tags: [memory, knowledge-base, distillation]
scope: dev
description: >
  Distill the just-finished conversation into a structured Markdown note and
  optionally save it into the configured L3 knowledge base with automatic
  frontmatter completion and incremental indexing. Use when the user asks to
  save or distill the current conversation. Not for browsing historical chat
  logs.
io:
  input:
    - type: json_data
      description: 标题、正文内容、可选 base_dir 的 JSON payload
  output:
    - type: json_data
      description: 保存结果（含 path、generated_at、ingest 状态）
---

# Conversation Distiller

将当前对话提炼为一份结构化 Markdown 笔记，并把它写入 L3 知识库。

它的职责不是保存完整聊天记录，而是把可复用的结论、排查过程和最终方案沉淀为长期知识。

## 什么时候用

- 用户说“保存这段对话”“提炼一下并保存”“把刚才的问答整理成笔记”
- 当前问题已经解决，值得作为 L3 文档长期保留
- 你希望这次对话能被后续的 `knowledge-search` 检索到

## 快速开始

推荐始终使用 JSON mode，避免 shell 转义问题：

```bash
cat >/tmp/distill.json <<'JSON'
{
  "title": "[Dev] 端口冲突排查",
  "content": "## 背景与起因\n...\n\n## 排查过程\n1. ...\n\n## 最终方案\n...",
  "base_dir": "~/knowledge-base/40_Agent_Notes/distilled-conversations"
}
JSON

python3 ~/.ai-skills/conversation-distiller/scripts/save_note.py \
  --json /tmp/distill.json \
  --print-json
```

如果不提供 `base_dir`，默认行为是：

1. 读取 `~/.ai-memory/config.json`
2. 取其中第一个 `l3_paths` 作为知识根目录
3. 写入 `<knowledge-root>/40_Agent_Notes/distilled-conversations/`

## 建议的提炼结构

```markdown
## 背景与起因
[具体问题、错误、环境]

## 排查/探索过程
1. [步骤]
2. [步骤]

## 关键转折
[哪一步揭示了问题本质]

## 最终方案
[最终做法 + 原理]

## 延伸知识点
- [可选]
```

## 自动入库行为

当输出目录位于已配置的 L3 路径下时，脚本会自动：

1. 运行 `ensure-knowledge-frontmatter.py`
2. 运行 `rag-engine/knowledge_index.py --update`

这样新保存的笔记会尽快进入 L3 检索链路。

## 环境变量

可选环境变量：

- `CONVERSATION_DISTILLER_BASE_DIR`：覆盖默认输出目录
- `CONVERSATION_DISTILLER_KNOWLEDGE_ROOT`：覆盖自动识别的知识根目录
- `CONVERSATION_DISTILLER_DB_PATH`：覆盖 LanceDB 索引路径
- `CONVERSATION_DISTILLER_AUTO_INGEST`：设为 `false` 可关闭自动入库
- `CONVERSATION_DISTILLER_INDEXER_PYTHON`：覆盖 indexer 的 Python 解释器

## 设计约束

- 脚本本身零外部依赖（stdlib only）
- 默认只处理“当前对话”的提炼，不负责历史对话检索
- 自动入库依赖 `KitClaw` 自带的 `memory-manager` 和 `rag-engine`
- 对话正文建议通过 JSON 文件传递，不建议用 positional args
