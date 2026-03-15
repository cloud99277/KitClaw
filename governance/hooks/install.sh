#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK_SOURCE="$REPO_ROOT/governance/hooks/pre-commit"
HOOK_TARGET="$REPO_ROOT/.git/hooks/pre-commit"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
    echo "❌ Not a git repository: $REPO_ROOT" >&2
    exit 1
fi

mkdir -p "$(dirname "$HOOK_TARGET")"
cp "$HOOK_SOURCE" "$HOOK_TARGET"
chmod +x "$HOOK_TARGET"

echo "✅ Installed pre-commit hook → $HOOK_TARGET"
echo "   Re-run this script after updating governance/hooks/pre-commit."
