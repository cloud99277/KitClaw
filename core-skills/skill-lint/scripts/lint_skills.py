#!/usr/bin/env python3
"""
Repository-wide skill linter.

Checks frontmatter, naming, description quality, body consistency,
and auxiliary file violations across all skills in a directory.

Usage:
    python3 lint_skills.py [path] [--strict] [--format json] [--fail-on-warnings] [--errors-only]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

# ── Constants ──────────────────────────────────────────────────────────

MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_BODY_LINES = 500
ALLOWED_FRONTMATTER_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "io"}

# Files that should NOT exist in a skill directory (skill-creator convention)
FORBIDDEN_FILES = {
    "README.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md",
    "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "CODE_OF_CONDUCT.md",
    "banner.jpg", "banner.png", "logo.png", "logo.jpg",
}

# Legacy/deprecated phrases that may indicate stale description
STALE_DESCRIPTION_PHRASES = [
    "when to use this skill",
    "use this skill when",
    "triggered by",
    "triggers:",
]


# ── Result model ───────────────────────────────────────────────────────

class Issue:
    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"

    def __init__(self, level: str, code: str, message: str):
        self.level = level
        self.code = code
        self.message = message

    def to_dict(self):
        return {"level": self.level, "code": self.code, "message": self.message}

    def __str__(self):
        tag = f"[{self.level}]"
        return f"{tag} {self.code}: {self.message}"


# ── Individual checks ──────────────────────────────────────────────────

def check_frontmatter_exists(content: str) -> list[Issue]:
    issues = []
    if not content.startswith("---"):
        issues.append(Issue(Issue.ERROR, "FM_MISSING", "No YAML frontmatter found (must start with ---)"))
        return issues

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        issues.append(Issue(Issue.ERROR, "FM_INVALID", "Invalid frontmatter format (--- delimiters)"))
    return issues


def parse_frontmatter(content: str) -> tuple[dict | None, str, list[Issue]]:
    """Returns (frontmatter_dict, body_text, issues)."""
    issues = check_frontmatter_exists(content)
    if issues:
        return None, content, issues

    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    fm_text = match.group(1)
    body = match.group(2)

    try:
        fm = yaml.safe_load(fm_text)
        if not isinstance(fm, dict):
            issues.append(Issue(Issue.ERROR, "FM_TYPE", "Frontmatter must be a YAML dictionary"))
            return None, body, issues
    except yaml.YAMLError as e:
        issues.append(Issue(Issue.ERROR, "FM_YAML", f"Invalid YAML: {e}"))
        return None, body, issues

    return fm, body, issues


def check_name(fm: dict) -> list[Issue]:
    issues = []
    name = fm.get("name")
    if name is None:
        issues.append(Issue(Issue.ERROR, "NAME_MISSING", "Missing 'name' in frontmatter"))
        return issues

    if not isinstance(name, str):
        issues.append(Issue(Issue.ERROR, "NAME_TYPE", f"Name must be string, got {type(name).__name__}"))
        return issues

    name = name.strip()
    if not name:
        issues.append(Issue(Issue.ERROR, "NAME_EMPTY", "Name is empty"))
        return issues

    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name) and len(name) > 1:
        issues.append(Issue(Issue.ERROR, "NAME_FORMAT",
            f"Name '{name}' must be hyphen-case (lowercase, digits, hyphens; cannot start/end with hyphen)"))

    if "--" in name:
        issues.append(Issue(Issue.ERROR, "NAME_HYPHENS", f"Name '{name}' contains consecutive hyphens"))

    if len(name) > MAX_SKILL_NAME_LENGTH:
        issues.append(Issue(Issue.ERROR, "NAME_LENGTH",
            f"Name too long ({len(name)} chars, max {MAX_SKILL_NAME_LENGTH})"))

    return issues


def check_description(fm: dict) -> list[Issue]:
    issues = []
    desc = fm.get("description")
    if desc is None:
        issues.append(Issue(Issue.ERROR, "DESC_MISSING", "Missing 'description' in frontmatter"))
        return issues

    if not isinstance(desc, str):
        issues.append(Issue(Issue.ERROR, "DESC_TYPE", f"Description must be string, got {type(desc).__name__}"))
        return issues

    desc = desc.strip()
    if not desc:
        issues.append(Issue(Issue.ERROR, "DESC_EMPTY", "Description is empty"))
        return issues

    if "<" in desc or ">" in desc:
        issues.append(Issue(Issue.ERROR, "DESC_BRACKETS", "Description contains angle brackets (< or >)"))

    if len(desc) > MAX_DESCRIPTION_LENGTH:
        issues.append(Issue(Issue.ERROR, "DESC_LENGTH",
            f"Description too long ({len(desc)} chars, max {MAX_DESCRIPTION_LENGTH})"))

    for phrase in STALE_DESCRIPTION_PHRASES:
        if phrase.lower() in desc.lower():
            issues.append(Issue(Issue.WARN, "DESC_STALE_PHRASE",
                f"Description contains possibly stale phrase: '{phrase}'"))

    return issues


def check_frontmatter_keys(fm: dict) -> list[Issue]:
    issues = []
    unexpected = set(fm.keys()) - ALLOWED_FRONTMATTER_KEYS
    if unexpected:
        allowed = ", ".join(sorted(ALLOWED_FRONTMATTER_KEYS))
        bad = ", ".join(sorted(unexpected))
        issues.append(Issue(Issue.WARN, "FM_EXTRA_KEYS",
            f"Unexpected frontmatter keys: {bad}. Allowed: {allowed}"))
    return issues


def check_body(body: str) -> list[Issue]:
    issues = []
    lines = body.strip().split("\n") if body.strip() else []
    if len(lines) > MAX_BODY_LINES:
        issues.append(Issue(Issue.WARN, "BODY_LONG",
            f"Body has {len(lines)} lines (recommended max {MAX_BODY_LINES}). "
            f"Consider splitting detailed content into references/"))

    return issues


def check_auxiliary_files(skill_path: Path) -> list[Issue]:
    issues = []
    for forbidden in FORBIDDEN_FILES:
        fp = skill_path / forbidden
        if fp.exists():
            issues.append(Issue(Issue.WARN, "AUX_FILE",
                f"Unnecessary file: {forbidden} (skill-creator convention: don't include auxiliary docs)"))
    return issues


def check_references_structure(skill_path: Path) -> list[Issue]:
    issues = []
    refs_dir = skill_path / "references"
    scripts_dir = skill_path / "scripts"

    if refs_dir.exists():
        for f in refs_dir.iterdir():
            if f.suffix == ".md" and f.stat().st_size > 15000:
                issues.append(Issue(Issue.WARN, "REF_LARGE",
                    f"references/{f.name} is large ({f.stat().st_size // 1024}KB). "
                    f"Consider adding grep patterns in SKILL.md"))

    return issues


# ── Main lint logic ────────────────────────────────────────────────────

def lint_skill(skill_path: Path, strict: bool = False) -> list[Issue]:
    """Lint a single skill directory. Returns list of issues."""
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return [Issue(Issue.ERROR, "SKILL_MD_MISSING", "SKILL.md not found")]

    content = skill_md.read_text(encoding="utf-8", errors="replace")
    all_issues: list[Issue] = []

    # Parse frontmatter
    fm, body, parse_issues = parse_frontmatter(content)
    all_issues.extend(parse_issues)

    if fm is None:
        return all_issues  # Can't continue without valid frontmatter

    # Core checks
    all_issues.extend(check_name(fm))
    all_issues.extend(check_description(fm))
    all_issues.extend(check_frontmatter_keys(fm))
    all_issues.extend(check_body(body))
    all_issues.extend(check_auxiliary_files(skill_path))
    all_issues.extend(check_references_structure(skill_path))

    # Strict-only checks
    if strict:
        if "description" in fm:
            desc = fm["description"].strip()
            # In strict mode, description should mention trigger conditions
            trigger_words = ["use when", "triggers", "触发", "when to", "prefer"]
            if not any(tw in desc.lower() for tw in trigger_words):
                all_issues.append(Issue(Issue.WARN, "DESC_NO_TRIGGER",
                    "Description doesn't mention when to trigger (strict mode)"))

    return all_issues


def discover_skills(root: Path) -> list[Path]:
    """Find all skill directories (contain SKILL.md) under root."""
    skills = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith((".", "__")):
            if (item / "SKILL.md").exists():
                skills.append(item)
    return skills


def lint_all(root: Path, strict: bool = False) -> dict[str, list[Issue]]:
    """Lint all skills under root. Returns {skill_name: [issues]}."""
    results = {}
    skills = discover_skills(root)
    for skill_path in skills:
        issues = lint_skill(skill_path, strict=strict)
        results[skill_path.name] = issues
    return results


# ── Output formatters ──────────────────────────────────────────────────

def format_text(results: dict[str, list[Issue]], errors_only: bool = False) -> str:
    lines = []
    total_ok = 0
    total_warn = 0
    total_error = 0

    for skill_name, issues in results.items():
        has_errors = any(i.level == Issue.ERROR for i in issues)
        has_warnings = any(i.level == Issue.WARN for i in issues)

        if errors_only and not has_errors:
            continue

        if not issues:
            total_ok += 1
            if not errors_only:
                lines.append(f"  ✅ {skill_name}")
            continue

        if has_errors:
            total_error += 1
        elif has_warnings:
            total_warn += 1

        for issue in issues:
            if errors_only and issue.level != Issue.ERROR:
                continue
            lines.append(f"  {issue} [{skill_name}]")

    summary = f"\n── Summary: {total_ok} OK, {total_warn} WARN, {total_error} ERROR ──"
    header = f"Scanned {len(results)} skills under {root_display}\n"

    return header + "\n".join(lines) + summary


def format_json(results: dict[str, list[Issue]]) -> str:
    out = {}
    for skill_name, issues in results.items():
        out[skill_name] = {
            "status": "ERROR" if any(i.level == Issue.ERROR for i in issues)
                      else "WARN" if any(i.level == Issue.WARN for i in issues)
                      else "OK",
            "issues": [i.to_dict() for i in issues],
        }
    return json.dumps(out, indent=2, ensure_ascii=False)


# ── CLI ────────────────────────────────────────────────────────────────

root_display = ""

def main() -> int:
    global root_display

    parser = argparse.ArgumentParser(description="Lint skills repository")
    parser.add_argument("path", nargs="?", default=".", help="Skills root directory")
    parser.add_argument("--strict", action="store_true", help="Enable strict checks")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--fail-on-warnings", action="store_true")
    parser.add_argument("--errors-only", action="store_true")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    root_display = str(root)

    if not root.is_dir():
        print(f"[ERROR] Not a directory: {root}", file=sys.stderr)
        return 1

    results = lint_all(root, strict=args.strict)

    if args.format == "json":
        print(format_json(results))
    else:
        print(format_text(results, errors_only=args.errors_only))

    # Exit code
    has_errors = any(
        i.level == Issue.ERROR
        for issues in results.values()
        for i in issues
    )
    has_warnings = any(
        i.level == Issue.WARN
        for issues in results.values()
        for i in issues
    )

    if has_errors:
        return 1
    if args.fail_on_warnings and has_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
