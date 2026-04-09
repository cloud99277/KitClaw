#!/usr/bin/env python3
"""Sync the curated Windows Codex Desktop bridge from the runtime manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_PATH = Path.home() / ".ai-skills" / ".system" / "runtime-manifest.json"


@dataclass
class BridgeAction:
    skill: str
    codex_link: str
    target: str
    action: str
    details: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "codex_link": self.codex_link,
            "target": self.target,
            "action": self.action,
            "details": self.details,
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object")
    return data


def normalize(path_value: str) -> Path:
    return Path(path_value).expanduser()


def ensure_parent(path: Path, apply_changes: bool) -> None:
    if apply_changes:
        path.parent.mkdir(parents=True, exist_ok=True)


def planned_link_action(link_path: Path, target_path: Path) -> tuple[str, str]:
    if not link_path.exists():
        return "create", "missing link"
    if not link_path.is_symlink():
        return "error", "path exists but is not a symlink"
    if link_path.resolve() != target_path.resolve():
        return "update", f"points to {link_path.resolve()}"
    return "noop", "already correct"


def sync_bridge(manifest_path: Path, apply_changes: bool) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    bridge = manifest.get("bridge", {})
    codex_skill_root = normalize(str(manifest.get("windows", {}).get("codex_skill_root", "")))
    curated = bridge.get("curated_codex_skills", [])

    actions: list[BridgeAction] = []
    errors: list[dict[str, Any]] = []

    if not codex_skill_root.exists():
        errors.append(
            {
                "skill": "bridge-root",
                "codex_link": str(codex_skill_root),
                "target": "",
                "action": "error",
                "details": "Codex skill root is missing",
            }
        )
        return {
            "schema_version": "1.0",
            "manifest_path": str(manifest_path),
            "apply": apply_changes,
            "status": "error",
            "errors": errors,
            "actions": [],
            "summary": {"created": 0, "updated": 0, "noop": 0, "error": 1},
        }

    for item in curated:
        skill = item["name"]
        link_path = normalize(str(item["codex_link"]))
        target_path = normalize(str(item["target"]))

        if not target_path.exists():
            errors.append(
                {
                    "skill": skill,
                    "codex_link": str(link_path),
                    "target": str(target_path),
                    "action": "error",
                    "details": "target path does not exist",
                }
            )
            continue

        action, details = planned_link_action(link_path, target_path)
        if action == "error":
            errors.append(
                {
                    "skill": skill,
                    "codex_link": str(link_path),
                    "target": str(target_path),
                    "action": action,
                    "details": details,
                }
            )
            continue

        if apply_changes:
            ensure_parent(link_path, True)
            if action in {"create", "update"}:
                if link_path.is_symlink():
                    link_path.unlink()
                elif link_path.exists():
                    errors.append(
                        {
                            "skill": skill,
                            "codex_link": str(link_path),
                            "target": str(target_path),
                            "action": "error",
                            "details": "refusing to replace existing non-symlink path",
                        }
                    )
                    continue
                link_path.symlink_to(target_path)

        actions.append(
            BridgeAction(
                skill=skill,
                codex_link=str(link_path),
                target=str(target_path),
                action=action,
                details=details,
            )
        )

    summary = {
        "created": sum(1 for item in actions if item.action == "create"),
        "updated": sum(1 for item in actions if item.action == "update"),
        "noop": sum(1 for item in actions if item.action == "noop"),
        "error": len(errors),
    }
    status = "ok" if not errors else "error"
    return {
        "schema_version": "1.0",
        "manifest_path": str(manifest_path),
        "apply": apply_changes,
        "status": status,
        "errors": errors,
        "actions": [item.as_dict() for item in actions],
        "summary": summary,
    }


def print_human(report: dict[str, Any]) -> None:
    mode = "APPLY" if report["apply"] else "DRY-RUN"
    print(f"{mode} {report['status'].upper()} — {report['manifest_path']}")
    for action in report["actions"]:
        print(
            f"[{action['action'].upper()}] {action['skill']}: {action['codex_link']} -> {action['target']} ({action['details']})"
        )
    for error in report["errors"]:
        print(
            f"[ERROR] {error['skill']}: {error['codex_link']} -> {error['target']} ({error['details']})",
            file=sys.stderr,
        )
    summary = report["summary"]
    print(
        f"Summary: created={summary['created']} updated={summary['updated']} noop={summary['noop']} error={summary['error']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync curated Windows Codex bridge symlinks")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to the runtime manifest JSON",
    )
    parser.add_argument("--apply", action="store_true", help="Apply symlink changes")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output machine-readable JSON")
    parser.add_argument("--version", action="version", version="runtime-bridge-sync 1.0.0")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        report = sync_bridge(normalize(args.manifest), apply_changes=args.apply)
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

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
