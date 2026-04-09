#!/usr/bin/env bash
# install.sh — knowledge-search Skill 安装脚本
# 创建 ~/.ai-skills/knowledge-search 软链接指向项目目录

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_DIR="$HOME/.ai-skills/knowledge-search"

echo "=== knowledge-search Skill 安装 ==="
echo "  源目录: $SKILL_DIR"
echo "  目标: $INSTALL_DIR"

# 创建 ~/.ai-skills 目录
mkdir -p "$HOME/.ai-skills"

# 创建或更新软链接
if [[ -L "$INSTALL_DIR" ]]; then
    CURRENT_TARGET=$(readlink -f "$INSTALL_DIR")
    if [[ "$CURRENT_TARGET" == "$(readlink -f "$SKILL_DIR")" ]]; then
        echo "  ✅ 已安装（软链接已存在且指向正确）"
    else
        echo "  🔄 更新软链接: $CURRENT_TARGET → $SKILL_DIR"
        rm "$INSTALL_DIR"
        ln -s "$SKILL_DIR" "$INSTALL_DIR"
        echo "  ✅ 更新完成"
    fi
elif [[ -e "$INSTALL_DIR" ]]; then
    echo "  ❌ $INSTALL_DIR 已存在且不是软链接，请手动处理"
    exit 1
else
    ln -s "$SKILL_DIR" "$INSTALL_DIR"
    echo "  ✅ 安装完成"
fi

# 设置脚本可执行权限
chmod +x "$SKILL_DIR/scripts/knowledge-search.sh"
echo "  ✅ knowledge-search.sh 已设置可执行权限"

echo ""
echo "用法:"
echo "  bash ~/.ai-skills/knowledge-search/scripts/knowledge-search.sh \"查询\" --preset coding"
