#!/usr/bin/env python3
"""
task-runner.py — Level 1 任务执行器 + YAML 解析中枢

集中负责：
  1. 解析任务 YAML（供 scheduler.py 和 agent-wrapper.sh 调用）
  2. 校验任务定义合法性
  3. 执行 Level 1（agent-free）任务

用法：
    python3 task-runner.py <task.yaml>                   # 执行 Level 1 任务
    python3 task-runner.py <task.yaml> --dry-run          # 只打印命令，不执行
    python3 task-runner.py <task.yaml> --parse            # 解析并输出 JSON
    python3 task-runner.py <task.yaml> --extract-all      # 等同 --parse（兼容）
    python3 task-runner.py <task.yaml> --validate         # 校验合法性
    python3 task-runner.py --help

零外部依赖（纯 Python stdlib）。
"""

import os
import sys
import re
import json
import subprocess
import argparse
from datetime import datetime, timezone

__version__ = "0.1.0"

# -------------------------------------------------------------------
# 配置
# -------------------------------------------------------------------

DEFAULT_SKILLS_DIR = os.path.expanduser("~/.ai-skills")
DEFAULT_LOG_FILE = os.path.join(DEFAULT_SKILLS_DIR, ".logs", "executions.jsonl")

VALID_LEVELS = [1, 2]
VALID_ON_FAILURE = ["log", "retry"]
VALID_AGENTS = ["gemini", "claude", "codex"]

# 合法 cron 表达式的字段数
CRON_FIELD_COUNT = 5

# -------------------------------------------------------------------
# YAML 子集解析器（借鉴 Phase 4 run-chain.py）
# -------------------------------------------------------------------

def parse_task_yaml(filepath):
    """解析任务定义 YAML 文件。

    支持：扁平 key-value, 内联数组 [a, b, c], 布尔值, null, 注释
    不支持：嵌套字典, 多行字符串, 锚点, 标签
    """
    if not os.path.exists(filepath):
        print(f"❌ Task file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    task = {}
    for line_num, line in enumerate(lines, 1):
        stripped_raw = line.strip()
        if not stripped_raw:
            continue

        # 先检查是否是纯注释行（以 # 开头）
        if stripped_raw.startswith('#'):
            continue

        # 对于含冒号的行，先提取 key 再决定是否做注释截断
        if ':' in stripped_raw:
            key_part = stripped_raw[:stripped_raw.index(':')].strip()

            # prompt 字段特殊处理：不截断行内注释
            # 因为 prompt 是自然语言，# 号是合法内容（如 "issue #123"、"C# code"）
            if key_part == 'prompt':
                key, val = _split_kv(stripped_raw)
                val = val.strip()
                task[key] = _clean_value(val)
                continue

        # 其他字段：正常截断行内注释
        comment_pos = _find_comment(line)
        if comment_pos >= 0:
            line = line[:comment_pos]

        stripped = line.strip()
        if not stripped:
            continue

        # key: value 格式
        if ':' in stripped:
            key, val = _split_kv(stripped)
            val = val.strip()

            # 内联数组 [a, b, c]
            if val.startswith('[') and val.endswith(']'):
                task[key] = _parse_inline_array(val)
            else:
                task[key] = _clean_value(val)
        else:
            # 非 key:value 行，跳过
            continue

    return task


def _find_comment(line):
    """找到行内注释的位置（不在引号内的 #）。"""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == '#' and not in_single and not in_double:
            # YAML 规范：行内注释的 # 前面必须有空白字符
            # 否则 "issue #123" 中的 # 会被误判为注释
            if i == 0 or line[i-1] in (' ', '\t'):
                return i
    return -1


def _split_kv(s):
    """分割 key: value。只取第一个冒号。"""
    idx = s.index(':')
    key = s[:idx].strip()
    val = s[idx + 1:].strip()
    return key, val


def _clean_value(val):
    """清理值：去引号，识别布尔值、null、整数。"""
    if not val:
        return val

    # 去引号
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]

    # 布尔值
    if val.lower() == 'true':
        return True
    if val.lower() == 'false':
        return False

    # null
    if val.lower() == 'null' or val == '~':
        return None

    # 整数
    try:
        return int(val)
    except ValueError:
        pass

    return val


def _parse_inline_array(val):
    """解析内联数组：["a", "b", "c"] 或 [a, b, c]。"""
    inner = val[1:-1].strip()
    if not inner:
        return []

    items = []
    for item in inner.split(','):
        item = item.strip()
        item = _clean_value(item)
        if item is not None and item != '':
            items.append(item)
    return items


# -------------------------------------------------------------------
# 任务校验
# -------------------------------------------------------------------

def validate_task(task, filepath=""):
    """校验任务定义合法性。返回错误列表。"""
    errors = []
    context = f" (in {os.path.basename(filepath)})" if filepath else ""

    # 必填字段检查
    required_fields = ['schema_version', 'name', 'description', 'level', 'schedule', 'enabled']
    for field in required_fields:
        if field not in task:
            errors.append(f"缺少必填字段: {field}{context}")

    if errors:
        return errors  # 基础字段缺失，无法继续校验

    # schema_version
    if str(task.get('schema_version')) != '1.0':
        errors.append(f"schema_version 必须为 '1.0'，当前: {task.get('schema_version')}{context}")

    # name 格式
    name = str(task.get('name', ''))
    if not re.match(r'^[a-z0-9-]+$', name):
        errors.append(f"name 必须为 kebab-case [a-z0-9-]+，当前: '{name}'{context}")

    # level
    level = task.get('level')
    if level not in VALID_LEVELS:
        errors.append(f"level 必须为 1 或 2，当前: {level}{context}")

    # schedule（5 字段 cron）
    schedule = str(task.get('schedule', ''))
    parts = schedule.split()
    if len(parts) != CRON_FIELD_COUNT:
        errors.append(f"schedule 必须为 5 字段 cron 表达式，当前 {len(parts)} 字段: '{schedule}'{context}")

    # enabled 必须是布尔值
    if task.get('enabled') not in (True, False):
        errors.append(f"enabled 必须为 true 或 false{context}")

    # Level 1 必填
    if level == 1:
        if not task.get('command'):
            errors.append(f"Level 1 任务必须有 command 字段{context}")

    # Level 2 必填
    if level == 2:
        agent = task.get('agent')
        if not agent:
            errors.append(f"Level 2 任务必须有 agent 字段{context}")
        elif agent not in VALID_AGENTS:
            errors.append(f"agent 必须为 {VALID_AGENTS} 之一，当前: '{agent}'{context}")
        if not task.get('prompt'):
            errors.append(f"Level 2 任务必须有 prompt 字段{context}")

    # 可选字段校验
    on_failure = task.get('on_failure')
    if on_failure is not None and on_failure not in VALID_ON_FAILURE:
        errors.append(f"on_failure 必须为 {VALID_ON_FAILURE} 之一，当前: '{on_failure}'{context}")

    timeout = task.get('timeout_seconds')
    if timeout is not None:
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append(f"timeout_seconds 必须为正整数，当前: {timeout}{context}")

    max_retries = task.get('max_retries')
    if max_retries is not None:
        if not isinstance(max_retries, int) or max_retries < 0:
            errors.append(f"max_retries 必须为非负整数，当前: {max_retries}{context}")

    return errors


# -------------------------------------------------------------------
# Level 1 任务执行
# -------------------------------------------------------------------

def run_task(task, dry_run=False):
    """执行 Level 1 任务。"""
    level = task.get('level')
    if level != 1:
        print(f"❌ task-runner.py 只执行 Level 1 任务。当前任务 Level: {level}", file=sys.stderr)
        print(f"   Level 2 任务请使用 agent-wrapper.sh", file=sys.stderr)
        sys.exit(1)

    command = task.get('command', '')
    args = task.get('args', [])
    if isinstance(args, str):
        args = [args]
    if args is None:
        args = []

    # 展开路径中的 ~
    command = os.path.expanduser(command)
    args = [os.path.expanduser(str(a)) for a in args]

    working_dir = os.path.expanduser(task.get('working_dir', '~'))
    timeout = task.get('timeout_seconds', 300)
    on_failure = task.get('on_failure', 'log')
    max_retries = task.get('max_retries', 0)
    task_name = task.get('name', 'unknown')

    full_cmd = [command] + args

    if dry_run:
        print(f"[DRY-RUN] Task: {task_name}")
        print(f"[DRY-RUN] Level: 1")
        print(f"[DRY-RUN] Command: {' '.join(full_cmd)}")
        print(f"[DRY-RUN] Working Dir: {working_dir}")
        print(f"[DRY-RUN] Timeout: {timeout}s")
        print(f"[DRY-RUN] On Failure: {on_failure}")
        print(f"[DRY-RUN] Max Retries: {max_retries}")
        return

    print(f"=== [{datetime.now(timezone.utc).isoformat()}] Starting Level 1 task: {task_name} ===")
    print(f"Command: {' '.join(full_cmd)}")

    status = "success"
    attempt = 0
    max_attempts = max_retries + 1

    while attempt < max_attempts:
        attempt += 1
        if attempt > 1:
            print(f"--- Retry {attempt - 1}/{max_retries} ---")

        try:
            result = subprocess.run(
                full_cmd,
                cwd=working_dir,
                timeout=timeout,
                capture_output=False
            )

            if result.returncode == 0:
                status = "success"
                break
            else:
                status = "failure"
                print(f"❌ Command exited with code {result.returncode}")
                if on_failure != "retry" or attempt >= max_attempts:
                    break
        except subprocess.TimeoutExpired:
            status = "failure"
            print(f"❌ Command timed out after {timeout}s")
            if on_failure != "retry" or attempt >= max_attempts:
                break
        except FileNotFoundError:
            status = "failure"
            print(f"❌ Command not found: {command}")
            break
        except Exception as e:
            status = "failure"
            print(f"❌ Unexpected error: {e}")
            break

    print(f"=== [{datetime.now(timezone.utc).isoformat()}] Task {task_name} finished with status: {status} ===")

    # 调用 observability 记录
    _log_to_observability(task_name, status)

    if status == "failure":
        sys.exit(1)


def _log_to_observability(task_name, status):
    """调用 log-execution.py 记录到 observability 系统。"""
    log_script = os.path.join(DEFAULT_SKILLS_DIR, "skill-observability", "scripts", "log-execution.py")

    if not os.path.exists(log_script):
        print(f"⚠️ skill-observability 未安装，跳过日志记录", file=sys.stderr)
        return

    try:
        subprocess.run(
            [
                sys.executable, log_script,
                "--skill", "scheduled-tasks",
                "--agent", "cron",
                "--status", status,
                "--notes", f"Level 1 task: {task_name}"
            ],
            timeout=10,
            capture_output=True
        )
    except Exception as e:
        print(f"⚠️ observability 日志记录失败: {e}", file=sys.stderr)


# -------------------------------------------------------------------
# CLI 入口
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="task-runner.py — Level 1 任务执行器 + YAML 解析中枢",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python3 task-runner.py task.yaml              # 执行 Level 1 任务
  python3 task-runner.py task.yaml --dry-run     # 只打印命令
  python3 task-runner.py task.yaml --parse       # 输出解析后的 JSON
  python3 task-runner.py task.yaml --validate    # 校验合法性
"""
    )
    parser.add_argument('task_file', help='任务 YAML 文件路径')
    parser.add_argument('--dry-run', action='store_true', help='只打印命令，不执行')
    parser.add_argument('--parse', action='store_true', help='解析 YAML 并输出 JSON')
    parser.add_argument('--extract-all', action='store_true', help='等同 --parse（兼容 agent-wrapper.sh）')
    parser.add_argument('--validate', action='store_true', help='校验任务定义合法性')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args()
    task_file = args.task_file

    # 解析 YAML
    task = parse_task_yaml(task_file)

    # --parse / --extract-all 模式
    if args.parse or args.extract_all:
        # 输出 JSON 到 stdout（供其他脚本调用）
        print(json.dumps(task, ensure_ascii=False, indent=None))
        return

    # --validate 模式
    if args.validate:
        errors = validate_task(task, task_file)
        if errors:
            print(f"❌ 任务定义校验失败 ({os.path.basename(task_file)}):")
            for err in errors:
                print(f"   • {err}")
            sys.exit(1)
        else:
            print(f"✅ 任务定义校验通过: {task.get('name', '?')}")
        return

    # 默认：先校验，再执行
    errors = validate_task(task, task_file)
    if errors:
        print(f"❌ 任务定义校验失败 ({os.path.basename(task_file)}):")
        for err in errors:
            print(f"   • {err}")
        sys.exit(1)

    # --dry-run 或执行
    run_task(task, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
