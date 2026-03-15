#!/usr/bin/env python3
"""
find-unused.py — 查找从未执行过的 skill。

比较 skill 目录（有 SKILL.md 的子目录）和执行日志（JSONL），
输出"从未出现在日志中"的 skill 列表。

用法:
  python3 find-unused.py --skills-dir ~/.ai-skills
  python3 find-unused.py --skills-dir ~/.ai-skills --since 2026-01-01
  python3 find-unused.py --skills-dir ~/.ai-skills --log-file /custom/path.jsonl

零外部依赖（纯 Python stdlib）。
"""

import argparse
import json
import os
import sys
from datetime import datetime

# === 常量 ===

DEFAULT_LOG_FILE = os.path.expanduser("~/.ai-skills/.logs/executions.jsonl")
# 排除以 . 开头的系统目录（.system, .logs 等）
EXCLUDED_PREFIXES = (".",)


def discover_skills(skills_dir):
    """遍历 skills_dir，找出所有含 SKILL.md 的子目录。"""
    skills = set()
    if not os.path.isdir(skills_dir):
        print(f"❌ 错误: skills 目录不存在: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    for entry in sorted(os.listdir(skills_dir)):
        # 排除系统目录
        if any(entry.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        entry_path = os.path.join(skills_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        # 检查是否有 SKILL.md
        skill_md = os.path.join(entry_path, "SKILL.md")
        if os.path.isfile(skill_md):
            skills.add(entry)
        # 如果是符号链接指向的目录且含 SKILL.md，也算
        elif os.path.islink(entry_path):
            real_path = os.path.realpath(entry_path)
            if os.path.isdir(real_path) and os.path.isfile(
                os.path.join(real_path, "SKILL.md")
            ):
                skills.add(entry)

    return skills


def parse_log_skills(log_file, since=None):
    """从 JSONL 日志中提取所有出现过的 skill_name 集合。"""
    used_skills = set()
    error_lines = 0

    if not os.path.isfile(log_file):
        return used_skills, error_lines

    with open(log_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                error_lines += 1
                continue

            # --since 过滤
            if since and "timestamp" in entry:
                try:
                    entry_time = datetime.fromisoformat(
                        entry["timestamp"].replace("Z", "+00:00")
                    )
                    since_time = datetime.fromisoformat(since + "T00:00:00+00:00")
                    if entry_time < since_time:
                        continue
                except (ValueError, TypeError):
                    pass  # 时间解析失败，不做过滤

            skill_name = entry.get("skill_name")
            if skill_name:
                used_skills.add(skill_name)

    return used_skills, error_lines


def main():
    parser = argparse.ArgumentParser(
        description="查找从未执行过的 skill。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s --skills-dir ~/.ai-skills
  %(prog)s --skills-dir ~/.ai-skills --since 2026-01-01
""",
    )

    parser.add_argument(
        "--skills-dir",
        default=os.path.expanduser("~/.ai-skills"),
        help="skill 仓库目录（默认: ~/.ai-skills）",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"日志文件路径（默认: {DEFAULT_LOG_FILE}）",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="只考虑此日期之后的日志（格式 YYYY-MM-DD）",
    )

    args = parser.parse_args()

    # 1. 发现所有 skill
    all_skills = discover_skills(args.skills_dir)

    if not all_skills:
        print("⚠️  未发现任何含 SKILL.md 的子目录。", file=sys.stderr)
        sys.exit(0)

    # 2. 解析日志
    if not os.path.isfile(args.log_file):
        print(f"⚠️  日志文件不存在: {args.log_file}", file=sys.stderr)
        print("   尚无执行日志，所有 skill 均视为「未使用」。\n", file=sys.stderr)
        used_skills = set()
        error_lines = 0
    else:
        used_skills, error_lines = parse_log_skills(args.log_file, args.since)

    # 3. 计算差集
    unused_skills = sorted(all_skills - used_skills)

    # 4. 输出
    since_label = f"（自 {args.since} 起）" if args.since else "（全量日志）"
    print(f"# 未使用 Skill 报告 {since_label}")
    print()
    print(f"- 已知 skill 总数: {len(all_skills)}")
    print(f"- 已执行 skill 数: {len(used_skills)}")
    print(f"- 未使用 skill 数: **{len(unused_skills)}**")
    print()

    if unused_skills:
        print("| # | Skill | 路径 |")
        print("|---|-------|------|")
        for i, skill in enumerate(unused_skills, 1):
            skill_path = os.path.join(args.skills_dir, skill)
            print(f"| {i} | {skill} | `{skill_path}` |")
    else:
        print("✅ 所有 skill 均有执行记录。")

    if error_lines > 0:
        print(f"\n⚠️  日志中有 {error_lines} 行格式错误，已跳过。")

    print()


if __name__ == "__main__":
    main()
