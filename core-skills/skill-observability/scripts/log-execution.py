#!/usr/bin/env python3
"""
log-execution.py — 记录一次 skill 执行到 JSONL 日志。

用法:
  python3 log-execution.py --skill translate --agent gemini --status success
  python3 log-execution.py --skill translate --agent gemini --status success --dry-run
  python3 log-execution.py --skill translate --agent gemini --status success --input-fields file,to,mode
  python3 log-execution.py --skill translate --agent gemini --status failure --notes "文件不存在"

零外部依赖（纯 Python stdlib）。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# === 常量 ===

SCHEMA_VERSION = "1.0"
DEFAULT_LOG_DIR = os.path.expanduser("~/.ai-skills/.logs")
DEFAULT_LOG_FILE = os.path.join(DEFAULT_LOG_DIR, "executions.jsonl")
VALID_STATUSES = {"success", "failure", "partial"}
VALID_AGENTS = {"gemini", "claude", "codex", "openclaw", "unknown"}


def ensure_log_dir(log_file):
    """首次运行自动创建日志目录。"""
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, mode=0o700, exist_ok=True)


def build_log_entry(args):
    """构建一条日志记录（Python dict）。"""
    entry = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "skill_name": args.skill,
        "agent": args.agent,
        "status": args.status,
        "duration_seconds": args.duration,
        "input_fields": args.input_fields.split(",") if args.input_fields else None,
        "output_file": args.output_file,
        "notes": args.notes,
    }
    return entry


def write_log_entry(entry, log_file):
    """追加一条 JSON 行到日志文件。"""
    ensure_log_dir(log_file)
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    # 设置文件权限为 600（仅所有者可读写）
    try:
        os.chmod(log_file, 0o600)
    except OSError:
        pass  # Windows 等环境可能不支持 chmod


def main():
    parser = argparse.ArgumentParser(
        description="记录一次 skill 执行到 JSONL 日志。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s --skill translate --agent gemini --status success
  %(prog)s --skill translate --agent gemini --status success --dry-run
  %(prog)s --skill skill-lint --agent claude --status failure --notes "目录不存在"
  %(prog)s --skill memory-search --agent gemini --status success --duration 3.5
""",
    )

    # 必填参数
    parser.add_argument(
        "--skill", required=True, help="执行的 skill 名称（目录名）"
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=sorted(VALID_AGENTS),
        help="执行 Agent 标识",
    )
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_STATUSES),
        help="执行状态",
    )

    # 可选参数
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="执行耗时（秒）",
    )
    parser.add_argument(
        "--input-fields",
        default=None,
        help="输入字段名列表，逗号分隔（如 file,to,mode）。不记录值，防止凭据泄露",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="输出文件路径",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="备注（如失败原因）",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"日志文件路径（默认: {DEFAULT_LOG_FILE}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 JSON 到 stdout，不写文件",
    )

    args = parser.parse_args()

    # 构建日志条目
    entry = build_log_entry(args)

    if args.dry_run:
        # Dry-run：打印到 stdout
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        print("\n[dry-run] 未写入文件。", file=sys.stderr)
    else:
        # 写入日志文件
        write_log_entry(entry, args.log_file)
        print(
            f"✅ 已记录: {entry['skill_name']} ({entry['status']}) → {args.log_file}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
