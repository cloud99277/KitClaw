#!/usr/bin/env bash
# knowledge-search.sh — Agent 知识库检索 Wrapper
# 
# 用法:
#   bash knowledge-search.sh "查询文本" [--preset coding|audit|qa|fast] [--top N] [--scope S] [--tags T] [--mode M]
#
# 功能:
#   1. preset 快速配置
#   2. 标准化 JSON 输出（schema_version + query metadata）
#   3. 优先使用项目 venv 的 Python
#   4. 错误处理

set -euo pipefail

# ---------- 路径配置 ----------

# 解析真实路径（跟随软链接）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 查找 knowledge_search.py 的位置
# 优先级: 环境变量 > 项目 src/rag/ > 同级目录
if [[ -n "${KNOWLEDGE_SEARCH_PY:-}" ]] && [[ -f "$KNOWLEDGE_SEARCH_PY" ]]; then
    SEARCH_PY="$KNOWLEDGE_SEARCH_PY"
elif [[ -f "$SKILL_DIR/../../rag-engine/knowledge_search.py" ]]; then
    SEARCH_PY="$(cd "$SKILL_DIR/../../rag-engine" && pwd)/knowledge_search.py"
else
    echo '{"schema_version":"1.0","error":"knowledge_search.py not found. Set KNOWLEDGE_SEARCH_PY or install from project root."}' >&2
    exit 1
fi

PROJECT_DIR="$(cd "$SKILL_DIR/../.." && pwd)"

# ---------- Python 路径 ----------

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    PYTHON_BIN="python3"
elif [[ -x "$PROJECT_DIR/.venv/bin/python3" ]]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

# ---------- 参数解析 ----------

QUERY=""
PRESET=""
MODE=""
TOP=""
SCOPE=""
TAGS=""
AUTHOR=""
AFTER=""
DB_PATH=""
DEBUG=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --preset)
            PRESET="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --top)
            TOP="$2"
            shift 2
            ;;
        --scope)
            SCOPE="$2"
            shift 2
            ;;
        --tags)
            TAGS="$2"
            shift 2
            ;;
        --author)
            AUTHOR="$2"
            shift 2
            ;;
        --after)
            AFTER="$2"
            shift 2
            ;;
        --db-path)
            DB_PATH="$2"
            shift 2
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --help|-h)
            echo "Usage: knowledge-search.sh \"query\" [--preset coding|audit|qa|fast] [options]"
            echo ""
            echo "Presets:"
            echo "  coding  - hybrid, top 3, scope=dev (架构决策查询)"
            echo "  audit   - hybrid, top 5, scope=dev (历史调研对比)"
            echo "  qa      - hybrid, top 10 (广泛搜索)"
            echo "  fast    - fts, top 5 (快速关键词匹配)"
            echo ""
            echo "Options:"
            echo "  --mode vector|fts|hybrid  搜索模式"
            echo "  --top N                   返回结果数"
            echo "  --scope S                 按 scope 过滤"
            echo "  --tags T                  按 tags 过滤 (逗号分隔)"
            echo "  --author A                按 author 过滤"
            echo "  --after YYYY-MM-DD        按日期过滤"
            echo "  --db-path PATH            指定 LanceDB 索引目录"
            echo "  --debug                   透传 debug 模式"
            exit 0
            ;;
        -*)
            echo "{\"schema_version\":\"1.0\",\"error\":\"Unknown option: $1\"}" >&2
            exit 1
            ;;
        *)
            if [[ -z "$QUERY" ]]; then
                QUERY="$1"
            else
                echo "{\"schema_version\":\"1.0\",\"error\":\"Multiple queries not supported\"}" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$QUERY" ]]; then
    echo "{\"schema_version\":\"1.0\",\"error\":\"Query is required. Usage: knowledge-search.sh \\\"query\\\" [--preset coding|audit|qa|fast]\"}" >&2
    exit 1
fi

# ---------- preset 配置 ----------

case "${PRESET:-}" in
    coding)
        MODE="${MODE:-hybrid}"
        TOP="${TOP:-3}"
        SCOPE="${SCOPE:-dev}"
        ;;
    audit)
        MODE="${MODE:-hybrid}"
        TOP="${TOP:-5}"
        SCOPE="${SCOPE:-dev}"
        ;;
    qa)
        MODE="${MODE:-hybrid}"
        TOP="${TOP:-10}"
        ;;
    fast)
        MODE="${MODE:-fts}"
        TOP="${TOP:-5}"
        ;;
    "")
        MODE="${MODE:-hybrid}"
        TOP="${TOP:-5}"
        ;;
    *)
        echo "{\"schema_version\":\"1.0\",\"error\":\"Unknown preset: $PRESET. Valid: coding, audit, qa, fast\"}" >&2
        exit 1
        ;;
esac

# ---------- 构建 CLI 参数 ----------

CLI_ARGS=("$QUERY" --json --mode "$MODE" --top "$TOP")

if [[ -n "${SCOPE:-}" ]]; then
    CLI_ARGS+=(--scope "$SCOPE")
fi
if [[ -n "${TAGS:-}" ]]; then
    CLI_ARGS+=(--tags "$TAGS")
fi
if [[ -n "${AUTHOR:-}" ]]; then
    CLI_ARGS+=(--author "$AUTHOR")
fi
if [[ -n "${AFTER:-}" ]]; then
    CLI_ARGS+=(--after "$AFTER")
fi
if [[ -n "${DB_PATH:-}" ]]; then
    CLI_ARGS+=(--db-path "$DB_PATH")
fi
if [[ "$DEBUG" == "true" ]]; then
    CLI_ARGS+=(--debug)
fi

# ---------- 执行搜索 ----------

ERR_FILE=$(mktemp)
set +e
RAW_OUTPUT=$("$PYTHON_BIN" "$SEARCH_PY" "${CLI_ARGS[@]}" 2>"$ERR_FILE")
EXIT_CODE=$?
set -e

if [[ $EXIT_CODE -ne 0 ]]; then
    "$PYTHON_BIN" - "$QUERY" "$EXIT_CODE" "$ERR_FILE" <<'PY' >&2
import json
from pathlib import Path
import sys

query = sys.argv[1]
exit_code = int(sys.argv[2])
err_file = Path(sys.argv[3])
message = err_file.read_text(encoding="utf-8").strip()
if not message:
    message = f"Search failed (exit code: {exit_code})"

print(json.dumps({
    "schema_version": "1.0",
    "error": message,
    "query": query,
}, ensure_ascii=False))
PY
    rm -f "$ERR_FILE"
    exit $EXIT_CODE
fi
rm -f "$ERR_FILE"

# ---------- 标准化 JSON 输出 ----------

# 使用 Python 包装标准化 JSON（避免依赖 jq）
"$PYTHON_BIN" -c "
import json, sys

try:
    raw = json.loads(sys.stdin.read())
except Exception:
    raw = []

output = {
    'schema_version': '1.0',
    'query': sys.argv[1],
    'mode': sys.argv[2],
    'preset': sys.argv[3],
    'total_results': len(raw) if isinstance(raw, list) else 0,
    'results': raw if isinstance(raw, list) else []
}
print(json.dumps(output, ensure_ascii=False, indent=2))
" "$QUERY" "$MODE" "${PRESET:-default}" <<< "$RAW_OUTPUT"

# ---------- 审计日志（可选） ----------

if [[ "${AUDIT_LOG:-false}" == "true" ]]; then
    AUDIT_DIR="$HOME/.ai-skills/.logs"
    AUDIT_FILE="$AUDIT_DIR/search-audit.jsonl"
    mkdir -p "$AUDIT_DIR"

    # 计算结果数
    RESULT_COUNT=$("$PYTHON_BIN" -c "
import json, sys
try:
    raw = json.loads(sys.stdin.read())
    print(len(raw) if isinstance(raw, list) else 0)
except:
    print(0)
" <<< "$RAW_OUTPUT")

    # 写入 JSONL
    "$PYTHON_BIN" -c "
import json, sys
from datetime import datetime, timezone

entry = {
    'schema_version': '1.0',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'action': 'search',
    'agent': '${AUDIT_AGENT:-unknown}',
    'query': sys.argv[1],
    'preset': sys.argv[2],
    'scope': sys.argv[3] if sys.argv[3] != 'None' else None,
    'results_count': int(sys.argv[4]),
}
# 移除 None 值
entry = {k: v for k, v in entry.items() if v is not None}
print(json.dumps(entry, ensure_ascii=False))
" "$QUERY" "${PRESET:-default}" "${SCOPE:-None}" "$RESULT_COUNT" >> "$AUDIT_FILE"
fi
