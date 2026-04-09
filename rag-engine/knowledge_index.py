#!/usr/bin/env python3
# ruff: noqa: E402
"""
Knowledge Index Engine
基于 LanceDB 的本地 Markdown 知识库索引引擎。

用法:
  python3 knowledge_index.py --full <directory> [--db-path ~/.lancedb/knowledge]
  python3 knowledge_index.py --update <directory> [--db-path ~/.lancedb/knowledge]
  python3 knowledge_index.py --status [--db-path ~/.lancedb/knowledge]
  python3 knowledge_index.py --clear [--db-path ~/.lancedb/knowledge]
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

__version__ = "1.0.0"
SCHEMA_VERSION = "1.0"
TABLE_NAME = "knowledge_chunks"
DEFAULT_DB_PATH = os.path.expanduser("~/.lancedb/knowledge")

# 导入同目录的 chunker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_chunker import scan_directory, parse_file, MarkdownChunk

# ---------- 延迟导入 ----------

def _import_lancedb():
    try:
        import lancedb
        return lancedb
    except ImportError:
        print("Error: lancedb not installed. Run: pip install lancedb", file=sys.stderr)
        sys.exit(1)


# ---------- Embedding Engine ----------

# BGE 系列模型推荐的 query 前缀（提升检索质量）
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


def _production_mode() -> bool:
    """在生产模式下禁止退回测试用伪向量。"""
    return os.environ.get("PRODUCTION", "").lower() == "true"


class EmbeddingEngine:
    """双轨 Embedding：local 或 api，显式选择"""

    def __init__(self, mode: str = "local", model_name: str = "BAAI/bge-small-zh-v1.5", api_key: str | None = None):
        self.mode = mode
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        self._dimension = None
        # 检测是否为 BGE 模型，自动添加 query 前缀
        self._is_bge = 'bge' in model_name.lower()

        if mode == "local":
            self._init_local(model_name)
        elif mode == "api":
            self._init_api(api_key)
        else:
            raise ValueError(f"Unknown embedding mode: {mode}. Use 'local' or 'api'.")

    def _init_local(self, model_name: str):
        """尝试 sentence-transformers，fallback 到简单 TF-IDF 向量"""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            self._init_hash_fallback(e)
            return

        try:
            self._model = SentenceTransformer(model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            self._local_type = "sentence_transformers"
            print(f"  Embedding: {model_name} (sentence-transformers, dim={self._dimension})", file=sys.stderr)
            return
        except Exception as e:
            self._init_hash_fallback(e)

    def _init_hash_fallback(self, reason: Exception | None = None):
        """开发环境允许退回伪向量，生产环境必须给出明确失败原因。"""
        if _production_mode():
            detail = f" Original error: {reason}" if reason else ""
            raise RuntimeError(
                f"Failed to load local embedding model '{self.model_name}'. "
                "Production mode forbids hash fallback. Ensure sentence-transformers is "
                "installed, proxy/runtime dependencies are available, and the model can be downloaded." + detail
            ) from reason

        # Fallback: 用简单的 hash-based 假向量（仅用于开发测试）
        # > v1→v2 变更：生产环境禁止 fallback，来源：审查报告 #5
        if reason is not None:
            print(f"  Warning: failed to load local embedding model '{self.model_name}': {reason}", file=sys.stderr)
        print("  ⚠️  WARNING: Using hash-based pseudo-vectors (TESTING ONLY)", file=sys.stderr)
        print("  ⚠️  DO NOT USE IN PRODUCTION - set PRODUCTION=true to enforce", file=sys.stderr)
        print("  Install runtime deps and pre-download the embedding model for production use", file=sys.stderr)
        self._dimension = 384
        self._local_type = "hash_fallback"

    def _init_api(self, api_key: str | None = None):
        """OpenAI text-embedding-3-small API"""
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not set. Set environment variable or use --embedding-mode local")
        try:
            import openai  # pyright: ignore[reportMissingImports]
            self._client = openai.OpenAI(api_key=self._api_key)
            self._dimension = 1536
            print(f"  Embedding: OpenAI text-embedding-3-small (dim={self._dimension})", file=sys.stderr)
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

    @property
    def dimension(self) -> int:
        assert self._dimension is not None
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 Embedding 向量（用于文档内容）"""
        if not texts:
            return []

        if self.mode == "local":
            return self._embed_local(texts)
        else:
            return self._embed_api(texts)

    def embed_query(self, query: str) -> list[float]:
        """生成查询向量（BGE 模型自动添加前缀提升检索质量）"""
        if self._is_bge:
            query = BGE_QUERY_PREFIX + query
        return self.embed([query])[0]

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        if self._local_type == "sentence_transformers":
            assert self._model is not None
            vectors = self._model.encode(texts, show_progress_bar=len(texts) > 50)
            return [v.tolist() for v in vectors]
        else:
            # hash fallback (测试用)
            assert self._dimension is not None
            result = []
            for text in texts:
                h = hashlib.sha256(text.encode()).hexdigest()
                vec = [int(h[i:i+2], 16) / 255.0 for i in range(0, min(len(h), self._dimension * 2), 2)]
                vec.extend([0.0] * (self._dimension - len(vec)))
                result.append(vec[:self._dimension])
            return result

    def _embed_api(self, texts: list[str]) -> list[list[float]]:
        # 批量调用，每次最多 2048 条
        all_vectors = []
        batch_size = 2048
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            resp = self._client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            for item in resp.data:
                all_vectors.append(item.embedding)
        return all_vectors


# ---------- 索引操作 ----------


class EmbeddingBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

def _file_hash(filepath: str) -> str:
    """计算文件内容的 MD5"""
    return hashlib.md5(Path(filepath).read_bytes()).hexdigest()


# > v1→v2 变更：tags 字段强制转字符串，修复 PyArrow Schema 崩溃，来源：审查报告 #3
def _to_str(val):
    """将任意值转为字符串，防止 list/str 混合导致 PyArrow Schema 崩溃"""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return ",".join(map(str, val))
    return str(val)


def _chunks_to_records(chunks: list[MarkdownChunk], vectors: list[list[float]], file_hashes: dict) -> list[dict]:
    """将 chunks + vectors 转为 LanceDB 记录"""
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for chunk, vector in zip(chunks, vectors):
        meta = chunk.metadata
        records.append({
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "vector": vector,
            "source_file": chunk.source_file,
            "heading_path": json.dumps(chunk.heading_path, ensure_ascii=False),
            "level": chunk.level,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "tags": _to_str(meta.get("tags", "")),
            "scope": str(meta.get("scope", "")),
            "author": str(meta.get("author", "")),
            "date": str(meta.get("date", "")),
            "title": str(meta.get("title", "") or (chunk.heading_path[0] if chunk.heading_path else "")),
            "indexed_at": now,
            "file_hash": file_hashes.get(chunk.source_file, ""),
            "schema_version": SCHEMA_VERSION,
        })
    return records


def do_full_index(directory: str, db_path: str, engine: EmbeddingBackend):
    """全量索引"""
    lancedb = _import_lancedb()

    print(f"Scanning {directory}...", file=sys.stderr)
    chunks = scan_directory(directory)
    if not chunks:
        print("No Markdown files found.", file=sys.stderr)
        return

    print(f"Found {len(chunks)} chunks from Markdown files.", file=sys.stderr)

    # 计算文件 hash
    file_hashes = {}
    for c in chunks:
        fp = os.path.join(directory, c.source_file)
        if c.source_file not in file_hashes and os.path.exists(fp):
            file_hashes[c.source_file] = _file_hash(fp)

    # 生成 Embedding
    print("Generating embeddings...", file=sys.stderr)
    texts = [c.text for c in chunks]
    t0 = time.time()
    vectors = engine.embed(texts)
    elapsed = time.time() - t0
    print(f"  {len(vectors)} embeddings in {elapsed:.1f}s", file=sys.stderr)

    # 写入 LanceDB
    records = _chunks_to_records(chunks, vectors, file_hashes)
    db = lancedb.connect(db_path)

    # 删除旧表（如存在）
    try:
        db.drop_table(TABLE_NAME)
    except Exception:
        pass

    table = db.create_table(TABLE_NAME, data=records)
    print(f"Index created: {len(records)} chunks in {db_path}/{TABLE_NAME}", file=sys.stderr)
    print(f"Files indexed: {len(file_hashes)}", file=sys.stderr)

    # 创建 FTS 索引（Tantivy 全文搜索）
    try:
        table.create_fts_index("text", replace=True)
        print("FTS index created on 'text' column", file=sys.stderr)
    except Exception as e:
        print(f"  Warning: FTS index creation failed: {e}", file=sys.stderr)
        print("  Hybrid search will fallback to pure vector mode", file=sys.stderr)


def do_update_index(directory: str, db_path: str, engine: EmbeddingBackend):
    """增量索引：只处理新增/修改/删除的文件"""
    lancedb = _import_lancedb()

    db = lancedb.connect(db_path)
    try:
        table = db.open_table(TABLE_NAME)
    except Exception:
        print("No existing index found. Running full index instead.", file=sys.stderr)
        do_full_index(directory, db_path, engine)
        return

    # 获取已索引文件的 hash
    existing = table.to_pandas()
    indexed_hashes = {}
    for _, row in existing[['source_file', 'file_hash']].drop_duplicates().iterrows():
        indexed_hashes[row['source_file']] = row['file_hash']

    # 扫描当前目录
    root = Path(directory)
    current_files = {}
    for path in sorted(root.rglob('*.md')):
        if path.is_file():
            parts = path.relative_to(root).parts
            if any(p.startswith('.') for p in parts):
                continue
            rel = str(path.relative_to(root))
            current_files[rel] = _file_hash(str(path))

    # 识别变更
    new_files = [f for f in current_files if f not in indexed_hashes]
    modified_files = [f for f in current_files if f in indexed_hashes and current_files[f] != indexed_hashes[f]]
    deleted_files = [f for f in indexed_hashes if f not in current_files]
    unchanged = len(current_files) - len(new_files) - len(modified_files)

    print(f"Incremental update: {len(new_files)} new, {len(modified_files)} modified, {len(deleted_files)} deleted, {unchanged} unchanged", file=sys.stderr)

    if not new_files and not modified_files and not deleted_files:
        print("Nothing to update.", file=sys.stderr)
        return

    # 删除已修改和已删除文件的旧记录
    files_to_remove = modified_files + deleted_files
    if files_to_remove:
        for f in files_to_remove:
            table.delete(f"source_file = '{f}'")
        print(f"  Removed old records for {len(files_to_remove)} files", file=sys.stderr)

    # 索引新增和修改的文件
    files_to_index = new_files + modified_files
    if files_to_index:
        all_chunks = []
        file_hashes = {}
        for f in files_to_index:
            fp = os.path.join(directory, f)
            chunks = parse_file(fp)
            for c in chunks:
                c.source_file = f
            all_chunks.extend(chunks)
            file_hashes[f] = current_files[f]

        if all_chunks:
            print(f"  Generating embeddings for {len(all_chunks)} chunks...", file=sys.stderr)
            vectors = engine.embed([c.text for c in all_chunks])
            records = _chunks_to_records(all_chunks, vectors, file_hashes)
            table.add(records)
            print(f"  Added {len(records)} new chunks", file=sys.stderr)

    print("Update complete.", file=sys.stderr)


def do_status(db_path: str):
    """显示索引状态"""
    lancedb = _import_lancedb()

    db = lancedb.connect(db_path)
    try:
        table = db.open_table(TABLE_NAME)
    except Exception:
        print(f"No index found at {db_path}/{TABLE_NAME}")
        print("Run: knowledge_index.py --full <directory> to create index")
        return

    df = table.to_pandas()
    n_chunks = len(df)
    n_files = df['source_file'].nunique()
    latest = df['indexed_at'].max() if n_chunks > 0 else "N/A"
    schema_v = df['schema_version'].iloc[0] if n_chunks > 0 else "N/A"

    print(f"Index status: {db_path}/{TABLE_NAME}")
    print(f"  Chunks:         {n_chunks}")
    print(f"  Files:          {n_files}")
    print(f"  Last indexed:   {latest}")
    print(f"  Schema version: {schema_v}")

    if n_files > 0:
        print("\n  Files:")
        for f in sorted(df['source_file'].unique()):
            count = len(df[df['source_file'] == f])
            print(f"    {f} ({count} chunks)")


def do_clear(db_path: str):
    """清空索引"""
    lancedb = _import_lancedb()
    db = lancedb.connect(db_path)
    try:
        db.drop_table(TABLE_NAME)
        print(f"Index cleared: {db_path}/{TABLE_NAME}", file=sys.stderr)
    except Exception:
        print(f"No index found at {db_path}/{TABLE_NAME}", file=sys.stderr)


# ---------- CLI ----------

CONFIG_PATH = os.path.expanduser("~/.ai-memory/config.json")


def _load_config() -> dict:
    """Load config.json if it exists."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    config = _load_config()
    embedding_cfg = config.get("embedding", {})

    parser = argparse.ArgumentParser(
        description='Knowledge Index Engine (LanceDB)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'knowledge_index {__version__}')
    parser.add_argument('--db-path', default=config.get("index", {}).get("db_path", DEFAULT_DB_PATH),
                        help=f'LanceDB path (default from config or {DEFAULT_DB_PATH})')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--full', metavar='DIR', help='Full index of directory')
    group.add_argument('--update', metavar='DIR', help='Incremental update')
    group.add_argument('--status', action='store_true', help='Show index status')
    group.add_argument('--clear', action='store_true', help='Clear index')

    parser.add_argument('--embedding-mode', choices=['local', 'api'],
                        default=embedding_cfg.get("mode", "local"),
                        help='Embedding mode (default from config.json)')
    parser.add_argument('--model',
                        default=embedding_cfg.get("local_model", "BAAI/bge-small-zh-v1.5"),
                        help='Local embedding model name')

    args = parser.parse_args()

    if args.status:
        do_status(args.db_path)
        return

    if args.clear:
        do_clear(args.db_path)
        return

    # 初始化 Embedding 引擎
    engine = EmbeddingEngine(mode=args.embedding_mode, model_name=args.model)

    if args.full:
        do_full_index(args.full, args.db_path, engine)
    elif args.update:
        do_update_index(args.update, args.db_path, engine)


if __name__ == '__main__':
    main()
