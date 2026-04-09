#!/usr/bin/env python3
"""
scheduler.py — crontab 定时任务管理器

管理 cron 条目的安装、移除和状态查看。
通过调用 task-runner.py --parse 获取 YAML 解析结果。

用法：
    python3 scheduler.py install [--task NAME] [--dry-run]
    python3 scheduler.py remove [--task NAME]
    python3 scheduler.py list
    python3 scheduler.py status
    python3 scheduler.py --help

零外部依赖（纯 Python stdlib）。
"""

import os
import sys
import json
import glob
import subprocess
import argparse

__version__ = "0.1.0"

# -------------------------------------------------------------------
# 配置
# -------------------------------------------------------------------

SKILLS_DIR = os.path.expanduser("~/.ai-skills")
SCHEDULED_DIR = os.path.join(SKILLS_DIR, "scheduled-tasks")
TASKS_DIR = os.path.join(SCHEDULED_DIR, "tasks")
SCRIPTS_DIR = os.path.join(SCHEDULED_DIR, "scripts")
LOGS_DIR = os.path.join(SKILLS_DIR, ".logs")

CRONTAB_BEGIN = "# BEGIN scheduled-tasks (managed by scheduler.py — do not edit manually)"
CRONTAB_END = "# END scheduled-tasks"

TASK_RUNNER = os.path.join(SCRIPTS_DIR, "task-runner.py")
AGENT_WRAPPER = os.path.join(SCRIPTS_DIR, "agent-wrapper.sh")


# -------------------------------------------------------------------
# 任务加载（通过 task-runner.py --parse）
# -------------------------------------------------------------------

def load_task(task_file):
    """通过 task-runner.py --parse 加载并解析任务文件。"""
    try:
        result = subprocess.run(
            [sys.executable, TASK_RUNNER, task_file, "--parse"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print(f"⚠️ 解析失败 ({os.path.basename(task_file)}): {result.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(result.stdout.strip())
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"⚠️ 加载失败 ({os.path.basename(task_file)}): {e}", file=sys.stderr)
        return None


def validate_task(task_file):
    """通过 task-runner.py --validate 校验任务文件。"""
    try:
        result = subprocess.run(
            [sys.executable, TASK_RUNNER, task_file, "--validate"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout.strip() + result.stderr.strip()
    except Exception as e:
        return False, str(e)


def discover_tasks(task_name=None):
    """发现所有任务文件，可选按名称过滤。"""
    if not os.path.isdir(TASKS_DIR):
        print(f"❌ 任务目录不存在: {TASKS_DIR}", file=sys.stderr)
        sys.exit(1)

    yaml_files = sorted(glob.glob(os.path.join(TASKS_DIR, "*.yaml")))
    if not yaml_files:
        print("(任务目录为空，无可用任务)")
        return []

    tasks = []
    for yf in yaml_files:
        task = load_task(yf)
        if task is None:
            continue
        task['_filepath'] = yf
        if task_name is None or task.get('name') == task_name:
            tasks.append(task)

    return tasks


# -------------------------------------------------------------------
# crontab 操作
# -------------------------------------------------------------------

def read_crontab():
    """读取当前用户的 crontab 内容。"""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            # no crontab for user
            return ""
        return result.stdout
    except FileNotFoundError:
        print("❌ crontab 命令不可用。请确认 cron 已安装。", file=sys.stderr)
        sys.exit(1)


def write_crontab(content):
    """写入 crontab。"""
    try:
        proc = subprocess.run(
            ["crontab", "-"],
            input=content,
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            print(f"❌ 写入 crontab 失败: {proc.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print("❌ crontab 命令不可用。", file=sys.stderr)
        sys.exit(1)


def remove_managed_section(crontab_content):
    """移除 crontab 中 scheduled-tasks 管理的段落。"""
    lines = crontab_content.splitlines()
    result = []
    in_managed = False

    for line in lines:
        if line.strip() == CRONTAB_BEGIN:
            in_managed = True
            continue
        if line.strip() == CRONTAB_END:
            in_managed = False
            continue
        if not in_managed:
            result.append(line)

    return '\n'.join(result)


def generate_crontab_entry(task):
    """为单个任务生成 crontab 条目。"""
    name = task.get('name', 'unknown')
    schedule = task.get('schedule', '')
    level = task.get('level', 1)
    filepath = task.get('_filepath', '')
    lock_file = f"/tmp/st-{name}.lock"

    if level == 1:
        cmd = f"flock -n {lock_file} {sys.executable} {TASK_RUNNER} {filepath}"
    else:
        cmd = f"flock -n {lock_file} bash {AGENT_WRAPPER} {filepath}"

    log_file = os.path.join(LOGS_DIR, f"scheduled-{name}.log")

    return f"{schedule} {cmd} >> {log_file} 2>&1  # {name}"


def generate_managed_section(tasks):
    """生成 crontab 中 scheduled-tasks 管理的完整段落。"""
    lines = [CRONTAB_BEGIN]

    # 环境变量
    lines.append(f"PATH={os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}")
    lines.append(f"HOME={os.path.expanduser('~')}")
    lines.append(f"AGENT_SKILLS_DIR={SKILLS_DIR}")
    lines.append("")

    enabled_tasks = [t for t in tasks if t.get('enabled', False)]

    if not enabled_tasks:
        lines.append("# (no enabled tasks)")
    else:
        for task in enabled_tasks:
            lines.append(generate_crontab_entry(task))

    lines.append("")
    lines.append(CRONTAB_END)

    return '\n'.join(lines)


# -------------------------------------------------------------------
# 命令实现
# -------------------------------------------------------------------

def cmd_install(args):
    """安装任务到 crontab。"""
    tasks = discover_tasks(args.task)

    if not tasks:
        if args.task:
            print(f"❌ 未找到任务: {args.task}")
        else:
            print("❌ 无可用任务")
        sys.exit(1)

    # 校验所有任务
    all_valid = True
    for task in tasks:
        valid, msg = validate_task(task['_filepath'])
        if not valid:
            print(f"❌ {msg}")
            all_valid = False

    if not all_valid:
        print("\n❌ 存在校验失败的任务，安装中止。")
        sys.exit(1)

    # 生成 crontab 内容
    managed_section = generate_managed_section(tasks)

    if args.dry_run:
        print("═══ [DRY-RUN] 将要写入的 crontab 段落 ═══\n")
        print(managed_section)
        print(f"\n═══ 共 {len([t for t in tasks if t.get('enabled')])} 个启用任务 ═══")
        return

    # 读取现有 crontab，替换管理段落
    current = read_crontab()
    cleaned = remove_managed_section(current)

    # 确保末尾有换行
    if cleaned and not cleaned.endswith('\n'):
        cleaned += '\n'

    new_crontab = cleaned + managed_section + '\n'
    write_crontab(new_crontab)

    enabled_count = len([t for t in tasks if t.get('enabled')])
    total_count = len(tasks)
    print(f"✅ 已安装 {enabled_count}/{total_count} 个任务到 crontab")


def cmd_remove(args):
    """从 crontab 移除任务。"""
    current = read_crontab()

    if CRONTAB_BEGIN not in current:
        print("ℹ️ crontab 中没有 scheduled-tasks 管理的条目")
        return

    cleaned = remove_managed_section(current)
    write_crontab(cleaned)
    print("✅ 已从 crontab 移除所有 scheduled-tasks 条目")


def cmd_list(args):
    """列出所有任务及其状态。"""
    tasks = discover_tasks()

    if not tasks:
        print("(无可用任务)")
        return

    # 检查 crontab 中已安装的任务
    current = read_crontab()
    installed_names = set()
    for line in current.splitlines():
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        # 从注释中提取任务名
        if '# ' in line:
            name = line.rsplit('# ', 1)[1].strip()
            installed_names.add(name)

    print("═══ 定时任务列表 ═══\n")
    print(f"| {'任务名':<30} | {'级别':^4} | {'调度':^15} | {'启用':^4} | {'已安装':^6} |")
    print(f"|{'-'*32}|{'-'*6}|{'-'*17}|{'-'*6}|{'-'*8}|")

    for task in tasks:
        name = task.get('name', '?')
        level = task.get('level', '?')
        schedule = task.get('schedule', '?')
        enabled = '✅' if task.get('enabled') else '❌'
        installed = '✅' if name in installed_names else '—'
        print(f"| {name:<30} | L{level:>3} | {schedule:^15} | {enabled:^4} | {installed:^6} |")

    print(f"\n共 {len(tasks)} 个任务")


def cmd_status(args):
    """显示 crontab 中 scheduled-tasks 的当前状态。"""
    current = read_crontab()

    if CRONTAB_BEGIN not in current:
        print("ℹ️ crontab 中没有 scheduled-tasks 管理的条目")
        print("   运行 'scheduler.py install' 安装任务")
        return

    # 提取管理段落
    lines = current.splitlines()
    in_managed = False
    managed_lines = []

    for line in lines:
        if line.strip() == CRONTAB_BEGIN:
            in_managed = True
            managed_lines.append(line)
            continue
        if line.strip() == CRONTAB_END:
            managed_lines.append(line)
            in_managed = False
            continue
        if in_managed:
            managed_lines.append(line)

    print("═══ crontab 中的 scheduled-tasks 条目 ═══\n")
    for line in managed_lines:
        print(f"  {line}")

    # 统计
    entry_count = len([l for l in managed_lines if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('PATH') and not l.strip().startswith('HOME') and not l.strip().startswith('AGENT_SKILLS_DIR')])
    print(f"\n共 {entry_count} 条活跃条目")


# -------------------------------------------------------------------
# CLI 入口
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="scheduler.py — crontab 定时任务管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python3 scheduler.py list                    # 列出所有任务
  python3 scheduler.py install --dry-run       # 预览 crontab 变更
  python3 scheduler.py install                 # 安装到 crontab
  python3 scheduler.py install --task my-task  # 只安装指定任务
  python3 scheduler.py remove                  # 移除所有条目
  python3 scheduler.py status                  # 查看当前 crontab 状态
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # install
    install_parser = subparsers.add_parser('install', help='安装任务到 crontab')
    install_parser.add_argument('--task', help='只安装指定任务（按名称）')
    install_parser.add_argument('--dry-run', action='store_true', help='只打印，不实际修改')

    # remove
    remove_parser = subparsers.add_parser('remove', help='从 crontab 移除任务')
    remove_parser.add_argument('--task', help='只移除指定任务（暂不支持，移除全部）')

    # list
    subparsers.add_parser('list', help='列出所有任务')

    # status
    subparsers.add_parser('status', help='查看 crontab 状态')

    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 确保日志目录存在
    os.makedirs(LOGS_DIR, exist_ok=True)

    if args.command == 'install':
        cmd_install(args)
    elif args.command == 'remove':
        cmd_remove(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'status':
        cmd_status(args)


if __name__ == "__main__":
    main()
