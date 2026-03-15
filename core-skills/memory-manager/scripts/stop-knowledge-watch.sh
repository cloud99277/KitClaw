#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${HOME}/.ai-memory/obsidian-l3-watch.pid"
SERVICE_NAME="obsidian-l3-watch.service"

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active default.target >/dev/null 2>&1; then
  if systemctl --user list-unit-files "${SERVICE_NAME}" --no-legend 2>/dev/null | grep -q "^${SERVICE_NAME}"; then
    systemctl --user stop "${SERVICE_NAME}"
    echo "obsidian-l3-watch stopped"
    echo "Service: ${SERVICE_NAME}"
    exit 0
  fi
fi

if [[ ! -f "${PID_FILE}" ]]; then
  echo "obsidian-l3-watch is not running"
  exit 0
fi

pid="$(cat "${PID_FILE}")"

if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
  kill "${pid}"
  echo "obsidian-l3-watch stopped"
  echo "PID: ${pid}"
else
  echo "obsidian-l3-watch pid file existed but process was not running"
fi

rm -f "${PID_FILE}"
