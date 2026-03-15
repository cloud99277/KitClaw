#!/usr/bin/env python3
"""
Knowledge Auditor — 知识库治理健康度巡检

根据 docs/GOVERNANCE.md（下位法）定义的规则，巡检知识库文档质量。

用法:
  python3 knowledge_auditor.py docs/                    # 巡检 docs 目录
  python3 knowledge_auditor.py docs/ --json              # JSON 输出
  python3 knowledge_auditor.py docs/ --fix-stale         # 自动标记过期文档
  python3 knowledge_auditor.py docs/ src/                # 巡检多个目录

Exit codes:
  0 = 健康度 ≥ 7/10
  1 = 健康度 < 7/10（有严重问题）
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"
SCHEMA_VERSION = "1.0"
STALE_THRESHOLD_DAYS = 90


def parse_frontmatter(content: str) -> dict:
    """
    简单字符串解析 YAML frontmatter（不依赖 PyYAML）。
    解析 --- 包裹区域内的 key: value 对。
    """
    if not content.strip().startswith("---"):
        return {}

    lines = content.split("\n")
    in_frontmatter = False
    fm_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break  # 结束 frontmatter
        if in_frontmatter:
            fm_lines.append(line)

    metadata = {}
    for line in fm_lines:
        # 跳过空行和注释
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 简单 key: value 解析
        match = re.match(r'^(\w[\w\-]*)\s*:\s*(.*)', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            # 去掉引号
            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            metadata[key] = value

    return metadata


def has_h1_heading(content: str) -> bool:
    """检查文档是否有一级标题（# 开头的行）"""
    for line in content.split("\n"):
        if re.match(r'^#\s+\S', line):
            return True
    return False


def get_file_mtime_days(filepath: Path) -> int:
    """获取文件距今的天数"""
    try:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        return (now - mtime).days
    except Exception:
        return 0


def audit_file(filepath: Path) -> dict:
    """
    审计单个 Markdown 文件。
    返回: {"file": str, "issues": [...], "frontmatter": {...}, "days_since_update": int}
    """
    result = {
        "file": str(filepath),
        "issues": [],
        "frontmatter": {},
        "days_since_update": 0,
    }

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        result["issues"].append({
            "check": "read_file",
            "severity": "error",
            "message": f"无法读取文件: {e}",
        })
        return result

    # 解析 frontmatter
    fm = parse_frontmatter(content)
    result["frontmatter"] = fm

    # 距今天数
    days = get_file_mtime_days(filepath)
    result["days_since_update"] = days

    # --- P0 检查 ---

    # frontmatter: title 必须有
    if not fm.get("title"):
        result["issues"].append({
            "check": "frontmatter_title",
            "severity": "error",
            "message": "缺少 frontmatter title",
            "priority": "P0",
        })

    # frontmatter: tags 建议有
    if not fm.get("tags"):
        result["issues"].append({
            "check": "frontmatter_tags",
            "severity": "warning",
            "message": "缺少 frontmatter tags",
            "priority": "P0",
        })

    # frontmatter: scope 建议有
    if not fm.get("scope"):
        result["issues"].append({
            "check": "frontmatter_scope",
            "severity": "warning",
            "message": "缺少 frontmatter scope",
            "priority": "P0",
        })

    # 过期检测
    status = fm.get("status", "active")
    if days > STALE_THRESHOLD_DAYS and status not in ("stale", "archived", "draft"):
        result["issues"].append({
            "check": "stale_detection",
            "severity": "warning",
            "message": f"超过 {STALE_THRESHOLD_DAYS} 天未更新（{days} 天），建议标记为 stale",
            "priority": "P0",
        })

    # expires 检测
    expires = fm.get("expires")
    if expires:
        try:
            exp_date = datetime.strptime(expires, "%Y-%m-%d")
            if exp_date < datetime.now():
                result["issues"].append({
                    "check": "expired",
                    "severity": "error",
                    "message": f"文档已过期（expires: {expires}）",
                    "priority": "P0",
                })
        except ValueError:
            pass  # 格式不对就跳过

    # --- P1 检查 ---

    # 一级标题检测
    if not has_h1_heading(content):
        result["issues"].append({
            "check": "h1_heading",
            "severity": "error",
            "message": "缺少一级标题（# 开头的行）",
            "priority": "P1",
        })

    # 生命周期一致性
    if status == "active" and days > STALE_THRESHOLD_DAYS:
        result["issues"].append({
            "check": "lifecycle_consistency",
            "severity": "warning",
            "message": f"status 为 active 但已 {days} 天未更新，与实际状态不一致",
            "priority": "P1",
        })

    return result


def calculate_health_score(results: list) -> float:
    """
    计算治理健康度评分（满分 10）。
    算法：从 10 分开始，每个 error 扣 1 分，每个 warning 扣 0.3 分。
    最低 0 分。
    """
    total_errors = sum(
        1 for r in results for i in r["issues"] if i["severity"] == "error"
    )
    total_warnings = sum(
        1 for r in results for i in r["issues"] if i["severity"] == "warning"
    )
    total_files = len(results) if results else 1

    # 按文件数归一化
    error_rate = total_errors / total_files
    warning_rate = total_warnings / total_files

    score = 10.0 - (error_rate * 3.0) - (warning_rate * 1.0)
    return max(0.0, min(10.0, round(score, 1)))


def generate_markdown_report(results: list, scan_dirs: list) -> str:
    """生成 Markdown 格式的健康度报告"""
    score = calculate_health_score(results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_files = len(results)

    # 统计 frontmatter 覆盖率
    has_title = sum(1 for r in results if r["frontmatter"].get("title"))
    has_tags = sum(1 for r in results if r["frontmatter"].get("tags"))
    has_scope = sum(1 for r in results if r["frontmatter"].get("scope"))

    title_pct = f"{has_title / total_files * 100:.0f}%" if total_files else "N/A"
    tags_pct = f"{has_tags / total_files * 100:.0f}%" if total_files else "N/A"
    scope_pct = f"{has_scope / total_files * 100:.0f}%" if total_files else "N/A"

    # 过期文档
    stale_files = [
        r for r in results
        if r["days_since_update"] > STALE_THRESHOLD_DAYS
        and r["frontmatter"].get("status", "active") not in ("stale", "archived", "draft")
    ]

    # 质量问题
    all_issues = []
    for r in results:
        for issue in r["issues"]:
            all_issues.append({"file": r["file"], **issue})

    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]

    # 生成报告
    # > v1→v2 变更：自动添加 frontmatter，来源：审查报告 #7
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        f'title: "知识库治理健康度报告 {date_str}"',
        "tags: [audit, governance, health-check]",
        "scope: dev",
        f'date: "{date_str}"',
        "---",
        "",
        "# 知识库治理健康度报告",
        "",
        f"> 巡检日期：{now}",
        f"> 巡检范围：{', '.join(scan_dirs)}",
        f"> 文件总数：{total_files}",
        f"> **健康度评分：{score}/10**",
        "",
        "---",
        "",
        "## frontmatter 覆盖率",
        "",
        "| 字段 | 覆盖率 | 覆盖数 / 总数 |",
        "|------|--------|-------------|",
        f"| title | {title_pct} | {has_title} / {total_files} |",
        f"| tags | {tags_pct} | {has_tags} / {total_files} |",
        f"| scope | {scope_pct} | {has_scope} / {total_files} |",
        "",
    ]

    if stale_files:
        lines.extend([
            "## 过期文档（> 90 天未更新）",
            "",
            "| 文件 | 天数 | 当前 status | 建议 |",
            "|------|------|-----------|------|",
        ])
        for r in stale_files:
            status = r["frontmatter"].get("status", "active")
            lines.append(
                f"| {r['file']} | {r['days_since_update']} | {status} | 标记为 stale |"
            )
        lines.append("")

    if errors or warnings:
        lines.extend([
            "## 质量问题",
            "",
            "| 文件 | 检查项 | 严重度 | 问题 |",
            "|------|--------|--------|------|",
        ])
        for issue in sorted(all_issues, key=lambda x: (0 if x["severity"] == "error" else 1)):
            icon = "❌" if issue["severity"] == "error" else "⚠️"
            lines.append(
                f"| {issue['file']} | {issue['check']} | {icon} {issue['severity']} | {issue['message']} |"
            )
        lines.append("")

    lines.extend([
        "---",
        "",
        f"> 统计：{len(errors)} error(s), {len(warnings)} warning(s), {total_files} file(s)",
    ])

    return "\n".join(lines)


def fix_stale_files(results: list) -> int:
    """自动在过期文档的 frontmatter 中添加 status: stale"""
    fixed = 0
    for r in results:
        if (r["days_since_update"] > STALE_THRESHOLD_DAYS
                and r["frontmatter"].get("status", "active") not in ("stale", "archived", "draft")):
            filepath = Path(r["file"])
            try:
                content = filepath.read_text(encoding="utf-8")
                # 在 frontmatter 的闭合 --- 前插入 status: stale
                if "\nstatus:" not in content.split("---")[1] if "---" in content else True:
                    content = content.replace(
                        "\n---\n",
                        "\nstatus: stale\n---\n",
                        1  # 只替换第一个闭合 ---
                    )
                    filepath.write_text(content, encoding="utf-8")
                    fixed += 1
                    print(f"  ✅ 已标记为 stale: {filepath}")
            except Exception as e:
                print(f"  ❌ 无法修改 {filepath}: {e}")
    return fixed


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Auditor — 知识库治理健康度巡检"
    )
    parser.add_argument(
        "directories",
        nargs="+",
        help="要巡检的目录",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--fix-stale",
        action="store_true",
        help="自动标记过期文档为 stale",
    )
    parser.add_argument(
        "--version", action="version", version=f"knowledge_auditor {__version__}"
    )
    args = parser.parse_args()

    # 收集所有 .md 文件
    md_files = []
    for directory in args.directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"⚠️  目录不存在: {directory}", file=sys.stderr)
            continue
        md_files.extend(sorted(dir_path.rglob("*.md")))

    if not md_files:
        print("ℹ️  未找到 .md 文件", file=sys.stderr)
        sys.exit(0)

    # 审计每个文件
    results = [audit_file(f) for f in md_files]

    # 自动修复过期
    if args.fix_stale:
        fixed = fix_stale_files(results)
        print(f"\n已自动标记 {fixed} 个过期文档")

    # 输出
    if args.json:
        output = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.now().isoformat(),
            "health_score": calculate_health_score(results),
            "total_files": len(results),
            "results": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        report = generate_markdown_report(results, args.directories)
        print(report)

    # 退出码
    score = calculate_health_score(results)
    sys.exit(0 if score >= 7.0 else 1)


if __name__ == "__main__":
    main()
