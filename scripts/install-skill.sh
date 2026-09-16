#!/usr/bin/env bash
# 把本仓库的 WorkBuddy 技能安装到本机技能目录。
#
# 用法：
#   scripts/install-skill.sh
#   SKILL_INSTALL_DIR=~/.skills scripts/install-skill.sh
#
# 说明：
#   - 默认装到 ~/.workbuddy/skills/boss-agent-cli
#   - 已存在同名目录时，先改名为 *.bak 再安装（不直接删除，方便回退）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_NAME="boss-agent-cli"
SKILL_SRC="$REPO_ROOT/skills/$SKILL_NAME"
DEST_ROOT="${SKILL_INSTALL_DIR:-$HOME/.workbuddy/skills}"
DEST="$DEST_ROOT/$SKILL_NAME"

if [[ ! -f "$SKILL_SRC/SKILL.md" ]]; then
	echo "找不到技能源文件：$SKILL_SRC/SKILL.md" >&2
	exit 1
fi

# 安全护栏：只允许写入名为 boss-agent-cli 的目标目录
if [[ "$(basename "$DEST")" != "$SKILL_NAME" ]]; then
	echo "目标路径异常，已中止：$DEST" >&2
	exit 1
fi

mkdir -p "$DEST_ROOT"

if [[ -e "$DEST" || -L "$DEST" ]]; then
	# 注意：macOS 自带 bash 3.2 处理多字节字符有缺陷，`$DEST` 紧跟中文标点会被
	# 当成变量名的一部分（报 unbound variable），所以这里一律写成 ${DEST}。
	echo "已存在 ${DEST}，先备份为 ${DEST}.bak"
	rm -rf "${DEST}.bak"
	mv "$DEST" "${DEST}.bak"
fi

cp -R "$SKILL_SRC" "$DEST"
rm -rf "$DEST/scripts/__pycache__"
chmod +x "$DEST"/scripts/*.py 2>/dev/null || true

echo "已安装技能：$DEST"
find "$DEST" -type f | sort | sed "s|$DEST/|  |"
echo
echo "在 WorkBuddy 里提到「BOSS 直聘 / 沟通记录」即可自动加载。"
echo "详见：docs/integrations/workbuddy.md"
