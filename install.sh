#!/bin/bash
# auto-music-download install/update script.
# Re-running this script updates defaults and validates code without deleting
# existing Solara/NAS/Music Tag Web credentials.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SKILL_DIR/config.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

read_default() {
    local prompt="$1"
    local default="$2"
    local value
    if [ -n "$default" ] && [ "$default" != "null" ]; then
        read -r -p "$prompt [$default]: " value
        printf '%s' "${value:-$default}"
    else
        read -r -p "$prompt: " value
        printf '%s' "$value"
    fi
}

json_get() {
    local expr="$1"
    [ -f "$CONFIG_FILE" ] || return 0
    jq -r "$expr // empty" "$CONFIG_FILE" 2>/dev/null || true
}

echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}auto-music-download 安装/更新向导${NC}"
echo -e "${BLUE}============================================${NC}"

echo -e "${YELLOW}[1/4] 检查依赖${NC}"
for dep in python3 jq curl ssh; do
    if ! command -v "$dep" >/dev/null 2>&1; then
        echo "  缺少依赖: $dep"
    fi
done
if ! command -v sshpass >/dev/null 2>&1; then
    echo "  提示: 未安装 sshpass 时需配置 SSH key，或手动安装 sshpass"
fi

echo -e "${YELLOW}[2/4] 生成或更新配置${NC}"
if [ -f "$CONFIG_FILE" ]; then
    echo "  已发现配置，将保留现有接口/API/密码，只补齐缺省字段。"
else
    echo "  新安装：请提供 Solara、NAS 和音乐目录信息。"
fi

SOLARA_URL="$(json_get '.solara_url')"
SOLARA_PASSWORD="$(json_get '.solara_password')"
NAS_HOST="$(json_get '.nas_host')"
NAS_PASS="$(json_get '.nas_pass')"
MEDIA_PATH="$(json_get '.media_path')"
MTW_URL="$(json_get '.mtw_url')"
MTW_USER="$(json_get '.mtw_user')"
MTW_PASS="$(json_get '.mtw_pass')"

SOLARA_URL="$(read_default 'SolaraPlus 地址' "${SOLARA_URL:-http://YOUR_NAS_IP:3010}")"
SOLARA_PASSWORD="$(read_default 'SolaraPlus 密码' "$SOLARA_PASSWORD")"
NAS_HOST="$(read_default 'NAS SSH 地址(user@IP)' "$NAS_HOST")"
NAS_PASS="$(read_default 'NAS SSH 密码' "$NAS_PASS")"
MEDIA_PATH="$(read_default '音乐存放路径' "${MEDIA_PATH:-/vol1/xxx/music}")"
MTW_URL="$(read_default 'Music Tag Web 地址(可选)' "$MTW_URL")"
MTW_USER="$(read_default 'Music Tag Web 用户名(可选)' "${MTW_USER:-admin}")"
MTW_PASS="$(read_default 'Music Tag Web 密码(可选)' "$MTW_PASS")"

tmp="$CONFIG_FILE.tmp.$$"
jq -n \
  --arg solara_url "$SOLARA_URL" \
  --arg solara_password "$SOLARA_PASSWORD" \
  --arg nas_host "$NAS_HOST" \
  --arg nas_pass "$NAS_PASS" \
  --arg media_path "$MEDIA_PATH" \
  --arg mtw_url "$MTW_URL" \
  --arg mtw_user "$MTW_USER" \
  --arg mtw_pass "$MTW_PASS" \
  '{
    solara_url: $solara_url,
    solara_password: $solara_password,
    nas_host: $nas_host,
    nas_pass: $nas_pass,
    media_path: $media_path,
    mtw_url: $mtw_url,
    mtw_user: $mtw_user,
    mtw_pass: $mtw_pass,
    prefer_hires: true,
    sources: ["netease", "kuwo"],
    default_quality: 999,
    gd_api_base: "https://music-api-hk.gdstudio.xyz/api.php",
    proxy: ""
  }' > "$tmp"
if [ -f "$CONFIG_FILE" ]; then
    merged="$CONFIG_FILE.merged.$$"
    jq -s '.[0] * .[1]' "$CONFIG_FILE" "$tmp" > "$merged"
    mv "$merged" "$CONFIG_FILE"
    rm -f "$tmp"
else
    mv "$tmp" "$CONFIG_FILE"
fi
chmod 600 "$CONFIG_FILE"

echo -e "${YELLOW}[3/4] 清理运行时临时文件${NC}"
rm -f "$SKILL_DIR/.solara_cookies.txt" 2>/dev/null || true

echo -e "${YELLOW}[4/4] 语法检查${NC}"
python3 -m py_compile "$SKILL_DIR"/scripts/*.py >/dev/null
for sh in "$SKILL_DIR"/scripts/*.sh; do
    bash -n "$sh"
done

echo -e "${GREEN}完成。已有配置已保留并刷新为当前格式。${NC}"
