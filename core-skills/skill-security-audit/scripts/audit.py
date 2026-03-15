#!/usr/bin/env python3
"""Static security audit for KitClaw skills."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCANNER_VERSION = "0.3.0"
SCHEMA_VERSION = "1.0"
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_SKILLS_DIR = REPO_ROOT / "core-skills"

CREDENTIAL_PATTERNS: list[tuple[str, str, str]] = [
    ("CRED-001", r"(?i)(api[_-]?key|apikey)\s*[=:]\s*[\"']?[A-Za-z0-9_-]{20,}", "generic API key"),
    ("CRED-002", r"sk-[A-Za-z0-9]{20,}", "OpenAI API key"),
    ("CRED-003", r"sk-ant-[A-Za-z0-9]{20,}", "Anthropic API key"),
    ("CRED-004", r"AIza[A-Za-z0-9_-]{35}", "Google API key"),
    ("CRED-005", r"(?i)(token|secret)\s*[=:]\s*[\"']?[A-Za-z0-9_-]{20,}", "token or secret"),
    ("CRED-006", r"(?i)password\s*[=:]\s*[\"']?[^\s\"']{8,}", "password"),
    ("CRED-007", r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    ("CRED-008", r"(?:gho|ghs|ghr)_[A-Za-z0-9]{36}", "GitHub OAuth or app token"),
    ("CRED-009", r"AKIA[A-Z0-9]{16}", "AWS access key"),
]

SAFE_PATTERNS = [
    re.compile(r"os\.environ"),
    re.compile(r"os\.getenv"),
    re.compile(r"process\.env"),
    re.compile(r"\$\{?\w+\}?"),
]

NETWORK_PATTERNS: list[tuple[str, str, str]] = [
    ("EXFIL-001", r"requests\.(get|post|put|delete|patch|head|options)\s*\(", "Python requests"),
    ("EXFIL-002", r"httpx\.(get|post|put|delete|patch|Client|AsyncClient)", "Python httpx"),
    ("EXFIL-003", r"urllib\.request", "Python urllib"),
    ("EXFIL-004", r"(?<!\w)curl\s+", "curl command"),
    ("EXFIL-005", r"(?<!\w)wget\s+", "wget command"),
    ("EXFIL-006", r"fetch\s*\(", "JavaScript fetch"),
    ("EXFIL-007", r"aiohttp\.(ClientSession|request)", "Python aiohttp"),
]

WRITE_PATTERNS = [
    re.compile(r"open\s*\(.+['\"][wax]['\"]"),
    re.compile(r"open\s*\(.+mode\s*=\s*['\"][wax]['\"]"),
    re.compile(r"\.write\s*\("),
    re.compile(r"\.writelines\s*\("),
]

NETWORK_KEYWORDS = [
    "url",
    "http",
    "https",
    "fetch",
    "download",
    "api",
    "request",
    "web",
    "endpoint",
    "webhook",
    "network",
]

REVERSE_MARKERS = [
    re.compile(r"reverse[\s-]?engineer", re.IGNORECASE),
    re.compile(r"reverse[\s-]?api", re.IGNORECASE),
    re.compile(r"unofficial[\s-]?api", re.IGNORECASE),
    re.compile(r"undocumented[\s-]?(api|endpoint)", re.IGNORECASE),
]

SUPPLY_CHAIN_FILES = ("requirements.txt", "package.json", "Pipfile", "pyproject.toml")


def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def is_comment_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith("//")


def line_has_safe_pattern(line: str) -> bool:
    return any(pattern.search(line) for pattern in SAFE_PATTERNS)


def parse_frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---"):
        return {}

    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    end_index = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index == -1:
        return {}

    frontmatter: dict[str, Any] = {}
    current_key: str | None = None
    for line in lines[1:end_index]:
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            frontmatter[key] = value
            current_key = key if value in {"|", ">"} else key
            continue

        if current_key and line.startswith((" ", "\t")):
            previous = str(frontmatter.get(current_key, "")).strip(">| ").strip()
            frontmatter[current_key] = f"{previous} {line.strip()}".strip()

    return frontmatter


def get_script_files(skill_path: Path) -> list[Path]:
    scripts_dir = skill_path / "scripts"
    if not scripts_dir.exists():
        return []

    allowed_suffixes = {
        "",
        ".bash",
        ".cfg",
        ".conf",
        ".csv",
        ".env",
        ".go",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".kt",
        ".md",
        ".pl",
        ".py",
        ".rb",
        ".rs",
        ".sh",
        ".swift",
        ".toml",
        ".ts",
        ".txt",
        ".yaml",
        ".yml",
    }

    return [
        path
        for path in scripts_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed_suffixes
    ]


def load_ignore_patterns(skill_path: Path) -> list[str]:
    ignore_path = skill_path / ".audit-ignore"
    if not ignore_path.exists():
        return []

    patterns: list[str] = []
    for line in read_file_safe(ignore_path).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped)
    return patterns


def should_ignore(path: Path, skill_path: Path, ignore_patterns: list[str]) -> bool:
    relative_path = str(path.relative_to(skill_path))
    return any(
        fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(path.name, pattern)
        for pattern in ignore_patterns
    )


def skill_declares_network(frontmatter: dict[str, Any], skill_md_content: str) -> bool:
    description = str(frontmatter.get("description", "")).lower()
    content_lower = skill_md_content.lower()
    return any(keyword in description for keyword in NETWORK_KEYWORDS) or "type: url" in content_lower


def scan_credentials(skill_path: Path, script_files: list[Path], ignore_patterns: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for file_path in script_files:
        if should_ignore(file_path, skill_path, ignore_patterns):
            continue
        for line_number, line in enumerate(read_file_safe(file_path).splitlines(), 1):
            if is_comment_line(line) or line_has_safe_pattern(line):
                continue
            for rule_id, pattern, description in CREDENTIAL_PATTERNS:
                if re.search(pattern, line):
                    findings.append(
                        finding(
                            "credential_leak",
                            "critical",
                            rule_id,
                            file_path.relative_to(skill_path),
                            line_number,
                            description,
                            line.strip()[:80],
                        )
                    )
                    break
    return findings


def scan_network(
    skill_path: Path,
    script_files: list[Path],
    ignore_patterns: list[str],
    declares_network: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    found_network = False
    for file_path in script_files:
        if should_ignore(file_path, skill_path, ignore_patterns):
            continue
        for line_number, line in enumerate(read_file_safe(file_path).splitlines(), 1):
            if is_comment_line(line):
                continue
            for rule_id, pattern, description in NETWORK_PATTERNS:
                if re.search(pattern, line):
                    found_network = True
                    if not declares_network:
                        findings.append(
                            finding(
                                "data_exfil",
                                "critical",
                                rule_id,
                                file_path.relative_to(skill_path),
                                line_number,
                                f"Undeclared external request: {description}",
                                line.strip()[:80],
                            )
                        )
                    break
    if found_network and not declares_network:
        findings.append(
            finding(
                "network_overreach",
                "high",
                "NET-001",
                Path("scripts"),
                0,
                "scripts/ contains network calls but SKILL.md does not declare network access",
                "",
            )
        )
    return findings


def scan_io_overreach(
    skill_path: Path,
    script_files: list[Path],
    skill_md_content: str,
) -> list[dict[str, Any]]:
    if "io:" not in skill_md_content:
        return []

    content_lower = skill_md_content.lower()
    declares_file_output = any(
        marker in content_lower
        for marker in (
            "type: markdown_file",
            "type: json_data",
            "type: image_file",
            "type: directory",
        )
    )

    for file_path in script_files:
        content = read_file_safe(file_path)
        for line_number, line in enumerate(content.splitlines(), 1):
            if any(pattern.search(line) for pattern in WRITE_PATTERNS):
                if not declares_file_output:
                    return [
                        finding(
                            "io_overreach",
                            "high",
                            "IO-001",
                            file_path.relative_to(skill_path),
                            line_number,
                            "scripts/ writes files but io.output declares no file-like artifact",
                            line.strip()[:80],
                        )
                    ]
                return []
    return []


def scan_consent(skill_path: Path, skill_md_content: str) -> list[dict[str, Any]]:
    if not any(pattern.search(skill_md_content) for pattern in REVERSE_MARKERS):
        return []
    if "danger-" in skill_path.name:
        return []
    return [
        finding(
            "consent",
            "medium",
            "CONS-001",
            Path("SKILL.md"),
            0,
            "SKILL.md references reverse or unofficial APIs without a danger-style name",
            "",
        )
    ]


def scan_supply_chain(skill_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for index, filename in enumerate(SUPPLY_CHAIN_FILES, start=1):
        path = skill_path / filename
        if not path.exists():
            continue
        findings.append(
            finding(
                "supply_chain",
                "low",
                f"SUPPLY-{index:03d}",
                Path(filename),
                0,
                f"Dependency manifest present: {filename}",
                read_file_safe(path)[:120].strip(),
            )
        )
    return findings


def finding(
    dimension: str,
    severity: str,
    rule_id: str,
    file_path: Path,
    line: int,
    message: str,
    matched_content: str,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "severity": severity,
        "rule_id": rule_id,
        "file": str(file_path),
        "line": line,
        "matched_content": matched_content,
        "whitelisted": False,
        "message": message,
    }


def summarize(findings: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for item in findings:
        summary[item["severity"]] += 1
    return summary


def audit_single_skill(skill_path: Path, dimensions: list[str] | None = None) -> dict[str, Any]:
    skill_md_path = skill_path / "SKILL.md"
    if not skill_md_path.exists():
        findings = [
            finding("general", "medium", "GENERAL-001", Path(""), 0, "SKILL.md not found", "")
        ]
        return {
            "skill_path": str(skill_path),
            "skill_name": skill_path.name,
            "status": "WARNING",
            "findings": findings,
            "summary": summarize(findings),
        }

    skill_md_content = read_file_safe(skill_md_path)
    frontmatter = parse_frontmatter(skill_md_content)
    script_files = get_script_files(skill_path)
    ignore_patterns = load_ignore_patterns(skill_path)
    declares_network = skill_declares_network(frontmatter, skill_md_content)

    requested = set(dimensions or [])
    run_all = not requested
    findings: list[dict[str, Any]] = []

    if run_all or "credentials" in requested:
        findings.extend(scan_credentials(skill_path, script_files, ignore_patterns))
    if run_all or "exfil" in requested or "network" in requested:
        findings.extend(scan_network(skill_path, script_files, ignore_patterns, declares_network))
    if run_all or "io" in requested:
        findings.extend(scan_io_overreach(skill_path, script_files, skill_md_content))
    if run_all or "consent" in requested:
        findings.extend(scan_consent(skill_path, skill_md_content))
    if run_all or "supply_chain" in requested:
        findings.extend(scan_supply_chain(skill_path))

    summary = summarize(findings)
    if summary["critical"] > 0:
        status = "CRITICAL"
    elif summary["high"] > 0 or summary["medium"] > 0:
        status = "WARNING"
    else:
        status = "PASS"

    return {
        "skill_path": str(skill_path),
        "skill_name": skill_path.name,
        "status": status,
        "findings": findings,
        "summary": summary,
    }


def audit_all_skills(skills_dir: Path, dimensions: list[str] | None = None) -> list[dict[str, Any]]:
    if not skills_dir.exists():
        print(f"Error: directory not found: {skills_dir}", file=sys.stderr)
        raise SystemExit(1)

    results: list[dict[str, Any]] = []
    for entry in sorted(skills_dir.iterdir(), key=lambda item: item.name):
        if entry.is_dir() and not entry.name.startswith((".", "_")) and (entry / "SKILL.md").exists():
            results.append(audit_single_skill(entry, dimensions))
    return results


def build_report(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "scanner_version": SCANNER_VERSION,
        "mode": mode,
        "results": results,
        "global_summary": {
            "total_skills": len(results),
            "pass": sum(1 for item in results if item["status"] == "PASS"),
            "warning": sum(1 for item in results if item["status"] == "WARNING"),
            "critical": sum(1 for item in results if item["status"] == "CRITICAL"),
        },
    }


def print_results(results: list[dict[str, Any]]) -> None:
    for result in results:
        summary = result["summary"]
        total = sum(summary.values())
        print(f"[{result['status']}] {result['skill_name']} ({total} findings)")
        for item in result["findings"]:
            if item["severity"] in {"critical", "high"}:
                location = item["file"] if item["line"] == 0 else f"{item['file']}:{item['line']}"
                print(f"  - {item['rule_id']}: {location} - {item['message']}")

    print()
    print(
        "Total: {total} | PASS: {passed} | WARNING: {warn} | CRITICAL: {critical}".format(
            total=len(results),
            passed=sum(1 for item in results if item["status"] == "PASS"),
            warn=sum(1 for item in results if item["status"] == "WARNING"),
            critical=sum(1 for item in results if item["status"] == "CRITICAL"),
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Static security audit for shared skill repositories")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_SKILLS_DIR),
        help=f"Skill directory or skills root (default: {DEFAULT_SKILLS_DIR})",
    )
    parser.add_argument("--all", action="store_true", help="Audit all skills under the target directory")
    parser.add_argument(
        "--dimension",
        choices=["credentials", "exfil", "network", "io", "consent", "supply_chain"],
        help="Limit the audit to a single dimension",
    )
    parser.add_argument("--output", "-o", help="Write the full JSON report to a file")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report to stdout")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {SCANNER_VERSION} (schema {SCHEMA_VERSION})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.path).expanduser().resolve()
    dimensions = [args.dimension] if args.dimension else None

    if args.all:
        results = audit_all_skills(target, dimensions)
        mode = "all"
    else:
        if not target.is_dir():
            print(f"Error: not a directory: {target}", file=sys.stderr)
            return 1
        results = [audit_single_skill(target, dimensions)]
        mode = "single"

    report = build_report(results, mode)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Report saved to: {output_path}")
        print_results(results)
    elif args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_results(results)

    return 1 if any(item["status"] == "CRITICAL" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
