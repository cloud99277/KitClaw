#!/usr/bin/env python3
"""
Markdown Frontmatter Validator
校验 Markdown 文件的 YAML frontmatter 格式和必填字段。

用法:
  python3 validate_frontmatter.py <file1.md> [file2.md ...]
  python3 validate_frontmatter.py --strict <file1.md>  # Warning 也算失败

Exit codes:
  0 = 全部通过（可能有 Warning）
  1 = 有 Error（阻塞 commit）
"""

import argparse
import sys
from pathlib import Path

try:
    import frontmatter
    HAS_FRONTMATTER = True
except ImportError:
    frontmatter = None
    HAS_FRONTMATTER = False

__version__ = "1.0.0"

# 校验规则定义
REQUIRED_FIELDS = {
    "title": {"severity": "error", "description": "文档标题"},
}
RECOMMENDED_FIELDS = {
    "tags": {"severity": "warning", "description": "标签列表"},
    "scope": {"severity": "warning", "description": "领域（dev/content/personal/archive）"},
}
VALID_SCOPES = {"archive", "content", "dev", "personal"}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        return value[1:-1]
    return value


def _parse_frontmatter_fallback(content: str) -> dict:
    """Parse a small YAML subset without external dependencies."""
    import re

    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', content, re.DOTALL)
    if not m:
        raise ValueError("YAML frontmatter 格式错误（缺少闭合 ---）")

    metadata: dict[str, object] = {}
    current_key: str | None = None

    for raw_line in m.group(1).splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if current_key is None:
                raise ValueError("YAML 列表项缺少父字段")
            metadata.setdefault(current_key, [])
            current_val = metadata[current_key]
            if not isinstance(current_val, list):
                raise ValueError(f"字段 '{current_key}' 同时被解析为标量和列表")
            current_val.append(_strip_quotes(stripped[2:]))
            continue

        if ":" not in line:
            raise ValueError(f"无法解析的 frontmatter 行: {line}")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()

        if not key:
            raise ValueError(f"空字段名: {line}")

        current_key = key
        if not value:
            metadata[key] = []
            continue

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            metadata[key] = [] if not inner else [_strip_quotes(part) for part in inner.split(",")]
            continue

        metadata[key] = _strip_quotes(value)

    return metadata


def validate_frontmatter_content(content: str, filepath: str) -> list[dict]:
    """
    校验单个文件的 frontmatter。
    返回问题列表 [{"file": str, "field": str, "severity": str, "message": str}]
    """
    issues = []

    # 检查 frontmatter 是否存在
    if not content.strip().startswith('---'):
        issues.append({
            "file": filepath,
            "field": "frontmatter",
            "severity": "error",
            "message": "缺少 YAML frontmatter（文件应以 --- 开头）",
        })
        return issues

    # 解析 frontmatter
    try:
        if HAS_FRONTMATTER:
            assert frontmatter is not None
            post = frontmatter.loads(content)
            metadata = dict(post.metadata)
        else:
            metadata = _parse_frontmatter_fallback(content)
    except Exception as e:
        issues.append({
            "file": filepath,
            "field": "frontmatter",
            "severity": "error",
            "message": f"YAML 解析失败: {e}",
        })
        return issues

    if not isinstance(metadata, dict):
        issues.append({
            "file": filepath,
            "field": "frontmatter",
            "severity": "error",
            "message": "Frontmatter 不是合法的 YAML 字典",
        })
        return issues

    # 检查必填字段
    for field, rule in REQUIRED_FIELDS.items():
        if field not in metadata or not metadata[field]:
            issues.append({
                "file": filepath,
                "field": field,
                "severity": rule["severity"],
                "message": f"缺少必填字段 '{field}'（{rule['description']}）",
            })

    # 检查推荐字段
    for field, rule in RECOMMENDED_FIELDS.items():
        if field not in metadata:
            issues.append({
                "file": filepath,
                "field": field,
                "severity": rule["severity"],
                "message": f"缺少推荐字段 '{field}'（{rule['description']}）",
            })

    # 校验 scope 值
    if "scope" in metadata and metadata["scope"]:
        scope_val = str(metadata["scope"]).strip().lower()
        if scope_val not in VALID_SCOPES:
            issues.append({
                "file": filepath,
                "field": "scope",
                "severity": "warning",
                "message": f"scope 值 '{metadata['scope']}' 不在允许范围内 ({', '.join(sorted(VALID_SCOPES))})",
            })

    return issues


def validate_file(filepath: str) -> list[dict]:
    """校验单个文件"""
    path = Path(filepath)
    if not path.exists():
        return [{"file": filepath, "field": "-", "severity": "error", "message": "文件不存在"}]
    if path.suffix.lower() not in ('.md', '.markdown'):
        return []  # 非 Markdown 文件跳过

    content = path.read_text(encoding='utf-8')
    return validate_frontmatter_content(content, filepath)


def main():
    parser = argparse.ArgumentParser(description='Markdown Frontmatter Validator')
    parser.add_argument('files', nargs='+', help='Markdown files to validate')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--version', action='version', version=f'validate_frontmatter {__version__}')
    args = parser.parse_args()

    all_issues = []
    for filepath in args.files:
        issues = validate_file(filepath)
        all_issues.extend(issues)

    # 统计
    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]

    if args.json:
        import json
        print(json.dumps(all_issues, ensure_ascii=False, indent=2))
    else:
        if not all_issues:
            print(f"✅ 全部通过（{len(args.files)} 个文件）")
        else:
            for issue in all_issues:
                icon = "❌" if issue["severity"] == "error" else "⚠️"
                print(f"  {icon} [{issue['severity'].upper()}] {issue['file']}: {issue['message']}")
            print()
            print(f"结果: {len(errors)} error(s), {len(warnings)} warning(s), {len(args.files)} file(s)")

    # 退出码
    if errors:
        sys.exit(1)
    if args.strict and warnings:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
