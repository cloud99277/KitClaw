#!/bin/bash
#
# sync-to-brain.sh - 将规则同步到大脑知识库
# 功能：从对话中提取规则，智能分类，更新 JSON 和 Markdown 文件
#

set -euo pipefail

# 配置路径
BRAIN_DIR="${BRAIN_DIR:-$HOME/.ai-memory/brain}"
JSON_FILE="$BRAIN_DIR/rules.json"
MARKDOWN_FILE="$BRAIN_DIR/rules.md"
LOG_FILE="$BRAIN_DIR/sync.log"

# 分类关键词映射
declare -A CATEGORY_KEYWORDS=(
    ["language"]="语法 语言特性 语法规则 关键字 变量 函数 类型 变量声明 常量 表达式"
    ["framework"]="框架 库 依赖 包管理器 npm yarn pnpm composer pip cargo go.mod"
    ["pattern"]="模式 设计模式 最佳实践 规范 代码风格 重构 性能优化 安全"
    ["projects"]="项目 结构 目录 组织 配置 构建 部署 CI/CD 测试"
)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

# 检查工具
JQ_AVAILABLE=false
if command -v jq &> /dev/null; then
    JQ_AVAILABLE=true
fi

PYTHON_AVAILABLE=false
if command -v python3 &> /dev/null; then
    PYTHON_AVAILABLE=true
fi

# 创建大脑目录和基础文件
init_brain() {
    mkdir -p "$BRAIN_DIR"

    if [[ ! -f "$JSON_FILE" ]]; then
        cat > "$JSON_FILE" << 'EOF'
{
  "version": "1.0",
  "updated_at": "",
  "categories": {
    "language": [],
    "framework": [],
    "pattern": [],
    "projects": []
  },
  "total_rules": 0
}
EOF
        log "Created brain JSON file: $JSON_FILE"
    fi

    if [[ ! -f "$MARKDOWN_FILE" ]]; then
        cat > "$MARKDOWN_FILE" << 'EOF'
# 大脑知识库规则

> 自动同步的规则、最佳实践和经验总结

## 更新日志

- 初始版本

---

## 语言特性 (Language)

> 与编程语言语法和特性相关的规则

*暂无规则*

## 框架与库 (Framework)

> 框架、库和依赖管理相关的规则

*暂无规则*

## 设计模式与最佳实践 (Pattern)

> 代码模式、设计原则和最佳实践

*暂无规则*

## 项目结构 (Projects)

> 项目组织、构建和部署相关的规则

*暂无规则*

---
*最后更新: 等待同步*
EOF
        log "Created brain Markdown file: $MARKDOWN_FILE"
    fi
}

# 智能分类规则
categorize_rule() {
    local content="$1"
    local category="pattern"

    content_lower=$(echo "$content" | tr '[:upper:]' '[:lower:]')

    for cat in language framework pattern projects; do
        keywords=${CATEGORY_KEYWORDS[$cat]}
        for keyword in $keywords; do
            if [[ "$content_lower" == *"$keyword"* ]]; then
                category="$cat"
                break 2
            fi
        done
    done

    echo "$category"
}

# 使用 Python 处理 JSON
python_json_op() {
    local op="$1"      # "add" or "exists"
    local category="$2"
    local content="$3"

    python3 - "$JSON_FILE" "$category" "$content" "$op" << 'PYEOF'
import sys
import json

json_file = sys.argv[1]
category = sys.argv[2]
content = sys.argv[3]
op = sys.argv[4]

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

if op == 'exists':
    for rule in data.get('categories', {}).get(category, []):
        if rule.get('content') == content:
            sys.exit(0)
    sys.exit(1)
elif op == 'add':
    import datetime
    timestamp = datetime.datetime.now().isoformat()
    rule_id = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    new_rule = {
        "id": rule_id,
        "content": content,
        "source": "会话历史",
        "added_at": timestamp
    }

    data['updated_at'] = timestamp
    data['categories'].setdefault(category, []).append(new_rule)
    data['total_rules'] = sum(len(v) for v in data['categories'].values())

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
PYEOF
}

# 检查规则是否存在
rule_exists() {
    local category="$1"
    local content="$2"

    if [[ -f "$JSON_FILE" ]]; then
        if [[ "$JQ_AVAILABLE" == "true" ]]; then
            if jq -e ".categories[\"$category\"] | any(.content == \"$content\")" "$JSON_FILE" 2>/dev/null | grep -q true; then
                return 0
            fi
        elif [[ "$PYTHON_AVAILABLE" == "true" ]]; then
            python_json_op "exists" "$category" "$content" && return 0
        else
            if grep -qF "\"content\": \"$content\"" "$JSON_FILE"; then
                return 0
            fi
        fi
    fi
    return 1
}

# 更新 JSON 文件
update_json() {
    local category="$1"
    local content="$2"
    local source="${3:-会话历史}"

    if [[ "$JQ_AVAILABLE" == "true" ]]; then
        local timestamp=$(date -Iseconds)
        jq --arg category "$category" \
           --arg content "$content" \
           --arg source "$source" \
           --arg timestamp "$timestamp" \
           '
           .updated_at = $timestamp |
           .categories[$category] += [{
               "id": (now | strftime("%Y%m%d%H%M%S")),
               "content": $content,
               "source": $source,
               "added_at": $timestamp
           }] |
           .total_rules = ([.categories[]] | map(length) | add)
           ' "$JSON_FILE" > "${JSON_FILE}.tmp" && mv "${JSON_FILE}.tmp" "$JSON_FILE"
    elif [[ "$PYTHON_AVAILABLE" == "true" ]]; then
        python_json_op "add" "$category" "$content"
    else
        warn "No JSON parser available"
    fi

    log "Updated JSON: category=$category"
}

# 更新 Markdown 文件
update_markdown() {
    local category="$1"
    local content="$2"

    local timestamp=$(date -Iseconds)
    local category_cn=""

    case "$category" in
        language) category_cn="语言特性 (Language)" ;;
        framework) category_cn="框架与库 (Framework)" ;;
        pattern) category_cn="设计模式与最佳实践 (Pattern)" ;;
        projects) category_cn="项目结构 (Projects)" ;;
    esac

    # 使用 Python 写入更安全
    if [[ "$PYTHON_AVAILABLE" == "true" ]]; then
        python3 - "$MARKDOWN_FILE" "$category_cn" "$content" "$timestamp" << 'PYEOF'
import sys

md_file = sys.argv[1]
category_cn = sys.argv[2]
content = sys.argv[3]
timestamp = sys.argv[4]

with open(md_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_entry = f"- **规则**: {content}\n  - **来源**: 会话历史\n  - **时间**: {timestamp}\n\n"

output = []
i = 0
in_category = False
added = False

while i < len(lines):
    line = lines[i]
    output.append(line)

    if line.strip() == f"## {category_cn}":
        in_category = True
    elif in_category and not added:
        # 检查是否是第一个规则（当前是暂无规则或空行）
        if "*暂无规则*" in line or line.strip() == "":
            # 跳过占位符
            output.pop()
            # 找到下一个分类标题或分隔符
            while i + 1 < len(lines) and not (lines[i+1].strip().startswith("## ") or lines[i+1].strip().startswith("---")):
                i += 1
            output.append(new_entry)
            added = True
        elif line.strip() and not line.startswith(">") and not line.startswith("-"):
            # 找到下一个分类标题前插入
            output.append(new_entry)
            added = True

    i += 1

if not added:
    # 追加到分类标题后
    for idx, line in enumerate(output):
        if line.strip() == f"## {category_cn}":
            output.insert(idx + 1, new_entry)
            break

# 更新时间戳
output = [line if "*最后更新*" not in line else f"*最后更新: {timestamp}*\n" for line in output]

with open(md_file, 'w', encoding='utf-8') as f:
    f.writelines(output)
PYEOF
    else
        # 纯 bash 方式
        local escaped_content=$(echo "$content" | sed 's/&/\\&/g; s/\//\\//g')
        local new_entry="- **规则**: $escaped_content
  - **来源**: 会话历史
  - **时间**: $timestamp"
        sed -i "/^## $category_cn$/a\\
\\
$new_entry" "$MARKDOWN_FILE"
        sed -i "s/\*最后更新:.*/\*最后更新: $timestamp\*/" "$MARKDOWN_FILE"
    fi

    log "Updated Markdown: category=$category"
}

# 从会话历史提取规则
extract_from_history() {
    local history_file="${CLAUDE_HISTORY_FILE:-}"

    if [[ -n "$history_file" && -f "$history_file" ]]; then
        if [[ "$JQ_AVAILABLE" == "true" ]]; then
            tail -100 "$history_file" 2>/dev/null | jq -r '.[] | select(.role == "user") | .content' 2>/dev/null | tail -20
        elif [[ "$PYTHON_AVAILABLE" == "true" ]]; then
            python3 - "$history_file" << 'PYEOF' 2>/dev/null
import sys
import json

hf = sys.argv[1]
try:
    with open(hf, 'r') as f:
        data = json.load(f)
    for msg in data[-20:]:
        if msg.get('role') == 'user':
            print(msg.get('content', ''))
except:
    pass
PYEOF
        else
            grep -A 5 '"role": "user"' "$history_file" 2>/dev/null | grep '"content"' | sed 's/.*"content": "//; s/"$//'
        fi
    else
        echo "${LAST_USER_MESSAGE:-${CLAUDE_LAST_USER_MSG:-}}"
    fi
}

# 主函数
main() {
    local category=""
    local content=""
    local force="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --category|-c)
                category="$2"
                shift 2
                ;;
            --content|-m)
                content="$2"
                shift 2
                ;;
            --force|-f)
                force="true"
                shift
                ;;
            --help|-h)
                echo "用法: sync-to-brain [选项]"
                echo ""
                echo "选项:"
                echo "  --category, -c <分类>    规则分类: language, framework, pattern, projects"
                echo "  --content, -m <内容>     要同步的规则内容"
                echo "  --force, -f             强制同步，忽略重复检查"
                echo "  --help, -h               显示帮助信息"
                echo ""
                echo "示例:"
                echo "  sync-to-brain -c pattern -m '始终使用绝对路径'"
                echo "  sync-to-brain -m '使用绝对路径避免相对路径问题'"
                exit 0
                ;;
            *)
                content="$1"
                shift
                ;;
        esac
    done

    init_brain

    if [[ -z "$content" ]]; then
        content=$(extract_from_history)
        if [[ -z "$content" ]]; then
            error "未提供规则内容，且无法从会话历史提取。请使用 --content 参数指定。"
        fi
        log "从会话历史提取内容: ${content:0:100}..."
    fi

    content=$(echo "$content" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//; s/^["'"'"']//; s/["'"'"']$//')

    if [[ -z "$category" ]]; then
        category=$(categorize_rule "$content")
        log "智能分类结果: $category"
    fi

    if [[ ! "$category" =~ ^(language|framework|pattern|projects|all)$ ]]; then
        error "无效的分类: $category"
    fi

    if [[ "$category" == "all" ]]; then
        category="pattern"
    fi

    if [[ "$force" != "true" ]] && rule_exists "$category" "$content"; then
        warn "规则已存在，跳过: ${content:0:50}..."
        echo "规则已存在于大脑知识库中。"
        exit 0
    fi

    log "同步规则到 $category..."
    update_json "$category" "$content"
    update_markdown "$category" "$content"

    echo ""
    echo "========================================"
    echo -e "${GREEN}成功同步规则到大脑知识库${NC}"
    echo "----------------------------------------"
    echo "分类: $category"
    echo "内容: ${content:0:100}${content:+...}"
    echo "----------------------------------------"
    echo "JSON 文件: $JSON_FILE"
    echo "Markdown 文件: $MARKDOWN_FILE"
    echo "========================================"

    log "Sync completed successfully"
}

main "$@"
