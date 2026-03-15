#!/usr/bin/env python3
"""
ensure-knowledge-frontmatter.py

Check Markdown files in a knowledge root for frontmatter and optionally
auto-fill a minimal metadata block for missing files.

Usage:
  python3 ensure-knowledge-frontmatter.py --root <dir>
  python3 ensure-knowledge-frontmatter.py --root <dir> --apply
  python3 ensure-knowledge-frontmatter.py --root <dir> --apply --json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class Finding:
    path: str
    action: str
    title: str
    scope: str
    doc_type: str
    project: str | None
    date: str
    tags: list[str]


def has_frontmatter(text: str) -> bool:
    return text.startswith("---\n") or text.startswith("---\r\n")


def infer_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem


def infer_scope(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    if "content" in parts:
        return "content"
    if "personal" in parts:
        return "personal"
    return "dev"


def infer_type(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    joined = "/".join(p.lower() for p in path.parts)
    if "reports" in parts or "generated-reports" in parts:
        return "report"
    if "playbooks" in parts or "/30_playbooks/" in joined:
        return "playbook"
    if "research" in parts:
        return "research"
    if "adr" in parts or "decisions" in parts:
        return "decision"
    if "templates" in parts:
        return "template"
    if "distilled-conversations" in parts:
        return "generated"
    return "note"


def infer_project(path: Path) -> str | None:
    parts = list(path.parts)
    if "10_Projects" in parts:
        idx = parts.index("10_Projects")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def infer_date(path: Path, text: str) -> str:
    filename = path.name
    for pattern in [
        r"_(\d{8})_\d{6}",
        r"(\d{4}-\d{2}-\d{2})",
    ]:
        match = re.search(pattern, filename)
        if match:
            value = match.group(1)
            if len(value) == 8:
                return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
            return value

    for line in text.splitlines()[:40]:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
        if match:
            return match.group(1)

    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def infer_tags(path: Path, title: str, scope: str, doc_type: str, project: str | None) -> list[str]:
    tags: list[str] = []
    if project:
        tags.append(project)
    prefix_match = re.match(r"\[([A-Za-z0-9_-]+)\]", title)
    if prefix_match:
        tags.append(prefix_match.group(1).lower())
    phase_match = re.search(r"phase[\s-]*(\d+)", title, re.IGNORECASE)
    if phase_match:
        tags.append(f"phase-{phase_match.group(1)}")
    tags.append(doc_type)
    tags.append(scope)

    parts = {p.lower() for p in path.parts}
    if "memory-manager" in title.lower() or "memory-manager" in parts:
        tags.append("memory-manager")
    if "knowledge-search" in title.lower() or "knowledge" in title.lower():
        tags.append("knowledge-search")
    if "obsidian" in title.lower():
        tags.append("obsidian")
    if "orchestrator" in title.lower():
        tags.append("orchestrator")
    if "observability" in title.lower() or "可观测性" in title:
        tags.append("observability")
    if "scheduler" in title.lower() or "定时调度" in title:
        tags.append("scheduler")
    if "mcp" in title.lower():
        tags.append("mcp-export")
    if "linux" in title.lower():
        tags.append("linux")
    if "antigravity" in title.lower():
        tags.append("antigravity")
    if "html" in title.lower():
        tags.append("html")

    deduped: list[str] = []
    for tag in tags:
        if tag and tag not in deduped:
            deduped.append(tag)
    return deduped


def build_frontmatter(finding: Finding) -> str:
    lines = [
        "---",
        f'title: "{finding.title}"',
        "tags: [" + ", ".join(finding.tags) + "]",
        f"scope: {finding.scope}",
        f"type: {finding.doc_type}",
        "status: active",
    ]
    if finding.project:
        lines.append(f"project: {finding.project}")
    lines.append(f'date: "{finding.date}"')
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def scan_markdown(root: Path, apply: bool) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if has_frontmatter(text):
            continue

        title = infer_title(path, text)
        scope = infer_scope(path)
        doc_type = infer_type(path)
        project = infer_project(path)
        date = infer_date(path, text)
        tags = infer_tags(path, title, scope, doc_type, project)

        finding = Finding(
            path=str(path),
            action="filled" if apply else "missing",
            title=title,
            scope=scope,
            doc_type=doc_type,
            project=project,
            date=date,
            tags=tags,
        )
        findings.append(finding)

        if apply:
            frontmatter = build_frontmatter(finding)
            path.write_text(frontmatter + text, encoding="utf-8", newline="\n")

    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check knowledge markdown files for frontmatter and optionally auto-fill missing metadata."
    )
    parser.add_argument("--root", required=True, help="Knowledge root directory to scan")
    parser.add_argument("--apply", action="store_true", help="Write inferred frontmatter into missing files")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Error: root directory not found: {root}")

    findings = scan_markdown(root, apply=args.apply)

    if args.as_json:
        payload = {
            "root": str(root),
            "apply": args.apply,
            "count": len(findings),
            "files": [asdict(item) for item in findings],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "filled" if args.apply else "missing"
        print(f"{mode}: {len(findings)} file(s)")
        for item in findings:
            print(f"- {item.path}")
            print(
                f"  title={item.title} scope={item.scope} type={item.doc_type} "
                f"project={item.project or '-'} date={item.date}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
