---
name: l3-sync
description: |
  Watch Markdown knowledge base directories and auto-trigger incremental RAG indexing on file changes.
  Use when the user wants to set up automatic L3 index syncing, enable background indexing, or
  configure filesystem watchers for their knowledge base.
  触发词：自动索引、知识库同步、l3 sync、watcher、自动入库。
  NOT for manual indexing (use knowledge_index.py directly).
  NOT for git sync or version control.
---

# l3-sync — L3 知识库自动索引

监控 Markdown 知识库目录的文件变更，自动触发增量 RAG 索引更新。

## 适用场景

- Obsidian 编辑后自动更新搜索索引
- 知识库目录有变更时自动增量索引
- 后台守护进程持续监听

## 工作原理

```
文件系统变更（inotify / 轮询）
  → 防抖（5s 窗口批量合并变更）
  → knowledge_index.py --update <目录>
  → 观测日志写入 skill-observability
```

## 使用方法

### 单次增量索引（手动触发）

```bash
# 读取配置，对所有 l3_paths 做一次增量索引
python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --once
```

### 启动后台监听（推荐）

```bash
# 前台运行（调试用）
python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --watch

# 后台运行
nohup python3 ~/.ai-skills/l3-sync/scripts/index_watcher.py --watch &
```

### 用 systemd 管理（生产环境）

```bash
# 安装 systemd user service
bash ~/.ai-skills/l3-sync/scripts/install_service.sh

# 管理
systemctl --user start l3-sync
systemctl --user status l3-sync
systemctl --user stop l3-sync
```

## 配置

监听路径从 `~/.ai-memory/config.json` 的 `l3_paths` 字段读取：

```json
{
  "l3_paths": [
    "/mnt/e/Cloud927/.../20_Knowledge_Base"
  ]
}
```

## 与其他 Skill 的关系

- **knowledge-search** — 搜索已索引的 L3。l3-sync 确保索引是最新的。
- **knowledge_index.py** — 索引引擎。l3-sync 是它的触发器。
- **conversation-distiller** — 对话 → L3 文档。写入后 l3-sync 自动增量索引。

## 依赖

- RAG 引擎已安装（`bash install.sh --with-rag`）
- Linux inotify 支持（WSL 有；纯轮询模式也支持，但延迟更高）
