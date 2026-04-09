#!/usr/bin/env python3
"""Runtime health checks for the shared KitClaw/WSL runtime."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_PATH = Path.home() / ".ai-skills" / ".system" / "runtime-manifest.json"


@dataclass
class CheckResult:
    name: str
    status: str
    details: str
    path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "details": self.details,
        }
        if self.path is not None:
            payload["path"] = self.path
        return payload


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object")
    return data


def normalize_path(value: str) -> Path:
    return Path(value).expanduser()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_codex_env(config_text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    in_env_block = False

    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_env_block = line == "[shell_environment_policy.set]"
            continue
        if not in_env_block:
            continue
        match = re.match(r'^([A-Z0-9_]+)\s*=\s*"(.*)"$', line)
        if match:
            env[match.group(1)] = match.group(2)
    return env


def check_readable_file(name: str, path: Path) -> CheckResult:
    if not path.exists():
        return CheckResult(name=name, status="FAIL", details="missing file", path=str(path))
    if not os.access(path, os.R_OK):
        return CheckResult(name=name, status="FAIL", details="file is not readable", path=str(path))
    return CheckResult(name=name, status="PASS", details="readable", path=str(path))


def check_directory(name: str, path: Path) -> CheckResult:
    if not path.exists():
        return CheckResult(name=name, status="FAIL", details="missing directory", path=str(path))
    if not path.is_dir():
        return CheckResult(name=name, status="FAIL", details="not a directory", path=str(path))
    if not os.access(path, os.R_OK | os.X_OK):
        return CheckResult(name=name, status="FAIL", details="directory is not readable", path=str(path))
    return CheckResult(name=name, status="PASS", details="directory readable", path=str(path))


def check_json_file(name: str, path: Path) -> CheckResult:
    result = check_readable_file(name, path)
    if result.status != "PASS":
        return result
    try:
        load_json(path)
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(name=name, status="FAIL", details=f"invalid JSON: {exc}", path=str(path))
    return CheckResult(name=name, status="PASS", details="valid JSON", path=str(path))


def check_manifest(manifest: dict[str, Any], manifest_path: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    canonical = manifest.get("canonical", {})
    windows = manifest.get("windows", {})
    openclaw = manifest.get("openclaw", {})
    bridge = manifest.get("bridge", {})

    skills_root = normalize_path(str(canonical.get("skills_root", "")))
    memory_root = normalize_path(str(canonical.get("memory_root", "")))
    whiteboard_path = normalize_path(str(canonical.get("whiteboard_path", "")))
    memory_config_path = normalize_path(str(canonical.get("memory_config_path", "")))
    observability_log_path = normalize_path(str(canonical.get("observability_log_path", "")))
    l3_roots = [normalize_path(str(value)) for value in canonical.get("l3_roots", [])]

    codex_config_path = normalize_path(str(windows.get("codex_config_path", "")))
    codex_state_path = normalize_path(str(windows.get("codex_global_state_path", "")))
    codex_skill_root = normalize_path(str(windows.get("codex_skill_root", "")))
    agents_skill_root = normalize_path(str(windows.get("agents_skill_root", "")))
    expected_env = windows.get("environment", {})

    shared_link = normalize_path(str(openclaw.get("shared_skill_link", "")))
    shared_target = normalize_path(str(openclaw.get("shared_skill_target", "")))

    curated_skills = bridge.get("curated_codex_skills", [])

    results.append(check_readable_file("manifest", manifest_path))
    results.append(check_directory("skills_root", skills_root))
    results.append(check_directory("memory_root", memory_root))
    results.append(check_json_file("whiteboard", whiteboard_path))
    results.append(check_json_file("memory_config", memory_config_path))

    if memory_config_path.exists():
        try:
            memory_config = load_json(memory_config_path)
            configured_roots = [normalize_path(str(value)) for value in memory_config.get("l3_paths", [])]
        except Exception as exc:  # pragma: no cover - defensive
            results.append(
                CheckResult(
                    name="l3_config",
                    status="FAIL",
                    details=f"invalid JSON config: {exc}",
                    path=str(memory_config_path),
                )
            )
            configured_roots = []
        if configured_roots and l3_roots and configured_roots != l3_roots:
            results.append(
                CheckResult(
                    name="l3_roots",
                    status="FAIL",
                    details="manifest L3 roots do not match memory config",
                    path=str(memory_config_path),
                )
            )
        else:
            results.append(
                CheckResult(
                    name="l3_roots",
                    status="PASS",
                    details=f"{len(l3_roots)} configured root(s)",
                    path=str(memory_config_path),
                )
            )

    for root in l3_roots:
        results.append(check_directory(f"l3_root:{root}", root))

    results.append(check_readable_file("codex_config", codex_config_path))
    if codex_config_path.exists():
        config_text = read_text(codex_config_path)
        env = parse_codex_env(config_text)
        for key, expected_value in expected_env.items():
            actual = env.get(key)
            if actual != expected_value:
                results.append(
                    CheckResult(
                        name=f"codex_env:{key}",
                        status="FAIL",
                        details=f"expected {expected_value!r}, got {actual!r}",
                        path=str(codex_config_path),
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=f"codex_env:{key}",
                        status="PASS",
                        details="environment variable present",
                        path=str(codex_config_path),
                    )
                )

        for skill in curated_skills:
            skill_name = skill["name"]
            link_path = normalize_path(str(skill["codex_link"]))
            target_path = normalize_path(str(skill["target"]))
            if not link_path.exists():
                results.append(
                    CheckResult(
                        name=f"codex_skill:{skill_name}",
                        status="FAIL",
                        details="missing bridge link",
                        path=str(link_path),
                    )
                )
                continue
            if not link_path.is_symlink():
                results.append(
                    CheckResult(
                        name=f"codex_skill:{skill_name}",
                        status="FAIL",
                        details="bridge entry is not a symlink",
                        path=str(link_path),
                    )
                )
                continue
            if link_path.resolve() != target_path.resolve():
                results.append(
                    CheckResult(
                        name=f"codex_skill:{skill_name}",
                        status="FAIL",
                        details=f"symlink target mismatch (expected {target_path}, got {link_path.resolve()})",
                        path=str(link_path),
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name=f"codex_skill:{skill_name}",
                        status="PASS",
                        details="bridge symlink resolves correctly",
                        path=str(link_path),
                    )
                )

    results.append(check_json_file("codex_global_state", codex_state_path))
    if codex_state_path.exists():
        state = load_json(codex_state_path)
        persisted = state.get("electron-persisted-atom-state", {})
        wsl_mode = (
            state.get("runCodexInWindowsSubsystemForLinux") is True
            or persisted.get("runCodexInWindowsSubsystemForLinux") is True
        )
        if wsl_mode:
            results.append(
                CheckResult(
                    name="codex_wsl_mode",
                    status="PASS",
                    details="Windows Codex is configured to run in WSL mode",
                    path=str(codex_state_path),
                )
            )
        else:
            results.append(
                CheckResult(
                    name="codex_wsl_mode",
                    status="FAIL",
                    details="runCodexInWindowsSubsystemForLinux is not true",
                    path=str(codex_state_path),
                )
            )

    results.append(check_directory("codex_skill_root", codex_skill_root))
    results.append(check_directory("agents_skill_root", agents_skill_root))

    results.append(check_directory("openclaw_shared_link_parent", shared_link.parent))
    if not shared_link.exists():
        results.append(
            CheckResult(
                name="openclaw_shared_link",
                status="FAIL",
                details="missing shared skill link",
                path=str(shared_link),
            )
        )
    elif not shared_link.is_symlink():
        results.append(
            CheckResult(
                name="openclaw_shared_link",
                status="FAIL",
                details="shared skill link is not a symlink",
                path=str(shared_link),
            )
        )
    elif shared_link.resolve() != shared_target.resolve():
        results.append(
            CheckResult(
                name="openclaw_shared_link",
                status="FAIL",
                details=f"expected {shared_target}, got {shared_link.resolve()}",
                path=str(shared_link),
            )
        )
    else:
        results.append(
            CheckResult(
                name="openclaw_shared_link",
                status="PASS",
                details="shared link resolves correctly",
                path=str(shared_link),
            )
        )

    observability_parent = observability_log_path.parent
    if observability_parent.exists() and observability_parent.is_dir():
        results.append(
            CheckResult(
                name="observability_log_dir",
                status="PASS",
                details="observability log directory exists",
                path=str(observability_parent),
            )
        )
        if observability_log_path.exists():
            results.append(check_readable_file("observability_log", observability_log_path))
        else:
            results.append(
                CheckResult(
                    name="observability_log",
                    status="PASS",
                    details="log file not yet created; directory is available",
                    path=str(observability_log_path),
                )
            )
    else:
        results.append(
            CheckResult(
                name="observability_log_dir",
                status="FAIL",
                details="observability log directory is missing",
                path=str(observability_parent),
            )
        )

    return results


def summarize(results: list[CheckResult]) -> dict[str, int]:
    summary = {"pass": 0, "fail": 0}
    for result in results:
        key = "pass" if result.status == "PASS" else "fail"
        summary[key] += 1
    return summary


def run_doctor(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    results = check_manifest(manifest, manifest_path)
    summary = summarize(results)
    return {
        "schema_version": "1.0",
        "manifest_path": str(manifest_path),
        "summary": summary,
        "checks": [result.as_dict() for result in results],
    }


def print_human(report: dict[str, Any]) -> None:
    checks = report["checks"]
    for item in checks:
        print(f"[{item['status']}] {item['name']}: {item['details']}")
        if "path" in item:
            print(f"  path: {item['path']}")
    summary = report["summary"]
    print(f"Summary: {summary['pass']} passed, {summary['fail']} failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the shared runtime contract")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to the runtime manifest JSON",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output machine-readable JSON")
    parser.add_argument("--version", action="version", version="runtime-doctor 1.0.0")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        report = run_doctor(normalize_path(args.manifest))
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)

    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
