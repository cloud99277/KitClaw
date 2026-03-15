#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="obsidian-l3-watch.service"
LEGACY_SERVICE_NAME="knowledge-watch.service"
SERVICE_FILE="${HOME}/.config/systemd/user/${SERVICE_NAME}"
LEGACY_SERVICE_FILE="${HOME}/.config/systemd/user/${LEGACY_SERVICE_NAME}"
PID_FILE="${HOME}/.ai-memory/obsidian-l3-watch.pid"
LEGACY_PID_FILE="${HOME}/.ai-memory/knowledge-watch.pid"

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active default.target >/dev/null 2>&1; then
  systemctl --user stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
  systemctl --user disable "${SERVICE_NAME}" >/dev/null 2>&1 || true
  rm -f "${SERVICE_FILE}"
  systemctl --user stop "${LEGACY_SERVICE_NAME}" >/dev/null 2>&1 || true
  systemctl --user disable "${LEGACY_SERVICE_NAME}" >/dev/null 2>&1 || true
  rm -f "${LEGACY_SERVICE_FILE}"
  systemctl --user daemon-reload
  systemctl --user reset-failed "${SERVICE_NAME}" >/dev/null 2>&1 || true
  systemctl --user reset-failed "${LEGACY_SERVICE_NAME}" >/dev/null 2>&1 || true
fi

if [[ -f "${PID_FILE}" ]]; then
  existing_pid="$(cat "${PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    kill "${existing_pid}"
  fi
  rm -f "${PID_FILE}"
fi

if [[ -f "${LEGACY_PID_FILE}" ]]; then
  existing_pid="$(cat "${LEGACY_PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    kill "${existing_pid}"
  fi
  rm -f "${LEGACY_PID_FILE}"
fi

echo "obsidian-l3-watch service uninstalled"
echo "Service file removed: ${SERVICE_FILE}"
