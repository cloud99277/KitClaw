from md_chunker import chunk_markdown, parse_frontmatter, scan_directory


def test_parse_frontmatter_extracts_metadata_and_body():
    content = """---
title: Demo
tags:
  - architecture
scope: dev
---
# Heading
Body
"""

    metadata, body = parse_frontmatter(content)

    assert metadata["title"] == "Demo"
    assert metadata["tags"] == ["architecture"]
    assert metadata["scope"] == "dev"
    assert body.startswith("# Heading")


def test_chunk_markdown_ignores_headings_inside_code_blocks():
    content = """# Intro
first block

```python
# not a heading
print("hello")
```

## Real Heading
second block
"""

    chunks = chunk_markdown(content, source_file="demo.md", min_size=1, max_size=500)

    assert len(chunks) == 2
    assert "# not a heading" in chunks[0].text
    assert chunks[1].heading_path == ["# Intro", "## Real Heading"]


def test_scan_directory_ignores_hidden_directories(tmp_path):
    (tmp_path / "visible.md").write_text("# Visible\nbody\n", encoding="utf-8")
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.md").write_text("# Hidden\nbody\n", encoding="utf-8")

    chunks = scan_directory(str(tmp_path), min_size=1, max_size=500)

    assert chunks
    assert all(chunk.source_file == "visible.md" for chunk in chunks)
