#!/usr/bin/env python3
"""
Skill Security Audit — 静态安全分析工具

扫描 ~/.ai-skills/ 中的 skill 目录，检测：
- 凭据泄露（硬编码 API key/token/password）
- 数据外传（未声明的 HTTP 请求）
- 网络越界（scripts/ 有网络请求但 SKILL.md 未声明）
- IO 越界（IO 契约声明与脚本实际行为不符）
- Consent 机制（逆向 API skill 合规性）
- 供应链（列出外部依赖文件）

用法：
  python3 audit.py <skill_path>                    # 审计单个 skill
  python3 audit.py <skill_path> --dimension=credentials  # 仅凭据扫描
  python3 audit.py <skills_dir> --all              # 审计全仓
  python3 audit.py <skills_dir> --all --output=report.json  # 输出 JSON

零外部依赖：仅使用 Python 3 标准库。
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ============================================================
# 版本
# ============================================================
SCANNER_VERSION = "0.2.0"
SCHEMA_VERSION = "1.0"

# ============================================================
# 维度 1：凭据泄露（CRED-）
# ============================================================
CREDENTIAL_PATTERNS: list[tuple[str, str, str]] = [
    # (rule_id, pattern, description)
    ("CRED-001", r'(?i)(api[_\-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}', "Generic API Key"),
    ("CRED-002", r'sk-[a-zA-Z0-9]{20,}', "OpenAI API Key"),
    ("CRED-003", r'sk-ant-[a-zA-Z0-9]{20,}', "Anthropic API Key"),
    ("CRED-004", r'AIza[a-zA-Z0-9_\-]{35}', "Google API Key"),
    ("CRED-005", r'(?i)(token|secret)\s*[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}', "Token/Secret"),
    ("CRED-006", r'(?i)password\s*[=:]\s*["\']?[^\s"\'\]]{8,}', "Password"),
    ("CRED-007", r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
    ("CRED-008", r'(?:gho|ghs|ghr)_[a-zA-Z0-9]{36}', "GitHub OAuth/App Token"),
    ("CRED-009", r'AKIA[A-Z0-9]{16}', "AWS Access Key ID"),
    ("CRED-010", r'xox[bpsa]-[a-zA-Z0-9\-]{20,}', "Slack Token"),
]

# 安全模式：匹配到这些则跳过（正确的凭据使用方式）
SAFE_PATTERNS: list[re.Pattern] = [
    re.compile(r'os\.environ'),
    re.compile(r'os\.getenv'),
    re.compile(r'process\.env'),
    re.compile(r'\$\{?\w+\}?'),  # shell 变量引用 ${VAR} 或 $VAR
]

# ============================================================
# 维度 2：数据外传（EXFIL-）
# ============================================================
EXFIL_PATTERNS: list[tuple[str, str, str]] = [
    ("EXFIL-001", r'requests\.(get|post|put|delete|patch|head|options)\s*\(', "Python requests"),
    ("EXFIL-002", r'httpx\.(get|post|put|delete|patch|Client|AsyncClient)', "Python httpx"),
    ("EXFIL-003", r'urllib\.request', "Python urllib"),
    ("EXFIL-004", r'(?<!\w)curl\s+', "curl command"),
    ("EXFIL-005", r'(?<!\w)wget\s+', "wget command"),
    ("EXFIL-006", r'fetch\s*\(', "JavaScript fetch"),
    ("EXFIL-007", r'http\.client', "Python http.client"),
    ("EXFIL-008", r'aiohttp\.(ClientSession|request)', "Python aiohttp"),
]

# ============================================================
# 维度 4：IO 越界检测辅助模式
# ============================================================
FILE_WRITE_PATTERNS: list[re.Pattern] = [
    re.compile(r'open\s*\(.+["\'][wax]'),       # open(f, 'w') / 'a' / 'x' 模式
    re.compile(r'open\s*\(.+mode\s*=\s*["\'][wax]'),  # open(f, mode='w')
    re.compile(r'\.write\s*\('),
    re.compile(r'\.writelines\s*\('),
]

# 网络相关关键词（用于判断 SKILL.md 是否声明了网络访问）
NETWORK_KEYWORDS = [
    'url', 'http', 'https', 'fetch', 'download', 'api', 'request',
    '网络', '远程', '在线', 'web', 'endpoint', 'webhook',
]

# Consent 相关关键词
# 注意：'reverse' 单独出现太宽泛（会匹配 reverse migration 等），
# 需要与 API/engineer 等上下文组合判定
REVERSE_KEYWORDS_SIMPLE = ['undocumented api', '非官方 api', '非官方api']  # 直接匹配（需含上下文）
REVERSE_KEYWORDS_CONTEXTUAL = [
    re.compile(r'逆向\s*(工程|api|接口)', re.IGNORECASE),  # 逆向 + 上下文
    re.compile(r'reverse[\-\s]?engineer', re.IGNORECASE),
    re.compile(r'reverse[\-\s]?api', re.IGNORECASE),
    re.compile(r'unofficial[\-\s]?api', re.IGNORECASE),
    re.compile(r'undocumented[\-\s]?(api|endpoint)', re.IGNORECASE),
]
RISK_KEYWORDS = ['风险', 'risk', 'warning', '注意', 'caution', 'danger', '警告']

# 自引用排除名单：这些 skill 本身就是安全/审计工具，
# 文档中提到 reverse API 是作为检测目标的描述，不应触发 CONS-001
AUDIT_SELF_REFERENCE_SKILLS = {'skill-security-audit', 'skill-lint'}


# ============================================================
# 工具函数
# ============================================================

def is_comment_line(line: str) -> bool:
    """判断是否为注释行。"""
    stripped = line.strip()
    return stripped.startswith('#') or stripped.startswith('//')


def line_has_safe_pattern(line: str) -> bool:
    """判断行是否包含安全模式（如 os.environ）。"""
    return any(p.search(line) for p in SAFE_PATTERNS)


def read_file_safe(filepath: Path) -> str:
    """安全读取文件，处理编码错误。"""
    try:
        return filepath.read_text(encoding='utf-8', errors='replace')
    except (OSError, PermissionError):
        return ""


def parse_frontmatter(content: str) -> dict:
    """简单解析 YAML frontmatter（不依赖 PyYAML）。"""
    if not content.startswith('---'):
        return {}

    # v2 修复：统一处理 CRLF/CR 行尾，来源：审查报告 code-review 🔴#3
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break

    if end_idx == -1:
        return {}

    fm: dict[str, Any] = {}
    current_key = None
    for line in lines[1:end_idx]:
        # 简单的 key: value 解析
        if ':' in line and not line.startswith(' ') and not line.startswith('\t'):
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            if value == '>' or value == '|':
                # 多行值，后续行会拼接
                fm[key] = ''
                current_key = key
            else:
                fm[key] = value
                current_key = key
        elif current_key and (line.startswith('  ') or line.startswith('\t')):
            fm[current_key] = fm.get(current_key, '') + ' ' + line.strip()

    return fm


def get_scripts_dir(skill_path: Path) -> Path:
    """获取 skill 的 scripts/ 目录。"""
    return skill_path / 'scripts'


def get_script_files(skill_path: Path) -> list[Path]:
    """获取 scripts/ 下所有非二进制文件。"""
    scripts_dir = get_scripts_dir(skill_path)
    if not scripts_dir.exists():
        return []

    files = []
    text_extensions = {
        '.py', '.sh', '.bash', '.js', '.ts', '.rb', '.pl',
        '.r', '.go', '.rs', '.java', '.kt', '.swift',
        '.yml', '.yaml', '.json', '.toml', '.ini', '.cfg',
        '.txt', '.md', '.csv', '.env', '.conf',
        '',  # 无扩展名的文件（如 Makefile）
    }

    for f in scripts_dir.rglob('*'):
        if f.is_file() and f.suffix.lower() in text_extensions:
            files.append(f)

    return files


def load_audit_ignore(skill_path: Path) -> list[str]:
    """加载 .audit-ignore 文件中的忽略模式。"""
    ignore_file = skill_path / '.audit-ignore'
    if not ignore_file.exists():
        return []

    patterns = []
    for line in ignore_file.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            patterns.append(line)
    return patterns


def should_ignore_file(filepath: Path, skill_path: Path, ignore_patterns: list[str]) -> bool:
    """检查文件是否在忽略列表中。

    v2 修复：改用 fnmatch 做 glob 风格匹配，避免子串误杀。
    来源：审查报告 code-review 🔴#2
    """
    rel_path = str(filepath.relative_to(skill_path))
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(filepath.name, pattern):
            return True
    return False


def get_audit_ignore_dimensions(fm: dict) -> list[str]:
    """从 frontmatter 获取审计豁免维度（简单解析）。

    降级说明（v0.1）：Layer 3 显式白名单（frontmatter audit: ignore:）
    暂未实现。当前依赖 Layer 1（扫描范围限定）和 Layer 2（模式排除）
    及 .audit-ignore 文件。完整 YAML 解析需要 PyYAML，违反零依赖约束，
    后续可用 regex 近似实现。
    来源：审查报告 project-audit 🔴#1
    """
    return []


# ============================================================
# 审计维度实现
# ============================================================

def scan_credentials(skill_path: Path, script_files: list[Path],
                     ignore_patterns: list[str]) -> list[dict]:
    """维度 1：凭据泄露扫描。"""
    findings = []

    for filepath in script_files:
        if should_ignore_file(filepath, skill_path, ignore_patterns):
            continue

        content = read_file_safe(filepath)
        for line_num, line in enumerate(content.splitlines(), 1):
            if is_comment_line(line):
                continue
            if line_has_safe_pattern(line):
                continue

            for rule_id, pattern, desc in CREDENTIAL_PATTERNS:
                if re.search(pattern, line):
                    matched = line.strip()
                    if len(matched) > 80:
                        matched = matched[:77] + "..."

                    findings.append({
                        "dimension": "credential_leak",
                        "severity": "critical",
                        "rule_id": rule_id,
                        "file": str(filepath.relative_to(skill_path)),
                        "line": line_num,
                        "matched_content": matched,
                        "whitelisted": False,
                        "message": f"{desc} detected",
                    })
                    break  # 一行只报一个凭据规则

    return findings


def scan_exfiltration(skill_path: Path, script_files: list[Path],
                      ignore_patterns: list[str],
                      skill_declares_network: bool) -> list[dict]:
    """维度 2 + 3：数据外传 + 网络越界扫描。

    返回的 findings 可能同时包含 data_exfil 和 network_overreach。
    """
    findings = []
    has_network_calls = False

    for filepath in script_files:
        if should_ignore_file(filepath, skill_path, ignore_patterns):
            continue

        content = read_file_safe(filepath)
        for line_num, line in enumerate(content.splitlines(), 1):
            if is_comment_line(line):
                continue

            for rule_id, pattern, desc in EXFIL_PATTERNS:
                if re.search(pattern, line):
                    has_network_calls = True
                    matched = line.strip()
                    if len(matched) > 80:
                        matched = matched[:77] + "..."

                    # 如果 skill 已声明网络访问，数据外传不报警
                    if not skill_declares_network:
                        findings.append({
                            "dimension": "data_exfil",
                            "severity": "critical",
                            "rule_id": rule_id,
                            "file": str(filepath.relative_to(skill_path)),
                            "line": line_num,
                            "matched_content": matched,
                            "whitelisted": False,
                            "message": f"Undeclared external request: {desc}",
                        })
                    break

    # 维度 3：网络越界（汇总判定）
    if has_network_calls and not skill_declares_network:
        findings.append({
            "dimension": "network_overreach",
            "severity": "high",
            "rule_id": "NET-001",
            "file": "scripts/",
            "line": 0,
            "matched_content": "",
            "whitelisted": False,
            "message": "scripts/ contains network requests but SKILL.md does not declare network access",
        })

    return findings


def check_io_overreach(skill_path: Path, script_files: list[Path],
                       fm: dict, skill_md_content: str) -> list[dict]:
    """维度 4：IO 越界检查。"""
    findings = []

    # 只对有 io: 声明的 skill 检查
    has_io_declaration = 'io:' in skill_md_content or 'io:' in str(fm)
    if not has_io_declaration:
        return findings

    # 检查 IO-001：声明了 url 输入但 scripts/ 无 HTTP 代码
    io_text = skill_md_content.lower()
    declares_url_input = 'type: url' in io_text or "type: 'url'" in io_text or 'type: "url"' in io_text

    if declares_url_input:
        has_http_code = False
        for filepath in script_files:
            content = read_file_safe(filepath)
            for _, pattern, _ in EXFIL_PATTERNS:
                if re.search(pattern, content):
                    has_http_code = True
                    break
            if has_http_code:
                break

        if not has_http_code:
            findings.append({
                "dimension": "io_overreach",
                "severity": "high",
                "rule_id": "IO-001",
                "file": "SKILL.md",
                "line": 0,
                "matched_content": "io declares url input",
                "whitelisted": False,
                "message": "IO declares url input but scripts/ has no HTTP request code",
            })

    # 检查 IO-002：scripts/ 有文件写入但 io output 无 file 类型
    has_file_write = False
    write_file = ""
    write_line = 0
    for filepath in script_files:
        content = read_file_safe(filepath)
        for line_num, line in enumerate(content.splitlines(), 1):
            for wp in FILE_WRITE_PATTERNS:
                if wp.search(line):
                    has_file_write = True
                    write_file = str(filepath.relative_to(skill_path))
                    write_line = line_num
                    break
            if has_file_write:
                break
        if has_file_write:
            break

    if has_file_write:
        declares_file_output = any(
            kw in io_text
            for kw in ['type: markdown_file', 'type: json_data', 'type: image_file',
                        'type: directory', 'type: yaml_config',
                        "type: 'markdown_file'", 'type: "markdown_file"']
        )
        if not declares_file_output:
            findings.append({
                "dimension": "io_overreach",
                "severity": "high",
                "rule_id": "IO-002",
                "file": write_file,
                "line": write_line,
                "matched_content": "",
                "whitelisted": False,
                "message": "scripts/ writes files but IO declaration has no file output type",
            })

    return findings


def _has_reverse_api_reference(content: str) -> bool:
    """检查内容是否真正提及逆向/非官方 API（而非普通的 reverse 用法）。"""
    content_lower = content.lower()

    # 直接匹配项（这些词本身就足够明确）
    if any(kw in content_lower for kw in REVERSE_KEYWORDS_SIMPLE):
        return True

    # 上下文匹配项（需要组合判定）
    if any(p.search(content) for p in REVERSE_KEYWORDS_CONTEXTUAL):
        return True

    return False


def check_consent(skill_path: Path, skill_md_content: str) -> list[dict]:
    """维度 5：Consent 机制检查。"""
    findings = []
    skill_name = skill_path.name
    content_lower = skill_md_content.lower()

    has_reverse_ref = _has_reverse_api_reference(skill_md_content)
    # v3 修复：改为检查 skill name 是否**包含** 'danger-'，而非仅 startswith
    # 修复 baoyu-danger-gemini-web / baoyu-danger-x-to-markdown 等误报
    # 来源：完整版测试报告 2026-03-14 CONS-001 误报分析
    has_danger_prefix = 'danger-' in skill_name
    # 自引用排除：审计/安全工具自身文档中提及 reverse API 是检测目标
    is_self_reference = skill_name in AUDIT_SELF_REFERENCE_SKILLS
    has_risk_explanation = any(kw in content_lower for kw in RISK_KEYWORDS)

    # CONS-001：有逆向/非官方 API 引用但无 danger- 前缀（排除自引用审计工具）
    if has_reverse_ref and not has_danger_prefix and not is_self_reference:
        findings.append({
            "dimension": "consent",
            "severity": "medium",
            "rule_id": "CONS-001",
            "file": "SKILL.md",
            "line": 0,
            "matched_content": "",
            "whitelisted": False,
            "message": "SKILL.md mentions reverse/unofficial API but skill name lacks 'danger-' prefix",
        })

    # CONS-002：有 danger- 前缀但无风险说明
    if has_danger_prefix and not has_risk_explanation:
        findings.append({
            "dimension": "consent",
            "severity": "medium",
            "rule_id": "CONS-002",
            "file": "SKILL.md",
            "line": 0,
            "matched_content": "",
            "whitelisted": False,
            "message": "Skill has 'danger-' prefix but SKILL.md lacks risk explanation section",
        })

    return findings


def check_supply_chain(skill_path: Path) -> list[dict]:
    """维度 6：供应链检查（仅列出依赖文件）。"""
    findings = []
    dep_files = ['requirements.txt', 'package.json', 'Pipfile', 'pyproject.toml']

    # v2 修复：改用 enumerate 生成 rule_id，避免 list.index() 的 O(n²) 和重复项问题
    # 来源：审查报告 project-audit 🟢#1
    for idx, dep_file in enumerate(dep_files, 1):
        dep_path = skill_path / dep_file
        if dep_path.exists():
            content = read_file_safe(dep_path)
            preview = content[:200] + "..." if len(content) > 200 else content
            findings.append({
                "dimension": "supply_chain",
                "severity": "low",
                "rule_id": f"SUPPLY-{idx:03d}",
                "file": dep_file,
                "line": 0,
                "matched_content": preview.strip(),
                "whitelisted": False,
                "message": f"External dependency file found: {dep_file}",
            })

    return findings


# ============================================================
# 主审计逻辑
# ============================================================

def skill_declares_network_access(fm: dict, skill_md_content: str) -> bool:
    """判断 skill 是否在 SKILL.md 中声明了网络访问。"""
    # 检查 description
    desc = fm.get('description', '').lower()
    content_lower = skill_md_content.lower()

    for kw in NETWORK_KEYWORDS:
        if kw in desc:
            return True

    # 检查 io: 中是否有 url 类型
    if 'type: url' in content_lower:
        return True

    return False


def audit_single_skill(skill_path: Path,
                       dimensions: list[str] | None = None) -> dict:
    """审计单个 skill，返回结果 dict。"""
    skill_name = skill_path.name
    all_findings: list[dict] = []

    # 读取 SKILL.md
    skill_md_path = skill_path / 'SKILL.md'
    if not skill_md_path.exists():
        return {
            "skill_path": str(skill_path),
            "skill_name": skill_name,
            "status": "WARNING",
            "findings": [{
                "dimension": "consent",
                "severity": "medium",
                "rule_id": "GENERAL-001",
                "file": "",
                "line": 0,
                "matched_content": "",
                "whitelisted": False,
                "message": "SKILL.md not found",
            }],
            "summary": {"critical": 0, "high": 0, "medium": 1, "low": 0},
        }

    skill_md_content = read_file_safe(skill_md_path)
    fm = parse_frontmatter(skill_md_content)

    # 获取文件列表和忽略规则
    script_files = get_script_files(skill_path)
    ignore_patterns = load_audit_ignore(skill_path)
    declares_network = skill_declares_network_access(fm, skill_md_content)

    # 运行各维度
    run_all = dimensions is None or len(dimensions) == 0
    dim_set = set(dimensions) if dimensions else set()

    if run_all or 'credentials' in dim_set:
        all_findings.extend(scan_credentials(skill_path, script_files, ignore_patterns))

    if run_all or 'exfil' in dim_set or 'network' in dim_set:
        all_findings.extend(scan_exfiltration(
            skill_path, script_files, ignore_patterns, declares_network))

    if run_all or 'io' in dim_set:
        all_findings.extend(check_io_overreach(
            skill_path, script_files, fm, skill_md_content))

    if run_all or 'consent' in dim_set:
        all_findings.extend(check_consent(skill_path, skill_md_content))

    if run_all or 'supply_chain' in dim_set:
        all_findings.extend(check_supply_chain(skill_path))

    # 计算 summary
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        if not f.get("whitelisted", False):
            sev = f.get("severity", "low")
            summary[sev] = summary.get(sev, 0) + 1

    # 判定 status
    if summary["critical"] > 0:
        status = "CRITICAL"
    elif summary["high"] > 0 or summary["medium"] > 0:
        status = "WARNING"
    else:
        status = "PASS"

    return {
        "skill_path": str(skill_path),
        "skill_name": skill_name,
        "status": status,
        "findings": all_findings,
        "summary": summary,
    }


def audit_all_skills(skills_dir: Path,
                     dimensions: list[str] | None = None) -> list[dict]:
    """审计目录下的所有 skill。"""
    results = []

    if not skills_dir.exists():
        print(f"Error: directory not found: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    # 获取所有 skill 目录（有 SKILL.md 的子目录）
    skill_dirs = sorted([
        d for d in skills_dir.iterdir()
        if d.is_dir()
        and not d.name.startswith('.')
        and not d.name.startswith('_')
        and (d / 'SKILL.md').exists()
    ])

    for skill_dir in skill_dirs:
        result = audit_single_skill(skill_dir, dimensions)
        results.append(result)

    return results


def print_results(results: list[dict]) -> None:
    """以终端友好格式输出结果。"""
    print()
    for r in results:
        status = r["status"]
        name = r["skill_name"]
        summary = r["summary"]
        total = sum(summary.values())

        if status == "PASS":
            icon = "✅"
            label = "PASS"
        elif status == "WARNING":
            icon = "🟡"
            label = "WARN"
        else:
            icon = "🔴"
            label = "CRIT"

        # 状态行
        detail_parts = []
        if summary["critical"] > 0:
            detail_parts.append(f"{summary['critical']} critical")
        if summary["high"] > 0:
            detail_parts.append(f"{summary['high']} high")
        if summary["medium"] > 0:
            detail_parts.append(f"{summary['medium']} medium")
        if summary["low"] > 0:
            detail_parts.append(f"{summary['low']} low")

        detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
        print(f"[{label}] {name} — {total} findings{detail}")

        # 关键发现缩进显示
        for f in r.get("findings", []):
            if f["severity"] in ("critical", "high") and not f.get("whitelisted"):
                loc = f"{f['file']}:{f['line']}" if f['line'] > 0 else f['file']
                print(f"  └── {f['rule_id']}: {loc} — {f['message']}")

    # 汇总
    total_skills = len(results)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    warn_count = sum(1 for r in results if r["status"] == "WARNING")
    crit_count = sum(1 for r in results if r["status"] == "CRITICAL")

    print()
    print("═" * 55)
    print(f"Total: {total_skills} skills | PASS: {pass_count} | WARN: {warn_count} | CRIT: {crit_count}")
    print("═" * 55)
    print()


def build_report(results: list[dict], mode: str) -> dict:
    """构建完整的 JSON 报告。"""
    total_skills = len(results)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    warn_count = sum(1 for r in results if r["status"] == "WARNING")
    crit_count = sum(1 for r in results if r["status"] == "CRITICAL")

    return {
        "schema_version": SCHEMA_VERSION,
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "scanner_version": SCANNER_VERSION,
        "mode": mode,
        "results": results,
        "global_summary": {
            "total_skills": total_skills,
            "pass": pass_count,
            "warning": warn_count,
            "critical": crit_count,
        },
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Skill Security Audit — 静态安全分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s ~/.ai-skills/translate                    # 审计单个 skill
  %(prog)s ~/.ai-skills/translate --dimension credentials  # 仅凭据扫描
  %(prog)s ~/.ai-skills --all                        # 审计全仓
  %(prog)s ~/.ai-skills --all --output report.json   # 输出 JSON 报告
""",
    )
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {SCANNER_VERSION} (schema {SCHEMA_VERSION})')
    parser.add_argument("path", help="skill 目录路径（单个 skill 或 skills 仓库根目录）")
    parser.add_argument("--all", action="store_true", help="审计目录下所有 skill")
    parser.add_argument("--dimension", type=str, default=None,
                        help="仅运行指定维度 (credentials, exfil, network, io, consent, supply_chain)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="输出 JSON 报告到指定文件")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 格式输出到 stdout")

    args = parser.parse_args()
    target = Path(args.path).expanduser().resolve()

    dimensions = [args.dimension] if args.dimension else None

    if args.all:
        results = audit_all_skills(target, dimensions)
        mode = "all"
    else:
        if not target.is_dir():
            print(f"Error: not a directory: {target}", file=sys.stderr)
            sys.exit(1)
        result = audit_single_skill(target, dimensions)
        results = [result]
        mode = "single"

    # 输出
    if args.output:
        report = build_report(results, mode)
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        print(f"Report saved to: {output_path}")
        print_results(results)  # 同时打印终端摘要
    elif args.json:
        report = build_report(results, mode)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_results(results)

    # 退出码
    has_critical = any(r["status"] == "CRITICAL" for r in results)
    sys.exit(1 if has_critical else 0)


if __name__ == "__main__":
    main()
