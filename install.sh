#!/usr/bin/env bash
# KitClaw Installer
# Usage: bash install.sh [--with-rag]
#
# Installs KitClaw core skills, initializes memory directories,
# and optionally sets up the RAG engine with its dependencies.

set -euo pipefail

KITCLAW_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${AI_SKILLS_DIR:-$HOME/.ai-skills}"
MEMORY_DIR="${AI_MEMORY_DIR:-$HOME/.ai-memory}"

echo "🐾 KitClaw Installer"
echo "   Skills dir: $SKILLS_DIR"
echo "   Memory dir: $MEMORY_DIR"
echo ""

# ---------- Step 1: Initialize ~/.ai-memory/ ----------

mkdir -p "$MEMORY_DIR"

if [[ ! -f "$MEMORY_DIR/whiteboard.json" ]]; then
    cp "$KITCLAW_DIR/templates/whiteboard.json" "$MEMORY_DIR/whiteboard.json"
    echo "✅ Created $MEMORY_DIR/whiteboard.json"
else
    echo "⏭️  $MEMORY_DIR/whiteboard.json already exists, skipping"
fi

if [[ ! -f "$MEMORY_DIR/config.json" ]]; then
    cp "$KITCLAW_DIR/templates/config.json" "$MEMORY_DIR/config.json"
    echo "✅ Created $MEMORY_DIR/config.json"
    echo "⚠️  Please edit $MEMORY_DIR/config.json to set your L3 knowledge base path"
else
    echo "⏭️  $MEMORY_DIR/config.json already exists, skipping"
fi

# ---------- Step 2: Symlink core-skills → ~/.ai-skills/ ----------

mkdir -p "$SKILLS_DIR"

for skill_dir in "$KITCLAW_DIR/core-skills/"*/; do
    skill_name=$(basename "$skill_dir")
    target="$SKILLS_DIR/$skill_name"

    if [[ -L "$target" ]]; then
        rm "$target"
    elif [[ -d "$target" ]]; then
        echo "⚠️  $target is an existing directory (not a symlink), skipping."
        echo "   If you want KitClaw to manage it, remove or rename it first."
        continue
    fi

    ln -s "$(realpath "$skill_dir")" "$target"
    echo "✅ Linked $skill_name → $target"
done

# ---------- Step 3: Create log directory ----------

mkdir -p "$SKILLS_DIR/.logs"
echo "✅ Log directory: $SKILLS_DIR/.logs/"

# ---------- Step 4: Optional — Install RAG engine dependencies ----------

if [[ "${1:-}" == "--with-rag" ]]; then
    echo ""
    echo "📦 Installing RAG engine dependencies..."
    if [[ ! -d "$KITCLAW_DIR/rag-engine/.venv" ]]; then
        python3 -m venv "$KITCLAW_DIR/rag-engine/.venv"
    fi
    "$KITCLAW_DIR/rag-engine/.venv/bin/pip" install -q -r "$KITCLAW_DIR/rag-engine/requirements.txt"
    echo "✅ RAG engine venv created at $KITCLAW_DIR/rag-engine/.venv/"
fi

# ---------- Done ----------

echo ""
echo "🎉 KitClaw installed successfully!"
echo ""
echo "Verify:"
echo "  python3 $SKILLS_DIR/memory-manager/scripts/memory-search.py --version"
echo ""
echo "Next steps:"
echo "  1. Edit $MEMORY_DIR/config.json to set your L3 knowledge base path"
echo "  2. Copy templates/AGENTS.md to ~/AGENTS.md and fill in your profile"
echo "  3. Read docs/memory-architecture.md to understand the L1/L2/L3 model"
