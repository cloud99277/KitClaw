#!/usr/bin/env python3
"""
save_note.py — Save a distilled conversation note into the configured L3 knowledge base.

Preferred mode:
  python3 save_note.py --json payload.json --print-json

Payload:
  {
    "title": "...",
    "content": "...",
    "base_dir": "..."   # optional
  }
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "1.0.0"
BASE_DIR_ENV = "CONVERSATION_DISTILLER_BASE_DIR"
KNOWLEDGE_ROOT_ENV = "CONVERSATION_DISTILLER_KNOWLEDGE_ROOT"
DB_PATH_ENV = "CONVERSATION_DISTILLER_DB_PATH"
AUTO_INGEST_ENV = "CONVERSATION_DISTILLER_AUTO_INGEST"
INDEXER_PYTHON_ENV = "CONVERSATION_DISTILLER_INDEXER_PYTHON"
DEFAULT_NOTES_SUBDIR = Path("40_Agent_Notes") / "distilled-conversations"
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
FRONTMATTER_SCRIPT = REPO_ROOT / "core-skills" / "memory-manager" / "scripts" / "ensure-knowledge-frontmatter.py"
INDEXER_SCRIPT = REPO_ROOT / "rag-engine" / "knowledge_index.py"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def windows_to_wsl(path: str) -> str:
    """Convert Windows drive paths into WSL paths."""
    normalized = (path or "").replace("\\", "/")
    match = re.match(r"^([A-Za-z]):(.*)", normalized)
    if not match:
        return normalized
    drive = match.group(1).lower()
    rest = match.group(2).lstrip("/")
    return f"/mnt/{drive}/{rest}"


def normalize_path(path: str) -> str:
    return str(Path(windows_to_wsl(path)).expanduser())


def default_knowledge_root() -> str:
    return str(Path.home() / "knowledge-base")


def default_db_path() -> str:
    return str(Path.home() / ".lancedb" / "knowledge")


def memory_config_path() -> Path:
    return Path.home() / ".ai-memory" / "config.json"


def load_l3_paths() -> list[str]:
    config_path = memory_config_path()
    if not config_path.exists():
        return []
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    paths = config.get("l3_paths", [])
    if not isinstance(paths, list):
        return []
    normalized: list[str] = []
    for path in paths:
        if isinstance(path, str) and path.strip():
            normalized.append(normalize_path(path))
    return normalized


def resolve_knowledge_root(note_path: str | None = None) -> str:
    env_root = os.environ.get(KNOWLEDGE_ROOT_ENV, "").strip()
    if env_root:
        return normalize_path(env_root)

    l3_paths = load_l3_paths()
    if note_path:
        note = Path(note_path).expanduser().resolve()
        for root in l3_paths:
            root_path = Path(root).expanduser().resolve()
            try:
                note.relative_to(root_path)
                return str(root_path)
            except ValueError:
                continue

    if l3_paths:
        return l3_paths[0]
    return default_knowledge_root()


def resolve_base_dir(raw_base_dir: str) -> str:
    if raw_base_dir and raw_base_dir.strip():
        return normalize_path(raw_base_dir)

    env_base_dir = os.environ.get(BASE_DIR_ENV, "").strip()
    if env_base_dir:
        return normalize_path(env_base_dir)

    return str(Path(resolve_knowledge_root()) / DEFAULT_NOTES_SUBDIR)


def resolve_db_path() -> str:
    raw = os.environ.get(DB_PATH_ENV, "").strip() or default_db_path()
    return normalize_path(raw)


def resolve_indexer_python() -> str | None:
    candidates: list[Path] = []
    if os.environ.get(INDEXER_PYTHON_ENV, "").strip():
        candidates.append(Path(normalize_path(os.environ[INDEXER_PYTHON_ENV])))
    candidates.extend(
        [
            REPO_ROOT / "rag-engine" / ".venv" / "bin" / "python3",
            REPO_ROOT / ".venv" / "bin" / "python3",
            Path(sys.executable),
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def auto_ingest_enabled() -> bool:
    value = os.environ.get(AUTO_INGEST_ENV, "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def make_dirs(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r'[/*?:"<>|]', "", value or "").strip()
    cleaned = cleaned.rstrip(". ")
    if not cleaned:
        cleaned = "unnamed_note"
    if cleaned.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


def atomic_write(filepath: str, content: str) -> None:
    directory = os.path.dirname(filepath) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".tmp_note_", suffix=".md", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, filepath)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def build_target_dir(base_dir: str, clean_title: str) -> str:
    match = re.match(r"^\[(.+?)\]", clean_title)
    if not match:
        return base_dir
    category = sanitize_filename(match.group(1)).lower()
    return os.path.join(base_dir, category)


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)


def maybe_auto_ingest(filepath: str) -> dict[str, object]:
    if not auto_ingest_enabled():
        return {"enabled": False, "ran": False}

    knowledge_root = Path(resolve_knowledge_root(filepath)).expanduser()
    note_path = Path(filepath).expanduser()

    try:
        note_path.resolve().relative_to(knowledge_root.resolve())
    except ValueError:
        return {
            "enabled": True,
            "ran": False,
            "reason": "outside_knowledge_root",
            "knowledge_root": str(knowledge_root),
        }

    indexer_python = resolve_indexer_python()
    missing: list[str] = []
    if not FRONTMATTER_SCRIPT.exists():
        missing.append(str(FRONTMATTER_SCRIPT))
    if not INDEXER_SCRIPT.exists():
        missing.append(str(INDEXER_SCRIPT))
    if not indexer_python:
        missing.append("indexer_python")
    if missing:
        return {
            "enabled": True,
            "ran": False,
            "reason": "missing_dependency",
            "missing": missing,
        }

    frontmatter_cmd = [
        sys.executable,
        str(FRONTMATTER_SCRIPT),
        "--root",
        str(knowledge_root),
        "--apply",
    ]
    frontmatter_result = run_command(frontmatter_cmd)
    if frontmatter_result.returncode != 0:
        return {
            "enabled": True,
            "ran": False,
            "reason": "frontmatter_failed",
            "stdout": frontmatter_result.stdout.strip(),
            "stderr": frontmatter_result.stderr.strip(),
        }

    env = os.environ.copy()
    env["PRODUCTION"] = "true"
    index_cmd = [
        indexer_python,
        str(INDEXER_SCRIPT),
        "--update",
        str(knowledge_root),
        "--db-path",
        resolve_db_path(),
    ]
    index_result = run_command(index_cmd, env=env)
    if index_result.returncode != 0:
        return {
            "enabled": True,
            "ran": False,
            "reason": "index_failed",
            "stdout": index_result.stdout.strip(),
            "stderr": index_result.stderr.strip(),
        }

    return {
        "enabled": True,
        "ran": True,
        "knowledge_root": str(knowledge_root),
        "db_path": resolve_db_path(),
    }


def save(title: str, content: str, raw_base_dir: str) -> tuple[str, str, dict[str, object]]:
    if not isinstance(title, str):
        raise ValueError("'title' must be a string.")
    if not isinstance(content, str):
        raise ValueError("'content' must be a string.")

    base_dir = resolve_base_dir(raw_base_dir)
    make_dirs(base_dir)

    clean_title = sanitize_filename(title)
    generated_at = dt.datetime.now().isoformat(timespec="seconds")
    filename = f"{clean_title}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    target_dir = build_target_dir(base_dir, clean_title)
    make_dirs(target_dir)

    filepath = os.path.join(target_dir, filename)
    body = content.rstrip() + "\n" if content.strip() else ""
    document = f"# {title}\n\n> Generated at: {generated_at}\n\n---\n\n{body}"
    atomic_write(filepath, document)
    ingest = maybe_auto_ingest(filepath)
    return filepath, generated_at, ingest


def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save a distilled conversation note to Markdown.")
    parser.add_argument("--json", dest="json_path", help="Path to JSON payload file")
    parser.add_argument("--print-json", action="store_true", help="Print machine-readable JSON result")
    parser.add_argument("--version", action="version", version=f"save_note {VERSION}")
    parser.add_argument("positional", nargs="*", help="Legacy positional args: <title> <content> [base_dir]")
    return parser.parse_args()


def main() -> int:
    args = parse_cli()

    if args.json_path:
        payload_path = Path(args.json_path)
        if not payload_path.exists():
            print(f"Error: JSON file not found: {payload_path}")
            return 1
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Error: Invalid JSON payload ({exc}).")
            return 1
        if not isinstance(payload, dict):
            print("Error: JSON payload must be an object.")
            return 1
        title = payload.get("title", "untitled")
        content = payload.get("content", "")
        raw_base_dir = payload.get("base_dir", "")
    else:
        if not args.positional:
            print(__doc__)
            return 1
        print(
            "Warning: positional mode is legacy and may break with shell escaping/backticks. Prefer --json mode.",
            file=sys.stderr,
        )
        if len(args.positional) < 2:
            print("Error: Requires at least <title> and <content> arguments.")
            return 1
        title = args.positional[0]
        content = args.positional[1].replace("\\n", "\n")
        raw_base_dir = args.positional[2] if len(args.positional) > 2 else ""

    try:
        filepath, generated_at, ingest = save(title, content, raw_base_dir)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    if args.print_json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "path": filepath,
                    "generated_at": generated_at,
                    "ingest": ingest,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"OK: {filepath}")
        if ingest.get("enabled") and not ingest.get("ran"):
            print(f"Warning: knowledge ingest not completed ({ingest.get('reason')})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
