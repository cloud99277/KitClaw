#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/knowledge-base}"
SERVICE_NAME="obsidian-l3-watch.service"
LEGACY_SERVICE_NAME="knowledge-watch.service"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/${SERVICE_NAME}"
LEGACY_SERVICE_FILE="${SERVICE_DIR}/${LEGACY_SERVICE_NAME}"
PID_FILE="${HOME}/.ai-memory/obsidian-l3-watch.pid"
LEGACY_PID_FILE="${HOME}/.ai-memory/knowledge-watch.pid"
LOG_DIR="${HOME}/.ai-memory/logs"
LOG_FILE="${LOG_DIR}/obsidian-l3-watch.log"
WATCH_SCRIPT="${HOME}/.ai-skills/memory-manager/scripts/watch-knowledge-base.py"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found; cannot install stable obsidian-l3-watch service" >&2
  exit 1
fi

if ! systemctl --user is-active default.target >/dev/null 2>&1; then
  echo "systemd --user is not active; cannot install stable obsidian-l3-watch service" >&2
  exit 1
fi

mkdir -p "${SERVICE_DIR}" "${LOG_DIR}" "${HOME}/.ai-memory"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Obsidian L3 Knowledge Watcher
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 ${WATCH_SCRIPT} --root ${ROOT}
WorkingDirectory=${HOME}
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=5
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}

[Install]
WantedBy=default.target
EOF

if systemctl --user list-unit-files "${LEGACY_SERVICE_NAME}" --no-legend 2>/dev/null | grep -q "^${LEGACY_SERVICE_NAME}"; then
  systemctl --user stop "${LEGACY_SERVICE_NAME}" >/dev/null 2>&1 || true
  systemctl --user disable "${LEGACY_SERVICE_NAME}" >/dev/null 2>&1 || true
  rm -f "${LEGACY_SERVICE_FILE}"
fi

if [[ -f "${LEGACY_PID_FILE}" ]]; then
  existing_pid="$(cat "${LEGACY_PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    kill "${existing_pid}"
  fi
  rm -f "${LEGACY_PID_FILE}"
fi

if [[ -f "${PID_FILE}" ]]; then
  existing_pid="$(cat "${PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    kill "${existing_pid}"
  fi
  rm -f "${PID_FILE}"
fi

systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}" >/dev/null
systemctl --user restart "${SERVICE_NAME}"

echo "obsidian-l3-watch service installed"
echo "Service file: ${SERVICE_FILE}"
echo "Service: ${SERVICE_NAME}"
echo "Root: ${ROOT}"
echo "Log file: ${LOG_FILE}"
echo "Journal: journalctl --user -u ${SERVICE_NAME} -n 50 --no-pager"
