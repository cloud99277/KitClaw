---
name: l3-quickstart
title: L3 Knowledge Base Quick Start
---

# L3 Knowledge Base — 30 分钟快速上手

本指南帮你从零跑通 L3 知识库：安装、配置、索引、搜索、自动同步。

## 前提

- KitClaw 已安装（`bash install.sh`）
- Python 3.10+ 已安装
- 有一个 Markdown 知识库目录（Obsidian vault 或普通 Markdown 文件夹）

## 1. 安装 RAG 引擎

```bash
cd KitClaw
bash install.sh --with-rag
```

这会安装 RAG 引擎依赖：
- `lancedb` — 嵌入式向量数据库
- `sentence-transformers` — 本地 Embedding 模型
- `python-frontmatter` — YAML frontmatter 解析
- `pandas` — 数据处理

首次运行需要下载 Embedding 模型（`BAAI/bge-small-zh-v1.5`，约 90MB），需要能访问 Hugging Face。

## 2. 配置知识库路径

```bash
# 复制配置模板
cp rag-engine/config.example.json ~/.ai-memory/config.json

# 编辑配置
```

关键配置项：

```json
{
  "l3_paths": [
    "/path/to/your/knowledge-base"
  ],
  "embedding": {
    "mode": "local",
    "local_model": "BAAI/bge-small-zh-v1.5"
  },
  "index": {
    "db_path": "~/.lancedb/knowledge"
  }
}
```

- `l3_paths`：你的 Markdown 知识库目录路径（支持多个目录）
- `embedding.mode`：`local`（本地模型，默认）或 `api`（需要 OpenAI API key）
- `index.db_path`：向量索引存储位置

## 3. 首次索引

```bash
# 全量索引（首次必须用 --full）
python3 rag-engine/knowledge_index.py --full ~/your-knowledge-base
```

输出示例：
```
📚 Full index: /home/user/knowledge-base
   Found 342 Markdown files
   Chunking... 342 files → 1280 chunks
   Embedding... (local: BAAI/bge-small-zh-v1.5)
   Building index...
   ✅ Done. 1280 chunks indexed.
```

后续更新用增量模式（只处理变更文件）：
```bash
python3 rag-engine/knowledge_index.py --update ~/your-knowledge-base
```

## 4. 测试搜索

```bash
# 默认混合搜索（向量 + 全文）
python3 rag-engine/knowledge_search.py "你的查询内容"

# JSON 输出（供 Agent 消费）
python3 rag-engine/knowledge_search.py "查询" --json --top 5

# 纯语义搜索
python3 rag-engine/knowledge_search.py "查询" --mode vector

# 纯全文搜索
python3 rag-engine/knowledge_search.py "查询" --mode fts
```

## 5. Agent 中使用

安装后，你的 Agent 会自动加载 `knowledge-search` skill。在对话中直接提问：

```
你: 我之前研究过 WSL 路径问题，帮我找找相关笔记
Agent: [自动调用 knowledge-search → 搜索 L3 → 返回结果]
```

不需要手动调用命令，Agent 根据 `description` 自动路由。

## 6. 设置自动索引（可选）

知识库文件变更后，搜索索引不会自动更新。可以用 `l3-sync` 实现自动索引：

```bash
# 单次增量索引
python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --once

# 持续监听（前台）
python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --watch

# 后台运行
nohup python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --watch &
```

或者用 cron 定期索引：
```bash
# 每小时增量索引一次
0 * * * * python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --once >> ~/.ai-memory/l3-sync.log 2>&1
```

## 7. 三层记忆协同

```
L1 (AGENTS.md)     ← 启动时加载，用户画像和规则
L2 (whiteboard.json) ← 会话决策，l2-capture 写入
L3 (知识库 + RAG)    ← 稳定知识，knowledge-search 检索

典型流程：
1. 对话中得出一个决策 → l2-capture 写入 L2
2. 对话解决了一个问题 → conversation-distiller 沉淀到 L3
3. Obsidian 里编辑了笔记 → l3-sync 自动更新索引
4. 下次会话搜索 → knowledge-search 从 L3 检索
```

## 常见问题

### Q: 首次运行很慢？
A: 首次需要下载 Embedding 模型（~90MB）。后续运行直接用缓存，秒启动。

### Q: 我没有 Hugging Face 访问权限？
A: 提前下载模型到本地，或改用 API 模式（`embedding.mode: "api"`，需要 OpenAI key）。

### Q: 索引文件在哪？
A: 默认在 `~/.lancedb/knowledge/`。删除这个目录 = 清空索引，不影响源文件。

### Q: 能搜索中文吗？
A: 可以。默认模型 `BAAI/bge-small-zh-v1.5` 是中英双语模型。

### Q: 和 Obsidian 的搜索有什么区别？
A: Obsidian 搜索是关键词匹配。L3 是语义搜索——搜 "部署方案" 能找到写 "上线流程" 的笔记。

## 下一步

- [Memory Architecture](memory-architecture.md) — 三层记忆的完整设计
- [Skill Runtime Architecture](skill-runtime-architecture.md) — Skill 运行时架构
- [Governance](governance.md) — 仓库治理规则
