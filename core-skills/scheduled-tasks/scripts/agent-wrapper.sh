#!/bin/bash
# agent-wrapper.sh — Level 2 执行器
# 用法: agent-wrapper.sh <task.yaml> [--dry-run]
#
# 从 task-runner.py --extract-all 一次性获取所有字段，
# 然后调用对应的 agent CLI 执行智能任务。
#
# 执行完成后自动调用 skill-observability 记录日志。

set -euo pipefail

# --- 参数检查 ---
if [ $# -lt 1 ]; then
  echo "用法: agent-wrapper.sh <task.yaml> [--dry-run]"
  echo "  Level 2 定时任务执行器 — 调用 agent CLI 执行智能任务"
  exit 1
fi

TASK_FILE="$1"
DRY_RUN="${2:-}"
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${HOME}/.ai-skills"
LOG_DIR="${SKILLS_DIR}/.logs"

# --- 一次性提取所有字段 ---
TASK_JSON=$(python3 "$SCRIPTS_DIR/task-runner.py" "$TASK_FILE" --extract-all)
AGENT=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent',''))")
PROMPT=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('prompt',''))")
TASK_NAME=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))")
TIMEOUT=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('timeout_seconds',300))")
LEVEL=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('level',''))")

# --- 校验 Level ---
if [ "$LEVEL" != "2" ]; then
  echo "❌ agent-wrapper.sh 只执行 Level 2 任务。当前任务 Level: ${LEVEL}"
  echo "   Level 1 任务请使用 task-runner.py"
  exit 1
fi

# --- 设置完整环境（cron 环境 PATH 不完整是经典踩坑） ---
if [ -f "$HOME/.bashrc" ]; then
  source "$HOME/.bashrc" 2>/dev/null || true
fi
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export AGENT_SKILLS_DIR="$SKILLS_DIR"

# --- --dry-run 模式 ---
if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "[DRY-RUN] Task: ${TASK_NAME}"
  echo "[DRY-RUN] Level: 2"
  echo "[DRY-RUN] Agent: ${AGENT}"
  echo "[DRY-RUN] Prompt: ${PROMPT}"
  echo "[DRY-RUN] Timeout: ${TIMEOUT}s"
  case "$AGENT" in
    claude) echo "[DRY-RUN] Command: timeout ${TIMEOUT} claude -p \"${PROMPT}\"" ;;
    gemini) echo "[DRY-RUN] Command: timeout ${TIMEOUT} gemini -p \"${PROMPT}\"" ;;
    codex)  echo "[DRY-RUN] Command: timeout ${TIMEOUT} codex -q \"${PROMPT}\"" ;;
    *)      echo "[DRY-RUN] ERROR: Unknown agent: ${AGENT}" ;;
  esac
  exit 0
fi

# --- 执行 ---
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TASK_LOG="${LOG_DIR}/scheduled-${TASK_NAME}-${TIMESTAMP}.log"
mkdir -p "$LOG_DIR"

echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting Level 2 task: ${TASK_NAME} ===" >> "$TASK_LOG"
echo "Agent: ${AGENT}" >> "$TASK_LOG"

STATUS="success"

# 根据 agent 选择 CLI
case "$AGENT" in
  claude)
    timeout "${TIMEOUT:-300}" claude -p "$PROMPT" >> "$TASK_LOG" 2>&1 || STATUS="failure"
    ;;
  gemini)
    timeout "${TIMEOUT:-300}" gemini -p "$PROMPT" >> "$TASK_LOG" 2>&1 || STATUS="failure"
    ;;
  codex)
    timeout "${TIMEOUT:-300}" codex -q "$PROMPT" >> "$TASK_LOG" 2>&1 || STATUS="failure"
    ;;
  *)
    echo "ERROR: Unknown agent: ${AGENT}" >> "$TASK_LOG"
    STATUS="failure"
    ;;
esac

echo "=== [$(date -u +%Y-%m-%dT%H:%M:%SZ)] Task ${TASK_NAME} finished with status: ${STATUS} ===" >> "$TASK_LOG"

# --- 记录到 observability ---
python3 "$SKILLS_DIR/skill-observability/scripts/log-execution.py" \
  --skill "scheduled-tasks" \
  --agent "$AGENT" \
  --status "$STATUS" \
  --notes "Level 2 task: ${TASK_NAME}" 2>/dev/null || true

exit $( [ "$STATUS" = "success" ] && echo 0 || echo 1 )
