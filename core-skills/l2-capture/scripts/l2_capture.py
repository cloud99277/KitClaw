#!/usr/bin/env python3
"""
l2_capture.py - Thin L2 write helper on top of memory-manager

Features:
- Parse [decision]/[action]/[learning] candidate lines
- Dry-run by default
- Duplicate detection against ~/.ai-memory/whiteboard.json
- Serial writes via memory-update.py
- Optional JSON output for other agents/tools
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


VALID_TYPES = ("decision", "action", "learning")
MARKER_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\[(decision|action|learning)\]|(decision|action|learning)\s*[:：])\s*(.+?)\s*$",
    re.IGNORECASE,
)
ROLE_PREFIX_RE = re.compile(r"^\s*(?:用户|User|Agent|助手|Assistant|系统|System|我|你)[:：]\s*")
AUTO_KEYWORDS = {
    "decision": [
        "决定",
        "选择",
        "采用",
        "改为",
        "改成",
        "统一",
        "为准",
        "优先",
        "保留",
        "主路径",
        "source of truth",
    ],
    "action": [
        "需要",
        "后续",
        "待",
        "todo",
        "计划",
        "补",
        "增加",
        "接入",
        "评估",
        "清理",
        "同步",
        "迁移",
        "修复",
        "编写",
        "建立",
    ],
    "learning": [
        "发现",
        "实测",
        "已验证",
        "说明",
        "适合",
        "不适合",
        "更适合",
        "会导致",
        "证明",
        "表明",
        "踩坑",
        "经验",
        "规律",
    ],
}

DEFAULT_MEMORY_UPDATE = Path.home() / ".ai-skills" / "memory-manager" / "scripts" / "memory-update.py"
DEFAULT_WHITEBOARD = Path.home() / ".ai-memory" / "whiteboard.json"
DEFAULT_LOCK = Path.home() / ".ai-memory" / "whiteboard.lock"


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def split_segments(text: str) -> list[str]:
    segments: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_text(ROLE_PREFIX_RE.sub("", raw_line.strip()))
        if not line:
            continue
        parts = re.split(r"[。！？!?；;]\s*", line)
        for part in parts:
            normalized = normalize_text(part)
            if 10 <= len(normalized) <= 160:
                segments.append(normalized)
    return segments


def classify_segment(segment: str) -> tuple[str, int, list[str]] | None:
    lowered = segment.lower()
    best_type = None
    best_score = 0
    best_signals: list[str] = []

    for entry_type, keywords in AUTO_KEYWORDS.items():
        score = 0
        signals: list[str] = []
        for keyword in keywords:
            if keyword in lowered:
                score += 1
                signals.append(keyword)
        if entry_type == "decision" and segment.startswith(("决定", "统一", "以后", "改为", "改成")):
            score += 2
            signals.append("prefix")
        if entry_type == "action" and segment.startswith(("后续", "需要", "待", "下一步", "补")):
            score += 2
            signals.append("prefix")
        if entry_type == "learning" and segment.startswith(("发现", "实测", "已验证", "说明")):
            score += 2
            signals.append("prefix")
        if "?" in segment or "？" in segment:
            score -= 1
        if score > best_score:
            best_type = entry_type
            best_score = score
            best_signals = signals

    if best_type and best_score > 0:
        return best_type, best_score, best_signals
    return None


def auto_extract_candidates(text: str, max_entries: int) -> list[dict]:
    ranked: list[dict] = []
    for segment in split_segments(text):
        classified = classify_segment(segment)
        if not classified:
            continue
        entry_type, score, signals = classified
        ranked.append(
            {
                "type": entry_type,
                "content": segment,
                "source_mode": "auto",
                "signals": signals,
                "_score": score,
            }
        )

    ranked.sort(key=lambda item: (-item["_score"], len(item["content"])))

    deduped: list[dict] = []
    seen_contents: set[str] = set()
    for item in ranked:
        key = item["content"].lower()
        if key in seen_contents:
            continue
        seen_contents.add(key)
        item.pop("_score", None)
        deduped.append(item)
        if len(deduped) >= max_entries:
            break
    return deduped


def parse_candidates(text: str, forced_type: str | None, max_entries: int) -> list[dict]:
    candidates: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = MARKER_RE.match(line)
        if match:
            entry_type = (match.group(1) or match.group(2) or "").lower()
            content = normalize_text(match.group(3) or "")
            if content:
                candidates.append({"type": entry_type, "content": content, "source_mode": "marked", "signals": []})

    if candidates:
        return candidates[:max_entries]

    stripped = normalize_text(text)
    if stripped and forced_type:
        return [{"type": forced_type, "content": stripped, "source_mode": "typed", "signals": []}]

    if not stripped:
        return []

    auto_candidates = auto_extract_candidates(text, max_entries=max_entries)
    if auto_candidates:
        return auto_candidates

    raise ValueError(
        "No L2 candidates found. Use [decision]/[action]/[learning], decision:/action:/learning:, "
        "provide --type for a single entry, or supply text that clearly contains decision/action/learning signals."
    )


def read_whiteboard(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": "1.0", "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to read whiteboard: {exc}") from exc
    if not isinstance(data.get("entries"), list):
        data["entries"] = []
    return data


def similarity(a: str, b: str) -> float:
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / max(len(a_words), len(b_words))


def assess_candidates(
    candidates: list[dict],
    existing_entries: list[dict],
    project: str,
    tags: list[str],
    threshold: float,
    max_entries: int,
    force: bool,
) -> list[dict]:
    assessed: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for candidate in candidates[:max_entries]:
        entry_type = candidate["type"].lower()
        content = normalize_text(candidate["content"])
        item = {
            "type": entry_type,
            "content": content,
            "project": project,
            "tags": tags,
            "source_mode": candidate.get("source_mode", "unknown"),
            "signals": candidate.get("signals", []),
            "status": "ready",
            "reason": "",
            "similar_to": None,
        }

        if entry_type not in VALID_TYPES:
            item["status"] = "skip"
            item["reason"] = f"invalid_type:{entry_type}"
        elif len(content) > 140:
            item["status"] = "skip"
            item["reason"] = "too_long_for_l2"
        else:
            dedupe_key = (entry_type, content.lower())
            if dedupe_key in seen_keys:
                item["status"] = "skip"
                item["reason"] = "duplicate_in_batch"
            else:
                best_match = None
                best_score = 0.0
                for entry in existing_entries:
                    score = similarity(content, entry.get("content", ""))
                    if score > best_score:
                        best_score = score
                        best_match = entry
                if best_match and best_score >= threshold and not force:
                    item["status"] = "skip"
                    item["reason"] = "similar_existing_entry"
                    item["similar_to"] = {
                        "id": best_match.get("id"),
                        "type": best_match.get("type"),
                        "project": best_match.get("project"),
                        "score": round(best_score, 2),
                        "content": best_match.get("content", ""),
                    }
                seen_keys.add(dedupe_key)

        assessed.append(item)

    return assessed


@contextmanager
def file_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def run_memory_update(
    memory_update_script: Path,
    entry: dict,
    project: str,
    tags: list[str],
    force: bool,
) -> dict:
    cmd = [
        sys.executable,
        str(memory_update_script),
        "--from-text",
        entry["content"],
        "--type",
        entry["type"],
        "--project",
        project,
    ]
    if tags:
        cmd.extend(["--tags", ",".join(tags)])
    if force:
        cmd.append("--force")

    result = subprocess.run(cmd, capture_output=True, text=True)
    payload = {
        "type": entry["type"],
        "content": entry["content"],
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    if result.returncode == 0:
        match = re.search(r"id=(\S+)", result.stdout)
        if match:
            payload["id"] = match.group(1)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture structured L2 Whiteboard entries")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-text", help="Inline candidate entries or raw single-entry text")
    source.add_argument("--from-file", help="Read candidate entries or raw text from a file")
    parser.add_argument("--type", choices=VALID_TYPES, help="Entry type for a single unmarked entry")
    parser.add_argument("--project", default="", help="Project name for all resulting entries")
    parser.add_argument("--tags", default="", help="Comma-separated tags applied to all entries")
    parser.add_argument("--max-entries", type=int, default=3, help="Maximum number of entries to process")
    parser.add_argument("--duplicate-threshold", type=float, default=0.8, help="Similarity threshold for duplicate detection")
    parser.add_argument("--apply", action="store_true", help="Write ready entries to the whiteboard")
    parser.add_argument("--dry-run", action="store_true", help="Preview candidates without writing (default)")
    parser.add_argument("--force", action="store_true", help="Write even if similar entries exist")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output JSON")
    parser.add_argument("--whiteboard-path", default=str(DEFAULT_WHITEBOARD), help=argparse.SUPPRESS)
    parser.add_argument("--memory-update-script", default=str(DEFAULT_MEMORY_UPDATE), help=argparse.SUPPRESS)
    parser.add_argument("--lock-path", default=str(DEFAULT_LOCK), help=argparse.SUPPRESS)
    return parser.parse_args()


def load_input(args: argparse.Namespace) -> str:
    if args.from_text is not None:
        return args.from_text
    return Path(args.from_file).read_text(encoding="utf-8")


def print_text_report(report: dict) -> None:
    mode = "apply" if report["apply"] else "dry-run"
    print(f"L2 capture ({mode}) — {len(report['candidates'])} candidate(s)")
    print()
    for index, item in enumerate(report["candidates"], start=1):
        print(f"{index}. [{item['type']}] {item['content']}")
        print(f"   source_mode={item.get('source_mode', 'unknown')} signals={item.get('signals', [])}")
        print(f"   status={item['status']}" + (f" reason={item['reason']}" if item["reason"] else ""))
        if item.get("similar_to"):
            similar = item["similar_to"]
            print(
                f"   similar_to={similar['id']} score={similar['score']} "
                f"project={similar['project']} content={similar['content']}"
            )
    if report["writes"]:
        print()
        print("Write results:")
        for item in report["writes"]:
            line = f"- [{item['type']}] rc={item['returncode']}"
            if item.get("id"):
                line += f" id={item['id']}"
            print(line)
            if item.get("stderr"):
                print(f"  stderr={item['stderr']}")


def main() -> int:
    args = parse_args()
    whiteboard_path = Path(args.whiteboard_path)
    memory_update_script = Path(args.memory_update_script)
    lock_path = Path(args.lock_path)
    tags = [normalize_text(tag) for tag in args.tags.split(",") if normalize_text(tag)]

    try:
        source_text = load_input(args)
        candidates = parse_candidates(source_text, args.type, max_entries=max(1, args.max_entries))
        whiteboard = read_whiteboard(whiteboard_path)
        assessed = assess_candidates(
            candidates=candidates,
            existing_entries=whiteboard.get("entries", []),
            project=args.project,
            tags=tags,
            threshold=args.duplicate_threshold,
            max_entries=max(1, args.max_entries),
            force=args.force,
        )
    except Exception as exc:
        error = {"status": "error", "reason": str(exc)}
        if args.as_json:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"❌ {exc}", file=sys.stderr)
        return 1

    ready = [item for item in assessed if item["status"] == "ready"]
    report = {
        "status": "ok",
        "apply": bool(args.apply),
        "project": args.project,
        "tags": tags,
        "candidates": assessed,
        "writes": [],
    }

    if args.apply and ready:
        with file_lock(lock_path):
            for item in ready:
                write_result = run_memory_update(
                    memory_update_script=memory_update_script,
                    entry=item,
                    project=args.project,
                    tags=tags,
                    force=True,
                )
                report["writes"].append(write_result)
                if write_result["returncode"] == 0 and write_result.get("id"):
                    item["status"] = "written"
                    item["id"] = write_result["id"]
                else:
                    item["status"] = "error"
                    item["reason"] = write_result.get("stderr") or write_result.get("stdout") or "write_failed"

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)

    has_errors = any(item["status"] == "error" for item in assessed)
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
