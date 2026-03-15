#!/usr/bin/env python3
# ruff: noqa: E402
"""
Heading-Aware Markdown Chunker
将 Markdown 文件按标题层级切分为语义完整的 chunk。

用法:
  python3 md_chunker.py parse <file.md> [--json] [--min-size 50] [--max-size 2000]
  python3 md_chunker.py scan <directory> [--json] [--extensions .md,.markdown]
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

__version__ = "1.0.0"

# 尝试导入 python-frontmatter，不存在时降级为简单解析
try:
    import frontmatter
    HAS_FRONTMATTER = True
except ImportError:
    frontmatter = None
    HAS_FRONTMATTER = False


@dataclass
class MarkdownChunk:
    """一个语义完整的 Markdown 文本块"""
    text: str
    heading_path: list = field(default_factory=list)
    level: int = 0
    source_file: str = ""
    start_line: int = 0
    end_line: int = 0
    metadata: dict = field(default_factory=dict)
    chunk_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- frontmatter 解析 ----------

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (metadata, body)"""
    if HAS_FRONTMATTER:
        assert frontmatter is not None
        post = frontmatter.loads(content)
        return dict(post.metadata), post.content
    # 降级：简单正则解析
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if m:
        meta = {}
        for line in m.group(1).split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
        return meta, content[m.end():]
    return {}, content


# ---------- 核心切分逻辑 ----------

HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')


def _build_code_block_lines(lines: list[str]) -> set[int]:
    """预扫描，返回所有在代码块内部的行号集合（O(n) 一次扫描）"""
    in_code = set()
    inside = False
    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            inside = not inside
        elif inside:
            in_code.add(i)
    return in_code


def _split_large_chunk(text: str, max_size: int) -> list[str]:
    """将超长文本在段落边界（空行）处分割"""
    if len(text) <= max_size:
        return [text]
    parts = []
    current = []
    current_len = 0
    for line in text.split('\n'):
        line_len = len(line) + 1  # +1 for newline
        if line.strip() == '' and current_len >= max_size // 2:
            # 在空行处切割
            parts.append('\n'.join(current))
            current = []
            current_len = 0
        else:
            current.append(line)
            current_len += line_len
    if current:
        parts.append('\n'.join(current))
    return parts if parts else [text]


def chunk_markdown(
    content: str,
    source_file: str = "",
    metadata: Optional[dict] = None,
    min_size: int = 50,
    max_size: int = 2000,
    max_heading_level: int = 3,
) -> list[MarkdownChunk]:
    """
    将 Markdown 内容按标题层级切分为 chunk 列表。

    Args:
        content: Markdown 正文（不含 frontmatter）
        source_file: 来源文件路径
        metadata: 从 frontmatter 提取的元数据
        min_size: 最小 chunk 大小（字符），低于此值合并到上一个
        max_size: 最大 chunk 大小（字符），超过此值在段落边界分割
        max_heading_level: 参与切分的最大标题层级（1-6）
    """
    if metadata is None:
        metadata = {}

    lines = content.split('\n')
    chunks: list[MarkdownChunk] = []
    code_block_lines = _build_code_block_lines(lines)  # O(n) 预扫描

    # 当前状态
    current_lines: list[str] = []
    current_start = 1  # 1-indexed
    heading_stack: list[tuple[int, str]] = []  # [(level, title), ...]

    def _flush(end_line: int):
        """将累积的行输出为一个或多个 chunk"""
        nonlocal current_lines, current_start
        text = '\n'.join(current_lines).strip()
        if not text:
            current_lines = []
            return

        path = [f"{'#' * lvl} {title}" for lvl, title in heading_stack]
        level = heading_stack[-1][0] if heading_stack else 0

        # 大 chunk 分割
        segments = _split_large_chunk(text, max_size)
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            chunk = MarkdownChunk(
                text=seg,
                heading_path=list(path),
                level=level,
                source_file=source_file,
                start_line=current_start,
                end_line=end_line,
                metadata=dict(metadata),
            )
            chunks.append(chunk)
        current_lines = []

    for i, line in enumerate(lines):
        line_num = i + 1  # frontmatter 已被移除，行号从正文开始

        # 检查是否在代码块中（O(1) 查表）
        if i in code_block_lines:
            current_lines.append(line)
            continue

        # 检查是否是标题行
        m = HEADING_RE.match(line)
        if m:
            h_level = len(m.group(1))
            h_title = m.group(2).strip()

            if h_level <= max_heading_level:
                # flush 之前的内容
                _flush(line_num - 1)
                current_start = line_num

                # 更新标题栈：弹出同级或更深的标题
                while heading_stack and heading_stack[-1][0] >= h_level:
                    heading_stack.pop()
                heading_stack.append((h_level, h_title))

                current_lines.append(line)
                continue

        current_lines.append(line)

    # flush 最后一段
    _flush(len(lines))

    # 合并过小的 chunk
    if len(chunks) > 1:
        merged: list[MarkdownChunk] = [chunks[0]]
        for chunk in chunks[1:]:
            if len(merged[-1].text) < min_size:
                # 合并到前一个
                merged[-1].text += '\n\n' + chunk.text
                merged[-1].end_line = chunk.end_line
            else:
                merged.append(chunk)
        # 最后一个太小也合并
        if len(merged) > 1 and len(merged[-1].text) < min_size:
            merged[-2].text += '\n\n' + merged[-1].text
            merged[-2].end_line = merged[-1].end_line
            merged.pop()
        chunks = merged

    # 生成 chunk_id
    for chunk in chunks:
        path_str = '::'.join(chunk.heading_path) if chunk.heading_path else '_root_'
        raw_id = f"{source_file}::{path_str}::{chunk.start_line}"
        chunk.chunk_id = hashlib.md5(raw_id.encode()).hexdigest()[:12]

    return chunks


# ---------- 文件 / 目录处理 ----------

def parse_file(filepath: str, min_size: int = 50, max_size: int = 2000) -> list[MarkdownChunk]:
    """解析单个 Markdown 文件"""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return []

    content = path.read_text(encoding='utf-8')
    metadata, body = parse_frontmatter(content)
    return chunk_markdown(
        content=body,
        source_file=str(path),
        metadata=metadata,
        min_size=min_size,
        max_size=max_size,
    )


def scan_directory(
    directory: str,
    extensions: list[str] | None = None,
    min_size: int = 50,
    max_size: int = 2000,
) -> list[MarkdownChunk]:
    """扫描目录下所有 Markdown 文件"""
    if extensions is None:
        extensions = ['.md', '.markdown']

    all_chunks = []
    root = Path(directory)
    if not root.is_dir():
        print(f"Error: Not a directory: {directory}", file=sys.stderr)
        return []

    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix.lower() in extensions:
            # 跳过隐藏目录
            parts = path.relative_to(root).parts
            if any(p.startswith('.') for p in parts):
                continue
            rel_path = str(path.relative_to(root))
            chunks = parse_file(str(path), min_size, max_size)
            # 用相对路径覆盖绝对路径
            for c in chunks:
                c.source_file = rel_path
                # 重新计算 chunk_id
                path_str = '::'.join(c.heading_path) if c.heading_path else '_root_'
                raw_id = f"{rel_path}::{path_str}::{c.start_line}"
                c.chunk_id = hashlib.md5(raw_id.encode()).hexdigest()[:12]
            all_chunks.extend(chunks)

    return all_chunks


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description='Heading-Aware Markdown Chunker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'md_chunker {__version__}')

    sub = parser.add_subparsers(dest='command', required=True)

    # parse 子命令
    p_parse = sub.add_parser('parse', help='Parse a single Markdown file')
    p_parse.add_argument('file', help='Path to Markdown file')
    p_parse.add_argument('--json', action='store_true', help='Output as JSON')
    p_parse.add_argument('--min-size', type=int, default=50, help='Min chunk size (chars)')
    p_parse.add_argument('--max-size', type=int, default=2000, help='Max chunk size (chars)')

    # scan 子命令
    p_scan = sub.add_parser('scan', help='Scan a directory for Markdown files')
    p_scan.add_argument('directory', help='Directory to scan')
    p_scan.add_argument('--json', action='store_true', help='Output as JSON')
    p_scan.add_argument('--extensions', default='.md,.markdown', help='File extensions')
    p_scan.add_argument('--min-size', type=int, default=50, help='Min chunk size (chars)')
    p_scan.add_argument('--max-size', type=int, default=2000, help='Max chunk size (chars)')

    args = parser.parse_args()

    if args.command == 'parse':
        chunks = parse_file(args.file, args.min_size, args.max_size)
    elif args.command == 'scan':
        exts = [e.strip() if e.startswith('.') else f'.{e.strip()}' for e in args.extensions.split(',')]
        chunks = scan_directory(args.directory, exts, args.min_size, args.max_size)
    else:
        parser.print_help()
        return

    if not chunks:
        print("No chunks found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2))
    else:
        for i, c in enumerate(chunks, 1):
            path_display = ' > '.join(c.heading_path) if c.heading_path else '(document root)'
            print(f"--- Chunk {i} [{c.chunk_id}] L{c.start_line}-L{c.end_line} ---")
            print(f"  Path: {path_display}")
            print(f"  File: {c.source_file}")
            print(f"  Size: {len(c.text)} chars")
            if c.metadata:
                tags = c.metadata.get('tags', '')
                scope = c.metadata.get('scope', '')
                if tags or scope:
                    print(f"  Meta: tags={tags} scope={scope}")
            preview = c.text[:120].replace('\n', ' ')
            print(f"  Preview: {preview}...")
            print()

    print(f"Total: {len(chunks)} chunks", file=sys.stderr)


if __name__ == '__main__':
    main()
