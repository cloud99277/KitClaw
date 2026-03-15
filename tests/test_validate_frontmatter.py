import validate_frontmatter


def test_validate_frontmatter_fallback_handles_multiline_list(monkeypatch):
    monkeypatch.setattr(validate_frontmatter, "HAS_FRONTMATTER", False)
    monkeypatch.setattr(validate_frontmatter, "frontmatter", None)

    content = """---
title: Demo
tags:
  - governance
scope: dev
---
# Heading
Body
"""

    issues = validate_frontmatter.validate_frontmatter_content(content, "docs/demo.md")

    assert issues == []


def test_validate_frontmatter_fallback_reports_invalid_scope(monkeypatch):
    monkeypatch.setattr(validate_frontmatter, "HAS_FRONTMATTER", False)
    monkeypatch.setattr(validate_frontmatter, "frontmatter", None)

    content = """---
title: Demo
tags: [governance]
scope: invalid
---
# Heading
Body
"""

    issues = validate_frontmatter.validate_frontmatter_content(content, "docs/demo.md")

    assert any(issue["field"] == "scope" and issue["severity"] == "warning" for issue in issues)
