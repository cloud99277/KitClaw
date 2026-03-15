# Sample Knowledge Vault

This directory contains example Markdown files to demonstrate KitClaw's knowledge base structure.

## How to Use

1. Point your `~/.ai-memory/config.json` to this directory:

```json
{
  "schema_version": "1.0",
  "l3_paths": ["/path/to/kitclaw/examples/sample-vault"]
}
```

2. Build the index (requires RAG engine):

```bash
python3 rag-engine/knowledge_index.py --update examples/sample-vault --db-path ~/.lancedb/sample
```

3. Search:

```bash
python3 rag-engine/knowledge_search.py "chunking" --mode hybrid --top 3 --db-path ~/.lancedb/sample
```

## Frontmatter Standard

Every Markdown file in a KitClaw knowledge base should have YAML frontmatter:

```yaml
---
title: "Document Title"
tags: [tag1, tag2]
scope: dev|content|personal
type: note|research|report|playbook|decision|template
status: active|archived
date: "YYYY-MM-DD"
---
```

Files without frontmatter will get auto-completed by `ensure-knowledge-frontmatter.py`.
