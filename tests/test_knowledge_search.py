from argparse import Namespace

import pandas as pd
import pytest

from knowledge_search import _build_filter, _df_to_results, _sanitize


def test_sanitize_accepts_safe_values():
    assert _sanitize("dev") == "dev"
    assert _sanitize("中文标签") == "中文标签"


def test_sanitize_rejects_unsafe_values():
    with pytest.raises(ValueError, match="Unsafe filter value"):
        _sanitize("dev' OR 1=1 --")


def test_build_filter_combines_all_conditions():
    args = Namespace(scope="dev", tags="rag,architecture", author="agent", after="2026-03-01")

    where = _build_filter(args)

    assert where == (
        "scope = 'dev' AND tags LIKE '%rag%' AND tags LIKE '%architecture%' "
        "AND author = 'agent' AND date >= '2026-03-01'"
    )


def test_df_to_results_parses_heading_path_and_metadata():
    df = pd.DataFrame([
        {
            "chunk_id": "cid",
            "text": "hello",
            "_score": 0.9,
            "source_file": "docs/demo.md",
            "heading_path": '["# Title", "## Section"]',
            "start_line": 1,
            "end_line": 5,
            "tags": "rag,architecture",
            "scope": "dev",
            "title": "Demo",
        }
    ])

    results = _df_to_results(df)

    assert len(results) == 1
    assert results[0].heading_path == ["# Title", "## Section"]
    assert results[0].metadata["scope"] == "dev"
    assert results[0].line_range == "L1-L5"
