#!/usr/bin/env python3
# ruff: noqa: E402
"""
Knowledge Search Engine
基于 LanceDB 的本地 Markdown 知识库语义搜索。

用法:
  python3 knowledge_search.py "查询文本" [--mode hybrid] [--top 10]
  python3 knowledge_search.py "部署方案" --scope dev --tags architecture
  python3 knowledge_search.py "编排链" --json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict

__version__ = "1.0.0"
TABLE_NAME = "knowledge_chunks"
DEFAULT_DB_PATH = os.path.expanduser("~/.lancedb/knowledge")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_index import EmbeddingEngine, _import_lancedb


# ---------- 数据结构 ----------

@dataclass
class SearchResult:
    """单条搜索结果"""
    chunk_id: str
    text: str
    score: float
    source_file: str
    heading_path: list
    line_range: str
    metadata: dict
    fallback: str = ""  # 降级标注

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d['fallback']:
            del d['fallback']
        return d


# ---------- 搜索逻辑 ----------

# > v1→v2 变更：收紧白名单正则，防止 SQL 注入，来源：审查报告 #2（CWE-89）
_SAFE_VALUE_RE = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$')
_SAFE_TAG_RE = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff,. ]+$')


def _sanitize(value: str, allow_separators: bool = False) -> str:
    """校验过滤值，防止 SQL 注入。使用严格白名单验证。"""
    pattern = _SAFE_TAG_RE if allow_separators else _SAFE_VALUE_RE
    if not pattern.match(value):
        raise ValueError(f"Unsafe filter value: {value}")
    return value


def _build_filter(args) -> str | None:
    """将 CLI 参数转为 LanceDB where 子句"""
    conditions = []
    if hasattr(args, 'scope') and args.scope:
        conditions.append(f"scope = '{_sanitize(args.scope)}'")
    if hasattr(args, 'tags') and args.tags:
        # > v1→v2 变更：每个 tag 单独验证，来源：审查报告 #2
        for tag in args.tags.split(","):
            tag = tag.strip()
            if tag:
                conditions.append(f"tags LIKE '%{_sanitize(tag, allow_separators=False)}%'")
    if hasattr(args, 'author') and args.author:
        conditions.append(f"author = '{_sanitize(args.author)}'")
    if hasattr(args, 'after') and args.after:
        conditions.append(f"date >= '{_sanitize(args.after)}'")
    return " AND ".join(conditions) if conditions else None


def search_vector(table, query_vector: list[float], top_k: int, where: str | None = None) -> list[SearchResult]:
    """纯向量语义搜索"""
    q = table.search(query_vector).limit(top_k)
    if where:
        q = q.where(where)
    results = q.to_pandas()
    return _df_to_results(results)


def search_fts(table, query: str, top_k: int, where: str | None = None) -> list[SearchResult]:
    """全文搜索（Tantivy FTS）"""
    try:
        q = table.search(query, query_type="fts").limit(top_k)
        if where:
            q = q.where(where)
        results = q.to_pandas()
        return _df_to_results(results)
    except Exception as e:
        # FTS 可能未创建索引或不支持
        print(f"  FTS unavailable: {e}", file=sys.stderr)
        return []


def search_hybrid(table, query: str, query_vector: list[float], top_k: int, where: str | None = None) -> list[SearchResult]:
    """混合搜索：向量 + FTS + 降级逻辑"""
    # 先尝试向量搜索
    vector_results = search_vector(table, query_vector, top_k * 2, where)

    # 尝试 FTS
    fts_results = search_fts(table, query, top_k * 2, where)

    # 降级检测：如果 FTS 返回 0 结果，降级为纯向量
    if not fts_results:
        for r in vector_results[:top_k]:
            r.fallback = "fts_unavailable"
        return vector_results[:top_k]

    # RRF (Reciprocal Rank Fusion) 融合
    rrf_scores = {}
    k = 60  # RRF constant

    for rank, r in enumerate(vector_results):
        rrf_scores[r.chunk_id] = rrf_scores.get(r.chunk_id, 0) + 1.0 / (k + rank + 1)
        if r.chunk_id not in rrf_scores:
            rrf_scores[r.chunk_id] = 0

    for rank, r in enumerate(fts_results):
        rrf_scores[r.chunk_id] = rrf_scores.get(r.chunk_id, 0) + 1.0 / (k + rank + 1)

    # 合并结果
    all_results = {}
    for r in vector_results + fts_results:
        if r.chunk_id not in all_results:
            all_results[r.chunk_id] = r

    # 按 RRF 分数排序
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    merged = []
    for cid in sorted_ids[:top_k]:
        if cid in all_results:
            r = all_results[cid]
            r.score = round(rrf_scores[cid], 6)
            merged.append(r)

    return merged


def _df_to_results(df) -> list[SearchResult]:
    """将 pandas DataFrame 转为 SearchResult 列表"""
    results = []
    for _, row in df.iterrows():
        heading_path = []
        hp = row.get('heading_path', '[]')
        if hp:
            try:
                heading_path = json.loads(hp) if isinstance(hp, str) else hp
            except (json.JSONDecodeError, TypeError):
                heading_path = []

        score = 0.0
        if '_distance' in row:
            # LanceDB 向量搜索返回 _distance (越小越相似)
            score = round(max(0, 1.0 - float(row['_distance'])), 4)
        elif '_score' in row:
            score = round(float(row['_score']), 4)

        meta = {}
        for field in ['tags', 'scope', 'author', 'date', 'title']:
            val = row.get(field, '')
            if val:
                meta[field] = val

        results.append(SearchResult(
            chunk_id=row.get('chunk_id', ''),
            text=str(row.get('text', '')),
            score=score,
            source_file=row.get('source_file', ''),
            heading_path=heading_path,
            line_range=f"L{row.get('start_line', 0)}-L{row.get('end_line', 0)}",
            metadata=meta,
        ))
    return results


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description='Knowledge Search Engine (LanceDB)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('query', nargs='?', help='Search query text')
    parser.add_argument('--version', action='version', version=f'knowledge_search {__version__}')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='LanceDB path')
    parser.add_argument('--mode', choices=['vector', 'fts', 'hybrid'], default='hybrid', help='Search mode')
    parser.add_argument('--top', type=int, default=10, help='Number of results')
    parser.add_argument('--json', action='store_true', dest='json_output', help='JSON output')
    # > v1→v2 变更：添加 debug 模式，来源：审查报告 #6
    parser.add_argument('--debug', action='store_true', help='Show full traceback on errors')

    # 元数据过滤
    parser.add_argument('--scope', help='Filter by scope (dev/content/personal)')
    parser.add_argument('--tags', help='Filter by tags (comma-separated)')
    parser.add_argument('--author', help='Filter by author')
    parser.add_argument('--after', help='Filter by date (YYYY-MM-DD)')

    # Embedding
    parser.add_argument('--embedding-mode', choices=['local', 'api'], default='local')
    parser.add_argument('--model', default='BAAI/bge-small-zh-v1.5')

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    # > v1→v2 变更：结构化错误处理 + debug 模式，来源：审查报告 #6
    try:
        # 连接 LanceDB
        lancedb = _import_lancedb()
        db = lancedb.connect(args.db_path)
        try:
            table = db.open_table(TABLE_NAME)
        except Exception:
            print(f"Error: No index found at {args.db_path}/{TABLE_NAME}", file=sys.stderr)
            print("Run: python3 knowledge_index.py --full <directory> to create index", file=sys.stderr)
            sys.exit(1)

        where = _build_filter(args)

        # 执行搜索
        if args.mode == 'fts':
            results = search_fts(table, args.query, args.top, where)
        elif args.mode == 'vector':
            engine = EmbeddingEngine(mode=args.embedding_mode, model_name=args.model)
            query_vector = engine.embed_query(args.query)
            results = search_vector(table, query_vector, args.top, where)
        else:  # hybrid
            engine = EmbeddingEngine(mode=args.embedding_mode, model_name=args.model)
            query_vector = engine.embed_query(args.query)
            results = search_hybrid(table, args.query, query_vector, args.top, where)

        # 输出
        if not results:
            if args.json_output:
                print("[]")
            else:
                print("No results found.", file=sys.stderr)
            sys.exit(0)

        if args.json_output:
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
        else:
            for i, r in enumerate(results, 1):
                path_display = ' > '.join(r.heading_path) if r.heading_path else '(root)'
                print(f"\n{'='*60}")
                print(f"  #{i}  Score: {r.score}  [{r.chunk_id}]")
                print(f"  File: {r.source_file} {r.line_range}")
                print(f"  Path: {path_display}")
                if r.metadata:
                    meta_str = ', '.join(f"{k}={v}" for k, v in r.metadata.items() if v)
                    if meta_str:
                        print(f"  Meta: {meta_str}")
                if r.fallback:
                    print(f"  Note: {r.fallback}")
                print("  ---")
                preview = r.text[:300].strip()
                print(f"  {preview}")
                if len(r.text) > 300:
                    print(f"  ... ({len(r.text)} chars total)")

            print(f"\n{len(results)} results found.", file=sys.stderr)

    except FileNotFoundError as e:
        print(f"Error: Database not found - {e}", file=sys.stderr)
        print("Run: python3 knowledge_index.py --full <directory> to create index", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid input - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
