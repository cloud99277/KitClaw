#!/usr/bin/env python3
"""
run-chain.py — 线性链式 Skill 编排器

基于 Phase 1 IO 契约，验证和规划 YAML 编排链。
从 verify-chain.py 提取核心函数并升级（动态加载 type-registry.json）。

用法：
    python3 run-chain.py validate <chain.yaml> [--skills-dir DIR] [--type-registry PATH]
    python3 run-chain.py plan <chain.yaml> --var KEY=VALUE [--skills-dir DIR]
    python3 run-chain.py list [--chains-dir DIR]
    python3 run-chain.py --version

零外部依赖（纯 Python stdlib）。
"""

import os
import sys
import re
import json
import glob

__version__ = "0.1.0"

# -------------------------------------------------------------------
# 配置
# -------------------------------------------------------------------

DEFAULT_SKILLS_DIR = os.path.expanduser("~/.ai-skills")
DEFAULT_CHAINS_DIR = None  # 默认为 skills_dir/agent-orchestrator/chains

# 内置兼容规则回退值（来自 verify-chain.py）
BUILTIN_COMPATIBILITY_RULES = {
    "markdown_file": ["text"],
    "text": ["markdown_file", "url"],
}

# 不支持的 YAML 语法检测
UNSUPPORTED_YAML_PATTERNS = [
    (r'^\s*\w+:\s*[|>]\s*$', '多行字符串 (| 或 >)'),
    (r'&\w+', '锚点 (&)'),
    (r'\*\w+', '引用 (*)'),
    (r'<<:', '合并键 (<<:)'),
    (r'!!\w+', 'YAML 标签 (!!)'),
]


# -------------------------------------------------------------------
# YAML 子集解析器（T2）
# -------------------------------------------------------------------

def parse_chain_yaml(filepath):
    """解析编排链 YAML 文件（YAML 子集解析器）。

    支持：flat key-value, 列表, inline dict, 2层嵌套, 注释
    不支持：多行字符串, 锚点, 标签, 多文档, >2层嵌套
    """
    if not os.path.exists(filepath):
        print(f"❌ Chain file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 检查不支持的语法
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            continue
        for pattern, desc in UNSUPPORTED_YAML_PATTERNS:
            if re.search(pattern, stripped):
                print(f"❌ Line {line_num}: 不支持的 YAML 语法 '{desc}'。"
                      f"agent-orchestrator 仅支持 YAML 子集，详见 chain-schema.md",
                      file=sys.stderr)
                sys.exit(1)

    chain = {}
    current_list_key = None  # 当前正在收集的列表键（steps, variables）
    current_list = []
    current_item = None
    current_sub_key = None  # 当前 list item 下的子字典键（如 input:）
    current_sub_indent = None  # 子字典键的缩进级别
    list_item_indent = None  # 列表项 "- " 的缩进级别

    for line in lines:
        # 去掉注释（不在引号内的 #）
        comment_pos = _find_comment(line)
        if comment_pos >= 0:
            line = line[:comment_pos]

        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        # 顶级 key: value（缩进=0）
        if indent == 0 and ':' in stripped:
            # 先保存之前的列表
            if current_list_key:
                if current_item:
                    current_list.append(current_item)
                    current_item = None
                if current_list:
                    chain[current_list_key] = current_list
                current_list = []
                current_list_key = None
                current_sub_key = None
                list_item_indent = None

            key, val = _split_kv(stripped)
            if val == '':
                current_list_key = key
                current_list = []
                current_item = None
            else:
                chain[key] = _clean_value(val)
            continue

        # 列表项起始（"- "）
        if current_list_key and stripped.startswith('- '):
            if current_item:
                current_list.append(current_item)
            current_sub_key = None
            list_item_indent = indent
            item_content = stripped[2:].strip()
            if ':' in item_content:
                key, val = _split_kv(item_content)
                current_item = {key: _clean_value(val)}
            else:
                current_item = _clean_value(item_content)
                current_list.append(current_item)
                current_item = None
            continue

        # 列表项的子属性（在 "- " 之后的缩进行）
        if current_list_key and current_item and isinstance(current_item, dict):
            if ':' in stripped:
                key, val = _split_kv(stripped)
                val = _clean_value(val)

                # inline dict
                if isinstance(val, str) and val.startswith('{') and val.endswith('}'):
                    val = _parse_inline_dict(val)
                    current_item[key] = val
                    current_sub_key = None
                    current_sub_indent = None
                elif val == '':
                    # 空值 = 开始一个子字典（如 input:）
                    current_sub_key = key
                    current_sub_indent = indent
                    current_item[key] = {}
                else:
                    # 检查是否属于当前的子字典
                    if current_sub_key and current_sub_indent is not None and indent > current_sub_indent:
                        # 缩进比子字典键更深，属于子字典
                        current_item[current_sub_key][key] = val
                    else:
                        # 同级或更浅缩进，属于列表项直接属性
                        current_item[key] = val
                        current_sub_key = None
                        current_sub_indent = None
            continue

    # 保存最后一个列表
    if current_list_key:
        if current_item:
            current_list.append(current_item)
        chain[current_list_key] = current_list

    # 验证必填字段
    if 'name' not in chain:
        print("❌ Chain file missing required field: 'name'", file=sys.stderr)
        sys.exit(1)
    if 'steps' not in chain or not chain['steps']:
        print("❌ Chain has no steps defined", file=sys.stderr)
        sys.exit(1)

    return chain


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
            return i
    return -1


def _split_kv(s):
    """分割 key: value。"""
    idx = s.index(':')
    key = s[:idx].strip()
    val = s[idx + 1:].strip()
    return key, val


def _clean_value(val):
    """清理值：去引号，识别布尔值和 null。"""
    if not val:
        return val
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    # 布尔值识别
    if val.lower() == 'true':
        return True
    if val.lower() == 'false':
        return False
    if val.lower() == 'null' or val == '~':
        return None
    return val


def _parse_inline_dict(s):
    """解析 inline dict：{key: value, key2: value2}。"""
    s = s.strip('{}').strip()
    result = {}
    for pair in s.split(','):
        pair = pair.strip()
        if ':' in pair:
            k, v = _split_kv(pair)
            result[k] = _clean_value(v)
    return result


# -------------------------------------------------------------------
# IO 匹配模块（T3，从 verify-chain.py 提取并升级）
# -------------------------------------------------------------------

def parse_frontmatter(filepath):
    """解析 SKILL.md 的 YAML frontmatter，提取 io 字段。

    直接复用 verify-chain.py 的实现。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None

    fm_text = match.group(1)

    if "\nio:" not in f"\n{fm_text}":
        return None

    io_data = {"input": [], "output": []}
    current_section = None
    current_item = None

    in_io_block = False
    for line in fm_text.split("\n"):
        stripped = line.strip()

        if stripped == "io:":
            in_io_block = True
            continue

        if not in_io_block:
            continue

        if stripped and not line.startswith(" ") and not line.startswith("\t"):
            break

        if stripped == "input:":
            current_section = "input"
            continue
        elif stripped == "output:":
            current_section = "output"
            continue

        if current_section and stripped.startswith("- type:"):
            type_val = stripped.replace("- type:", "").strip()
            current_item = {"type": type_val}
            io_data[current_section].append(current_item)
        elif current_section and current_item and stripped.startswith("description:"):
            current_item["description"] = stripped.replace("description:", "").strip()
        elif current_section and current_item and stripped.startswith("required:"):
            current_item["required"] = stripped.replace("required:", "").strip() == "true"
        elif current_section and current_item and stripped.startswith("path_pattern:"):
            val = stripped.replace("path_pattern:", "").strip().strip('"').strip("'")
            current_item["path_pattern"] = val

    return io_data


def load_compatibility_rules(skills_dir, type_registry_path=None):
    """从 type-registry.json 动态加载类型兼容规则。

    查找路径（优先级）：
    1. type_registry_path 参数指定
    2. skills_dir/.system/io-contracts/type-registry.json
    3. 内置回退值
    """
    paths_to_try = []
    if type_registry_path:
        paths_to_try.append(type_registry_path)
    paths_to_try.append(
        os.path.join(skills_dir, ".system", "io-contracts", "type-registry.json")
    )

    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
                rules = {}
                for rule in registry.get('compatibility_rules', []):
                    rules[rule['from']] = rule['to']
                return rules, path
            except (json.JSONDecodeError, KeyError):
                continue

    return BUILTIN_COMPATIBILITY_RULES, "(builtin fallback)"


def check_type_match(output_type, input_types, compat_rules):
    """检查 output_type 是否匹配 input_types 中的任何一个。

    返回 (matched, match_kind, matched_type)
    """
    # 精确匹配
    if output_type in input_types:
        return True, "exact", output_type

    # 兼容匹配
    compatible = compat_rules.get(output_type, [])
    for inp_type in input_types:
        if inp_type in compatible:
            return True, "compatible", inp_type

    return False, "none", None


# -------------------------------------------------------------------
# 链式执行器（T4）
# -------------------------------------------------------------------

def cmd_validate(args):
    """验证编排链的 IO 类型匹配。"""
    chain_file = args['chain_file']
    skills_dir = args.get('skills_dir', DEFAULT_SKILLS_DIR)
    type_registry = args.get('type_registry')

    chain = parse_chain_yaml(chain_file)
    compat_rules, registry_source = load_compatibility_rules(skills_dir, type_registry)

    print(f"═══ 验证编排链: {chain['name']} ═══")
    print(f"描述: {chain.get('description', '(无)')}")
    print(f"类型注册表: {registry_source}")
    print()

    steps = chain['steps']
    skill_ios = {}
    all_found = True

    # 加载所有 skill 的 IO 声明
    for i, step in enumerate(steps):
        skill_name = step.get('skill', '')
        skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")

        if not os.path.exists(skill_path):
            print(f"  ❌ Step {i+1}: skill 不存在: {skill_name}")
            all_found = False
            continue

        io_data = parse_frontmatter(skill_path)
        if io_data is None:
            print(f"  ⚠️  Step {i+1}: skill 无 IO 声明: {skill_name}")
            all_found = False
            continue

        skill_ios[i] = io_data
        input_types = [inp["type"] for inp in io_data["input"]]
        output_types = [out["type"] for out in io_data["output"]]
        print(f"  📋 Step {i+1}: {skill_name}")
        print(f"     input:  {input_types}")
        print(f"     output: {output_types}")

    if not all_found:
        print(f"\n  ❌ 编排链验证失败：部分 skill 缺失或无 IO 声明")
        sys.exit(1)

    # 验证相邻 skill 的 IO 匹配
    print(f"\n  --- 匹配检查 ---")
    all_matched = True

    for i in range(len(steps) - 1):
        current_io = skill_ios.get(i)
        next_io = skill_ios.get(i + 1)

        if not current_io or not next_io:
            continue

        current_output = current_io["output"]
        next_input = next_io["input"]

        if not current_output:
            print(f"  ❌ Step {i+1} ({steps[i]['skill']}) 没有声明 output")
            all_matched = False
            continue

        output_type = current_output[0]["type"]
        input_types = [inp["type"] for inp in next_input]

        matched, match_kind, matched_type = check_type_match(
            output_type, input_types, compat_rules
        )

        if matched:
            icon = "✅" if match_kind == "exact" else "🔄"
            kind_label = "精确匹配" if match_kind == "exact" else "兼容匹配"
            print(f"  {icon} Step {i+1} [{output_type}] → Step {i+2} [{matched_type}] ({kind_label})")
        else:
            print(f"  ❌ Step {i+1} [{output_type}] → Step {i+2} {input_types} (类型不匹配！)")
            all_matched = False

    # 总结
    total = len(steps)
    if all_matched:
        passed = total - 1 if total > 1 else 0
        print(f"\n═══ 验证结果: {passed}/{passed} 步 IO 匹配通过 ═══")
    else:
        print(f"\n═══ 验证失败 ═══")
        sys.exit(1)


def cmd_plan(args):
    """输出带变量替换的分步执行指引。"""
    chain_file = args['chain_file']
    skills_dir = args.get('skills_dir', DEFAULT_SKILLS_DIR)
    variables = args.get('variables', {})
    type_registry = args.get('type_registry')

    chain = parse_chain_yaml(chain_file)
    compat_rules, registry_source = load_compatibility_rules(skills_dir, type_registry)

    # 检查 required 变量
    for var_def in chain.get('variables', []):
        var_name = var_def.get('name', '') if isinstance(var_def, dict) else str(var_def)
        required = var_def.get('required', True) if isinstance(var_def, dict) else True
        if required and var_name not in variables:
            print(f"❌ 缺少必填变量: ${var_name}", file=sys.stderr)
            if isinstance(var_def, dict) and 'description' in var_def:
                print(f"   说明: {var_def['description']}", file=sys.stderr)
            sys.exit(1)

    steps = chain['steps']
    print(f"═══ 编排链: {chain['name']} ═══")
    print(f"描述: {chain.get('description', '(无)')}")
    print()

    for i, step in enumerate(steps):
        skill_name = step.get('skill', '')
        print(f"Step {i+1}/{len(steps)}: {skill_name}")

        # 处理输入（变量替换）
        input_params = step.get('input', {})
        if isinstance(input_params, dict):
            for key, val in input_params.items():
                display_val = _substitute_variables(str(val), variables)
                print(f"  输入: {key} = {display_val}")
        elif input_params:
            print(f"  输入: {_substitute_variables(str(input_params), variables)}")

        # 输出（也需要变量替换）
        output = step.get('output', '')
        if output:
            display_output = _substitute_variables(str(output), variables)
            print(f"  输出: {display_output}")

        # IO 匹配检查
        if i < len(steps) - 1:
            skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
            next_skill = steps[i + 1].get('skill', '')
            next_path = os.path.join(skills_dir, next_skill, "SKILL.md")

            current_io = parse_frontmatter(skill_path) if os.path.exists(skill_path) else None
            next_io = parse_frontmatter(next_path) if os.path.exists(next_path) else None

            if current_io and next_io and current_io["output"]:
                output_type = current_io["output"][0]["type"]
                input_types = [inp["type"] for inp in next_io["input"]]
                matched, match_kind, matched_type = check_type_match(
                    output_type, input_types, compat_rules
                )
                if matched:
                    icon = "✅" if match_kind == "exact" else "🔄"
                    kind_label = "精确匹配" if match_kind == "exact" else "兼容匹配"
                    print(f"  IO 匹配: {icon} ({output_type} → {matched_type}, {kind_label})")
                else:
                    print(f"  IO 匹配: ❌ ({output_type} → {input_types}, 类型不匹配)")
            elif not current_io:
                print(f"  IO 匹配: ⚠️ (skill 无 IO 声明)")
        print()

    print(f"═══ 执行计划生成完成（共 {len(steps)} 步）═══")


def cmd_list(args):
    """列出所有已注册的编排链。"""
    chains_dir = args.get('chains_dir')
    if not chains_dir:
        skills_dir = args.get('skills_dir', DEFAULT_SKILLS_DIR)
        chains_dir = os.path.join(skills_dir, "agent-orchestrator", "chains")

    if not os.path.isdir(chains_dir):
        print(f"❌ Chains directory not found: {chains_dir}", file=sys.stderr)
        sys.exit(1)

    yaml_files = sorted(glob.glob(os.path.join(chains_dir, "*.yaml")))
    if not yaml_files:
        print("(无已注册的编排链)")
        return

    print(f"═══ 已注册的编排链（{len(yaml_files)} 条）═══\n")
    for yf in yaml_files:
        try:
            chain = parse_chain_yaml(yf)
            steps = chain.get('steps', [])
            skill_names = [s.get('skill', '?') for s in steps if isinstance(s, dict)]
            chain_flow = " → ".join(skill_names)
            print(f"  📋 {chain['name']}")
            print(f"     {chain.get('description', '(无描述)')}")
            print(f"     {chain_flow}")
            print()
        except SystemExit:
            print(f"  ⚠️ 解析失败: {os.path.basename(yf)}")
            print()


def _substitute_variables(s, variables):
    """替换 $VAR 变量。"""
    for key, val in variables.items():
        s = s.replace(f"${key}", val)
    return s


# -------------------------------------------------------------------
# CLI 入口
# -------------------------------------------------------------------

def parse_args():
    """解析命令行参数（不依赖 argparse 以外的库）。"""
    args = sys.argv[1:]

    if not args or '--version' in args or '--help' in args or '-h' in args:
        if '--version' in args:
            print(f"run-chain.py v{__version__}")
            sys.exit(0)
        print_usage()
        sys.exit(0)

    command = args[0]
    result = {'command': command}

    if command in ('validate', 'plan'):
        if len(args) < 2:
            print(f"❌ {command} 需要指定链文件路径", file=sys.stderr)
            sys.exit(1)
        result['chain_file'] = args[1]

    # 解析可选参数
    i = 2 if command in ('validate', 'plan') else 1
    variables = {}
    while i < len(args):
        if args[i] == '--skills-dir' and i + 1 < len(args):
            result['skills_dir'] = args[i + 1]
            i += 2
        elif args[i] == '--chains-dir' and i + 1 < len(args):
            result['chains_dir'] = args[i + 1]
            i += 2
        elif args[i] == '--type-registry' and i + 1 < len(args):
            result['type_registry'] = args[i + 1]
            i += 2
        elif args[i] == '--var' and i + 1 < len(args):
            kv = args[i + 1]
            if '=' in kv:
                k, v = kv.split('=', 1)
                variables[k] = v
            i += 2
        else:
            i += 1

    if variables:
        result['variables'] = variables

    return result


def print_usage():
    """打印使用说明。"""
    print(f"""run-chain.py v{__version__} — 线性链式 Skill 编排器

用法:
  python3 run-chain.py validate <chain.yaml> [选项]
  python3 run-chain.py plan <chain.yaml> --var KEY=VALUE [选项]
  python3 run-chain.py list [选项]
  python3 run-chain.py --version

命令:
  validate   验证编排链的 IO 类型匹配
  plan       输出带变量替换的分步执行指引
  list       列出所有已注册的编排链

选项:
  --skills-dir DIR      Skills 目录（默认: ~/.ai-skills）
  --chains-dir DIR      Chains 目录（list 命令用）
  --type-registry PATH  type-registry.json 路径
  --var KEY=VALUE       设置变量（plan 命令用，可多次使用）
  --version             显示版本号
""")


def main():
    args = parse_args()
    command = args['command']

    if command == 'validate':
        cmd_validate(args)
    elif command == 'plan':
        cmd_plan(args)
    elif command == 'list':
        cmd_list(args)
    else:
        print(f"❌ 未知命令: {command}", file=sys.stderr)
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
