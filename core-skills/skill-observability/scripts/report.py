#!/usr/bin/env python3
"""
report.py — 生成 skill 执行统计报告。

从 JSONL 日志中聚合统计，输出 Markdown 格式报告。

用法:
  python3 report.py
  python3 report.py --since 2026-03-01 --until 2026-03-31
  python3 report.py --log-file /custom/path.jsonl
  python3 report.py --output report.md

零外部依赖（纯 Python stdlib）。
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

# === 常量 ===

DEFAULT_LOG_FILE = os.path.expanduser("~/.ai-skills/.logs/executions.jsonl")


def parse_logs(log_file, since=None, until=None):
    """解析 JSONL 日志，返回条目列表和错误行数。"""
    entries = []
    error_lines = 0

    if not os.path.isfile(log_file):
        return entries, error_lines

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

            # 时间窗过滤
            if (since or until) and "timestamp" in entry:
                try:
                    entry_time = datetime.fromisoformat(
                        entry["timestamp"].replace("Z", "+00:00")
                    )
                    if since:
                        since_time = datetime.fromisoformat(since + "T00:00:00+00:00")
                        if entry_time < since_time:
                            continue
                    if until:
                        until_time = datetime.fromisoformat(
                            until + "T23:59:59+00:00"
                        )
                        if entry_time > until_time:
                            continue
                except (ValueError, TypeError):
                    pass  # 时间解析失败，不做过滤

            entries.append(entry)

    return entries, error_lines


def generate_report(entries, error_lines, since=None, until=None):
    """根据日志条目列表生成 Markdown 报告。"""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 计算时间范围标签
    if since and until:
        range_label = f"{since} ~ {until}"
    elif since:
        range_label = f"{since} ~ 至今"
    elif until:
        range_label = f"开始 ~ {until}"
    else:
        range_label = "全量"

    lines = []
    lines.append("# Skill Observability Report")
    lines.append("")
    lines.append(f"- **生成时间**: {now_str}")
    lines.append(f"- **日志范围**: {range_label}")
    lines.append("")

    if not entries:
        lines.append("⚠️  无执行记录（日志为空或不在指定时间范围）。")
        if error_lines > 0:
            lines.append(f"\n⚠️  日志中有 {error_lines} 行格式错误，已跳过。")
        return "\n".join(lines)

    # === 总览 ===
    total = len(entries)
    success_count = sum(1 for e in entries if e.get("status") == "success")
    failure_count = sum(1 for e in entries if e.get("status") == "failure")
    partial_count = sum(1 for e in entries if e.get("status") == "partial")
    success_rate = (success_count / total * 100) if total > 0 else 0

    skill_names = set(e.get("skill_name", "unknown") for e in entries)
    agent_names = set(e.get("agent", "unknown") for e in entries)

    lines.append("## 总览")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|----|")
    lines.append(f"| 总执行次数 | {total} |")
    lines.append(f"| 成功次数 | {success_count} ({success_rate:.1f}%) |")
    lines.append(f"| 失败次数 | {failure_count} |")
    lines.append(f"| 部分成功次数 | {partial_count} |")
    lines.append(f"| 涉及 skill 数 | {len(skill_names)} |")
    lines.append(f"| 涉及 agent 数 | {len(agent_names)} |")
    lines.append("")

    # === Top 10 高频 Skill ===
    skill_counter = Counter(e.get("skill_name", "unknown") for e in entries)
    skill_success = Counter(
        e.get("skill_name", "unknown")
        for e in entries
        if e.get("status") == "success"
    )

    lines.append("## Top 10 高频 Skill")
    lines.append("")
    lines.append("| # | Skill | 执行次数 | 成功率 |")
    lines.append("|---|-------|---------|--------|")
    for rank, (skill, count) in enumerate(skill_counter.most_common(10), 1):
        s_count = skill_success.get(skill, 0)
        s_rate = (s_count / count * 100) if count > 0 else 0
        lines.append(f"| {rank} | {skill} | {count} | {s_rate:.0f}% |")
    lines.append("")

    # === 失败率 Top 5 ===
    skill_failure = Counter(
        e.get("skill_name", "unknown")
        for e in entries
        if e.get("status") == "failure"
    )

    if skill_failure:
        lines.append("## 失败率 Top 5 Skill")
        lines.append("")
        lines.append("| # | Skill | 失败次数 | 失败率 |")
        lines.append("|---|-------|---------|--------|")
        # 按失败率排序（需要至少有 1 次失败）
        failure_rates = []
        for skill, f_count in skill_failure.items():
            total_count = skill_counter[skill]
            f_rate = (f_count / total_count * 100) if total_count > 0 else 0
            failure_rates.append((skill, f_count, f_rate))
        failure_rates.sort(key=lambda x: x[2], reverse=True)

        for rank, (skill, f_count, f_rate) in enumerate(failure_rates[:5], 1):
            lines.append(f"| {rank} | {skill} | {f_count} | {f_rate:.0f}% |")
        lines.append("")

    # === Agent 使用分布 ===
    agent_counter = Counter(e.get("agent", "unknown") for e in entries)

    lines.append("## Agent 使用分布")
    lines.append("")
    lines.append("| Agent | 执行次数 | 占比 |")
    lines.append("|-------|---------|------|")
    for agent, count in agent_counter.most_common():
        pct = (count / total * 100) if total > 0 else 0
        lines.append(f"| {agent} | {count} | {pct:.0f}% |")
    lines.append("")

    # === 耗时统计（如果有 duration_seconds 数据）===
    durations = [
        e["duration_seconds"]
        for e in entries
        if e.get("duration_seconds") is not None
    ]
    if durations:
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)

        lines.append("## 耗时统计")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 有耗时记录的执行数 | {len(durations)} |")
        lines.append(f"| 平均耗时 | {avg_duration:.1f}s |")
        lines.append(f"| 最长耗时 | {max_duration:.1f}s |")
        lines.append(f"| 最短耗时 | {min_duration:.1f}s |")
        lines.append("")

    # === 错误行提示 ===
    if error_lines > 0:
        lines.append(f"⚠️  日志中有 {error_lines} 行格式错误，已跳过。")
        lines.append("")

    # 提示
    lines.append("---")
    lines.append("")
    lines.append(
        "> 提示: 运行 `find-unused.py --skills-dir ~/.ai-skills` 查看未使用 skill 列表。"
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="生成 skill 执行统计报告。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s
  %(prog)s --since 2026-03-01 --until 2026-03-31
  %(prog)s --output report.md
""",
    )

    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"日志文件路径（默认: {DEFAULT_LOG_FILE}）",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="起始日期过滤（格式 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="结束日期过滤（格式 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出到文件（默认输出到 stdout）",
    )

    args = parser.parse_args()

    # 检查日志文件
    if not os.path.isfile(args.log_file):
        print(f"⚠️  日志文件不存在: {args.log_file}", file=sys.stderr)
        print("   尚无执行日志，请先运行 log-execution.py 记录数据。", file=sys.stderr)
        # 仍然生成空报告
        report = generate_report([], 0, args.since, args.until)
    else:
        entries, error_lines = parse_logs(args.log_file, args.since, args.until)
        report = generate_report(entries, error_lines, args.since, args.until)

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 报告已写入: {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
