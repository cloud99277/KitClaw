---
name: knowledge-search
title: knowledge-search
description: >
  Search the local Markdown knowledge base using hybrid (vector + FTS) retrieval.
  Use when you need to find architecture decisions, past research, configuration
  guides, or any project-specific knowledge. Supports preset modes for different
  scenarios (coding, audit, qa, fast).
  当用户提到"搜索知识库""查知识""查历史决策""knowledge search""查文档"时触发。
io:
  input:
    - type: text
      description: 搜索查询文本
  output:
    - type: json_data
      description: 搜索结果（含 schema_version、query metadata、匹配条目列表）
---

# knowledge-search

本地 Markdown 知识库语义检索 Skill，基于 LanceDB 向量 + Tantivy FTS 混合搜索。

## 快速开始

### 按场景搜索（推荐）

```bash
# 编码场景：精确查架构决策（top 3, scope=dev）
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "Embedding 模型选型" --preset coding

# 审查场景：对比历史调研（top 5, scope=dev）
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "RAG 技术选型" --preset audit

# 提问场景：广泛搜索回答用户（top 10）
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "Git 同步策略" --preset qa

# 快速模式：FTS-only，跳过 Embedding 加载（<1s）
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "pre-commit" --preset fast
```

### 高级参数

```bash
# 自定义搜索模式和数量
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "查询" \
  --mode hybrid \
  --top 5 \
  --db-path ~/.lancedb/knowledge \
  --scope dev \
  --tags architecture

# 按时间过滤
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "查询" \
  --after 2026-03-01

# 按作者过滤
bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh "查询" \
  --author agent
```

## 搜索 Preset 配置

| preset | 搜索模式 | 数量 | scope | 适用场景 |
|--------|---------|------|-------|---------|
| `coding` | hybrid | 3 | dev | 编码时查架构决策、技术选型 |
| `audit` | hybrid | 5 | dev | 审查文档时对比历史调研 |
| `qa` | hybrid | 10 | （不限） | 回答用户知识提问 |
| `fast` | fts | 5 | （不限） | 快速关键词匹配，跳过模型加载 |

> `fast` preset 使用 FTS（全文检索），不加载 Embedding 模型，延迟 <1秒。
> 其他 preset 使用 hybrid（向量 + FTS + RRF 融合），首次加载模型约 3-5 秒。

## 输出格式

所有输出为 JSON 格式，遵循以下 Schema：

```json
{
  "schema_version": "1.0",
  "query": "搜索文本",
  "mode": "hybrid",
  "preset": "coding",
  "total_results": 3,
  "results": [
    {
      "chunk_id": "c12b2f551397",
      "text": "匹配的文本内容...",
      "score": 0.85,
      "source_file": "docs/RESEARCH-RAG-TECH.md",
      "heading_path": ["# RAG 技术调研", "## 向量数据库选型"],
      "line_range": "L45-L78",
      "metadata": {
        "title": "RAG 技术调研",
        "scope": "dev",
        "tags": "rag,architecture"
      }
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 输出格式版本，当前 "1.0" |
| `query` | string | 原始查询文本 |
| `mode` | string | 实际使用的搜索模式 |
| `preset` | string | 使用的 preset 名称（如有） |
| `total_results` | int | 返回结果数 |
| `results[].chunk_id` | string | 文本块唯一 ID |
| `results[].text` | string | 匹配的文本内容 |
| `results[].score` | float | 相关度评分（0-1，越高越相关） |
| `results[].source_file` | string | 来源文件路径 |
| `results[].heading_path` | list | 标题层级路径 |
| `results[].line_range` | string | 行号范围（如 "L45-L78"） |
| `results[].metadata` | object | 文件元数据（title, scope, tags, author, date） |

## 设计约束

- 零外部依赖：wrapper 脚本为纯 Bash
- Embedding 模型锁定为 `BAAI/bge-small-zh-v1.5`（中文优化，dim=512）
- 索引数据存储在 `~/.lancedb/knowledge/`，与 Skill 代码分离
- 所有输出格式含 `schema_version` 字段

## 安装

```bash
# 从项目目录安装（创建软链接）
bash skills/knowledge-search/scripts/install.sh
```

## 前置条件

- Python 3.10+
- LanceDB 索引已创建（运行 `python3 src/rag/knowledge_index.py --full <directory>`）
- Python 依赖已安装（`pip install -r src/rag/requirements.txt`）
- 首次本地模型加载需能访问 Hugging Face，或提前缓存模型

## 搜索结果使用协议

当你作为 Agent 使用此工具时，请遵循以下协议：

1. **基于结果回答**：不要依赖自身知识，以搜索结果为准
2. **引用来源**：在回答中标注 `source_file` + `line_range`
3. **无结果处理**：如果搜索无结果，明确告知用户"知识库中未找到相关信息"
4. **不篡改原文**：引用搜索结果时不要修改原文内容
5. **选择合适 preset**：
   - 编码场景 → `--preset coding`
   - 审查场景 → `--preset audit`
   - 提问场景 → `--preset qa`
   - 快速匹配 → `--preset fast`
