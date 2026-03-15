#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${HOME}/.ai-memory/obsidian-l3-watch.pid"
LOG_FILE="${HOME}/.ai-memory/logs/obsidian-l3-watch.log"
SERVICE_NAME="obsidian-l3-watch.service"

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active default.target >/dev/null 2>&1; then
  if systemctl --user list-unit-files "${SERVICE_NAME}" --no-legend 2>/dev/null | grep -q "^${SERVICE_NAME}"; then
    active_state="$(systemctl --user is-active "${SERVICE_NAME}" 2>/dev/null || true)"
    enabled_state="$(systemctl --user is-enabled "${SERVICE_NAME}" 2>/dev/null || true)"
    echo "obsidian-l3-watch status: ${active_state:-unknown}"
    echo "Service: ${SERVICE_NAME}"
    echo "Enabled: ${enabled_state:-unknown}"
    echo "Journal: journalctl --user -u ${SERVICE_NAME} -n 50 --no-pager"
    echo "File log: ${LOG_FILE}"
    exit 0
  fi
fi

if [[ ! -f "${PID_FILE}" ]]; then
  echo "obsidian-l3-watch status: stopped"
  echo "Log: ${LOG_FILE}"
  exit 0
fi

pid="$(cat "${PID_FILE}")"

if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
  echo "obsidian-l3-watch status: running"
  echo "PID: ${pid}"
  echo "Log: ${LOG_FILE}"
else
  echo "obsidian-l3-watch status: stale pid file"
  echo "PID file: ${PID_FILE}"
  echo "Log: ${LOG_FILE}"
  exit 1
fi
