import sys
from types import SimpleNamespace

import pytest

from knowledge_index import EmbeddingEngine, _chunks_to_records, _to_str
from md_chunker import MarkdownChunk


def test_to_str_handles_none_and_sequences():
    assert _to_str(None) == ""
    assert _to_str(["a", "b"]) == "a,b"
    assert _to_str(("x", 2)) == "x,2"
    assert _to_str("plain") == "plain"


def test_chunks_to_records_serializes_frontmatter_fields():
    chunk = MarkdownChunk(
        text="hello world",
        heading_path=["# Title"],
        level=1,
        source_file="docs/test.md",
        start_line=1,
        end_line=3,
        metadata={"tags": ["rag", "audit"], "scope": "dev", "title": "Doc"},
        chunk_id="abc123",
    )

    records = _chunks_to_records([chunk], [[0.1, 0.2]], {"docs/test.md": "hash1"})

    assert len(records) == 1
    assert records[0]["tags"] == "rag,audit"
    assert records[0]["scope"] == "dev"
    assert records[0]["title"] == "Doc"
    assert records[0]["file_hash"] == "hash1"
    assert records[0]["schema_version"] == "1.0"


def test_embedding_engine_falls_back_in_dev_when_model_load_fails(monkeypatch):
    class BrokenSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("model download failed")

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=BrokenSentenceTransformer),
    )
    monkeypatch.delenv("PRODUCTION", raising=False)

    engine = EmbeddingEngine(mode="local", model_name="broken/model")

    assert engine.dimension == 384
    assert engine._local_type == "hash_fallback"


def test_embedding_engine_raises_in_production_when_model_load_fails(monkeypatch):
    class BrokenSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("model download failed")

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=BrokenSentenceTransformer),
    )
    monkeypatch.setenv("PRODUCTION", "true")

    with pytest.raises(RuntimeError, match="Failed to load local embedding model 'broken/model'"):
        EmbeddingEngine(mode="local", model_name="broken/model")
