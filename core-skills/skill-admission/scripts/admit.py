#!/usr/bin/env python3
"""
KitClaw Skill Admission Check

Validates whether a skill meets the acceptance criteria for inclusion
in the KitClaw public repository.

Usage:
    python3 admit.py <skill_path> [--format text|json] [--strict]
    python3 admit.py <skills_root> --all [--format text|json] [--strict]

Exit codes:
    0 = PASS (all required checks passed)
    1 = FAIL (one or more required checks failed)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ── Constants ──────────────────────────────────────────────────────────

FORBIDDEN_FILES = {
    "README.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md",
    "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "CODE_OF_CONDUCT.md",
    "banner.jpg", "banner.png", "logo.png", "logo.jpg",
}

# Patterns that indicate hardcoded personal paths or secrets
PERSONAL_PATH_PATTERNS = [
    r"/home/[a-z][a-z0-9_-]+/",
    r"/Users/[a-z][a-z0-9_-]+/",
    r"C:\\Users\\",
    r"/mnt/[a-z]/",
    r"\\\\wsl\.localhost\\",
]

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"AIza[a-zA-Z0-9_-]{35}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*['\"]?[a-zA-Z0-9]{8,}",
]

# Agent-specific patterns that break portability
AGENT_SPECIFIC_PATTERNS = [
    (r"claude\.json|claude-settings|CLAUDE_CODE", "Claude Code specific"),
    (r"codex-settings|CODEX_HOME", "Codex specific"),
    (r"~/.claude/hooks/", "Claude Code hooks"),
    (r"\$\{CLAUDE_PLUGIN_ROOT\}", "Claude Code plugin variable"),
    (r"oh-my-claudecode|omc", "OMC (Claude Code extension)"),
]

# Required frontmatter keys
REQUIRED_FM_KEYS = {"name", "description"}

# Max body lines before suggesting split
MAX_BODY_LINES_WARN = 500


# ── Result model ───────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    level: str  # "required" | "recommended"
    message: str
    details: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "passed": self.passed,
            "level": self.level,
            "message": self.message,
            "details": self.details,
        }


# ── Individual checks ──────────────────────────────────────────────────

def check_lint(skill_path: Path) -> CheckResult:
    """Check 1: Lint passes (frontmatter, name format, description)."""
    details = []
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return CheckResult("lint", False, "required", "SKILL.md not found")

    content = skill_md.read_text(encoding="utf-8", errors="replace")

    # Parse frontmatter
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return CheckResult("lint", False, "required", "Invalid frontmatter format")

    try:
        fm = yaml.safe_load(match.group(1))
        if not isinstance(fm, dict):
            return CheckResult("lint", False, "required", "Frontmatter must be a YAML dict")
    except yaml.YAMLError as e:
        return CheckResult("lint", False, "required", f"Invalid YAML: {e}")

    # Check required keys
    for key in REQUIRED_FM_KEYS:
        if key not in fm:
            details.append(f"Missing required key: {key}")

    # Check name format
    name = fm.get("name", "")
    if name and not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", str(name)) and len(str(name)) > 1:
        details.append(f"Name '{name}' must be hyphen-case")

    # Check description
    desc = fm.get("description", "")
    if desc and len(str(desc)) > 1024:
        details.append("Description exceeds 1024 chars")

    if details:
        return CheckResult("lint", False, "required", "Lint issues found", details)
    return CheckResult("lint", True, "required", "Frontmatter valid")


def check_security(skill_path: Path) -> CheckResult:
    """Check 2: No secrets or sensitive data."""
    details = []
    for f in skill_path.rglob("*"):
        if not f.is_file() or f.suffix in (".pyc", ".pyo", ".png", ".jpg", ".svg", ".ttf"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel = f.relative_to(skill_path)
        for pattern in SECRET_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                details.append(f"{rel}: potential secret (pattern: {pattern[:20]}...)")

    if details:
        return CheckResult("security", False, "required", "Potential secrets found", details)
    return CheckResult("security", True, "required", "No secrets detected")


def check_no_personal_deps(skill_path: Path) -> CheckResult:
    """Check 3: No hardcoded personal paths or usernames."""
    details = []
    username = os.environ.get("USER", "")

    for f in skill_path.rglob("*"):
        if not f.is_file() or f.suffix in (".pyc", ".pyo", ".png", ".jpg", ".svg", ".ttf"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel = f.relative_to(skill_path)

        # Check personal paths
        for pattern in PERSONAL_PATH_PATTERNS:
            if re.search(pattern, content):
                details.append(f"{rel}: hardcoded personal path ({pattern})")

        # Check username references
        if username and username in content:
            # Allow in comments/examples if quoted
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if username in line and not line.strip().startswith("#"):
                    details.append(f"{rel}:{i}: references username '{username}'")

    if details:
        return CheckResult("no-personal-deps", False, "required",
                          "Personal dependencies found", details[:10])
    return CheckResult("no-personal-deps", True, "required", "No personal dependencies")


def check_agent_agnostic(skill_path: Path) -> CheckResult:
    """Check 4: No agent-specific dependencies."""
    details = []

    for f in skill_path.rglob("*"):
        if not f.is_file() or f.suffix in (".pyc", ".pyo", ".png", ".jpg", ".svg", ".ttf"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel = f.relative_to(skill_path)

        # Skip check scripts themselves (they define patterns to detect, not to use)
        if "admit" in f.stem or "lint" in f.stem or "audit" in f.stem:
            continue

        for pattern, label in AGENT_SPECIFIC_PATTERNS:
            if re.search(pattern, content):
                details.append(f"{rel}: {label}")

    if details:
        return CheckResult("agent-agnostic", False, "required",
                          "Agent-specific dependencies found", details[:10])
    return CheckResult("agent-agnostic", True, "required", "Agent-agnostic")


def check_self_contained(skill_path: Path) -> CheckResult:
    """Check 5: All referenced scripts/resources exist within the skill."""
    details = []
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return CheckResult("self-contained", False, "required", "SKILL.md not found")

    content = skill_md.read_text(encoding="utf-8", errors="replace")

    # Find script references in code blocks and inline
    script_refs = re.findall(r'scripts/[\w.-]+\.py', content)
    ref_refs = re.findall(r'references/[\w.-]+\.md', content)

    for ref in set(script_refs + ref_refs):
        full_path = skill_path / ref
        if not full_path.exists():
            details.append(f"Missing: {ref}")

    if details:
        return CheckResult("self-contained", False, "required",
                          "Missing referenced files", details)
    return CheckResult("self-contained", True, "required", "All references resolved")


def check_docs_complete(skill_path: Path) -> CheckResult:
    """Check 6: Documentation completeness."""
    details = []
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return CheckResult("docs", False, "required", "SKILL.md not found")

    content = skill_md.read_text(encoding="utf-8", errors="replace")
    body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)

    # Check body has meaningful content
    lines = [l for l in body.strip().split("\n") if l.strip()]
    if len(lines) < 5:
        details.append(f"Body too short ({len(lines)} lines, minimum 5)")

    # Check for heading structure
    headings = [l for l in lines if l.startswith("#")]
    if not headings:
        details.append("No headings in body")

    if len(lines) > MAX_BODY_LINES_WARN:
        details.append(f"Body has {len(lines)} lines (>{MAX_BODY_LINES_WARN}), consider splitting")

    if details:
        return CheckResult("docs", True, "recommended", "Documentation could be improved", details)
    return CheckResult("docs", True, "recommended", "Documentation complete")


def check_no_auxiliary_files(skill_path: Path) -> CheckResult:
    """Check 7: No forbidden auxiliary files."""
    details = []
    for forbidden in FORBIDDEN_FILES:
        if (skill_path / forbidden).exists():
            details.append(forbidden)

    if details:
        return CheckResult("no-aux-files", False, "recommended",
                          "Unnecessary files found", details)
    return CheckResult("no-aux-files", True, "recommended", "Clean")


# ── Main ───────────────────────────────────────────────────────────────

ALL_CHECKS = [
    check_lint,
    check_security,
    check_no_personal_deps,
    check_agent_agnostic,
    check_self_contained,
    check_docs_complete,
    check_no_auxiliary_files,
]


def run_admission(skill_path: Path, strict: bool = False) -> list[CheckResult]:
    """Run all admission checks on a skill."""
    results = []
    for check_fn in ALL_CHECKS:
        result = check_fn(skill_path)
        results.append(result)
    return results


def format_text(skill_name: str, results: list[CheckResult]) -> str:
    lines = [f"🔍 Admission Check: {skill_name}"]
    lines.append("=" * 50)

    passed_required = 0
    failed_required = 0
    passed_recommended = 0
    failed_recommended = 0

    for r in results:
        icon = "✅" if r.passed else "❌"
        tag = "REQ" if r.level == "required" else "REC"
        lines.append(f"  {icon} [{tag}] {r.name}: {r.message}")
        for d in r.details:
            lines.append(f"       └─ {d}")

        if r.level == "required":
            if r.passed:
                passed_required += 1
            else:
                failed_required += 1
        else:
            if r.passed:
                passed_recommended += 1
            else:
                failed_recommended += 1

    lines.append("=" * 50)

    if failed_required == 0:
        status = "✅ PASS" if failed_recommended == 0 else "⚠️  PASS (with warnings)"
    else:
        status = "❌ FAIL"

    lines.append(f"Result: {status}")
    lines.append(f"  Required: {passed_required} passed, {failed_required} failed")
    lines.append(f"  Recommended: {passed_recommended} passed, {failed_recommended} failed")

    return "\n".join(lines)


def format_json(skill_name: str, results: list[CheckResult]) -> str:
    failed_required = sum(1 for r in results if r.level == "required" and not r.passed)
    return json.dumps({
        "skill": skill_name,
        "status": "PASS" if failed_required == 0 else "FAIL",
        "checks": [r.to_dict() for r in results],
    }, indent=2, ensure_ascii=False)


def discover_skills(root: Path) -> list[Path]:
    skills = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith((".", "__")):
            if (item / "SKILL.md").exists():
                skills.append(item)
    return skills


def main() -> int:
    parser = argparse.ArgumentParser(description="KitClaw Skill Admission Check")
    parser.add_argument("path", help="Skill directory or skills root (with --all)")
    parser.add_argument("--all", action="store_true", help="Check all skills under path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true",
                        help="Treat recommended checks as required")
    args = parser.parse_args()

    root = Path(args.path).resolve()

    if args.all:
        skills = discover_skills(root)
        if not skills:
            print(f"No skills found under {root}", file=sys.stderr)
            return 1

        all_results = {}
        has_fail = False
        for skill_path in skills:
            results = run_admission(skill_path, strict=args.strict)
            all_results[skill_path.name] = results
            failed = sum(1 for r in results if r.level == "required" and not r.passed)
            if failed > 0:
                has_fail = True

        if args.format == "json":
            out = {name: {"status": "PASS" if all(r.passed for r in res if r.level == "required") else "FAIL",
                          "checks": [r.to_dict() for r in res]}
                   for name, res in all_results.items()}
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            passed_count = sum(1 for res in all_results.values()
                             if all(r.passed for r in res if r.level == "required"))
            print(f"KitClaw Admission — {len(skills)} skills scanned")
            print("=" * 50)
            for name, results in all_results.items():
                failed = [r for r in results if r.level == "required" and not r.passed]
                if failed:
                    print(f"\n❌ {name}")
                    for r in failed:
                        print(f"   [{r.name}] {r.message}")
                        for d in r.details:
                            print(f"     └─ {d}")
                else:
                    warns = [r for r in results if not r.passed]
                    if warns:
                        print(f"⚠️  {name} (passed, {len(warns)} warning(s))")
                    else:
                        print(f"✅ {name}")
            print("=" * 50)
            print(f"Result: {passed_count}/{len(skills)} pass admission")

        return 1 if has_fail else 0

    else:
        if not root.is_dir():
            print(f"Not a directory: {root}", file=sys.stderr)
            return 1

        results = run_admission(root, strict=args.strict)

        if args.format == "json":
            print(format_json(root.name, results))
        else:
            print(format_text(root.name, results))

        failed = sum(1 for r in results if r.level == "required" and not r.passed)
        return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
