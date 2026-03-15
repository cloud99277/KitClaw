#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/knowledge-base}"
PID_FILE="${HOME}/.ai-memory/obsidian-l3-watch.pid"
LOG_DIR="${HOME}/.ai-memory/logs"
LOG_FILE="${LOG_DIR}/obsidian-l3-watch.log"
SCRIPT="${HOME}/.ai-skills/memory-manager/scripts/watch-knowledge-base.py"
INSTALLER="${HOME}/.ai-skills/memory-manager/scripts/install-knowledge-watch-service.sh"
SERVICE_NAME="obsidian-l3-watch.service"

mkdir -p "${HOME}/.ai-memory" "${LOG_DIR}"

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active default.target >/dev/null 2>&1; then
  bash "${INSTALLER}" "${ROOT}" >/dev/null
  systemctl --user start "${SERVICE_NAME}"
  echo "obsidian-l3-watch started via systemd user service"
  echo "Service: ${SERVICE_NAME}"
  echo "Root: ${ROOT}"
  echo "Logs: journalctl --user -u ${SERVICE_NAME} -n 50 --no-pager"
  echo "File log: ${LOG_FILE}"
  exit 0
fi

if [[ -f "${PID_FILE}" ]]; then
  existing_pid="$(cat "${PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    echo "obsidian-l3-watch is already running"
    echo "PID: ${existing_pid}"
    echo "Log: ${LOG_FILE}"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

pid="$(
python3 - "${SCRIPT}" "${ROOT}" "${LOG_FILE}" <<'PY'
import subprocess
import sys

script, root, log_file = sys.argv[1:4]
with open(log_file, "ab", buffering=0) as log:
    proc = subprocess.Popen(
        ["python3", script, "--root", root],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
print(proc.pid)
PY
)"
echo "${pid}" >"${PID_FILE}"

echo "obsidian-l3-watch started"
echo "PID: ${pid}"
echo "Root: ${ROOT}"
echo "Log: ${LOG_FILE}"
