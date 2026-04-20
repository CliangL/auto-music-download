#!/bin/bash
# auto-music-download installer/updater for Hermes/OpenClaw.
# New install: detect environment, infer service ports, then ask only for
# missing secrets and media paths. Update: keep existing config and validate.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SKILL_DIR/config.json"
PLAN_FILE="$SKILL_DIR/install-plan.md"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

YES=false
RECONFIGURE=false
INSTALL_DEPS=false
INSTALL_CONTAINERS=false

for arg in "$@"; do
    case "$arg" in
        --yes|-y) YES=true ;;
        --reconfigure) RECONFIGURE=true ;;
        --install-deps) INSTALL_DEPS=true ;;
        --install-containers) INSTALL_CONTAINERS=true ;;
        --help|-h)
            echo "Usage: bash install.sh [--yes] [--reconfigure] [--install-deps] [--install-containers]"
            exit 0
            ;;
    esac
done

ask() {
    local prompt="$1"
    local default="${2:-}"
    local value
    if [ "$YES" = true ] && [ -n "$default" ]; then
        printf '%s' "$default"
        return
    fi
    if [ -n "$default" ] && [ "$default" != "null" ]; then
        read -r -p "$prompt [$default]: " value
        printf '%s' "${value:-$default}"
    else
        read -r -p "$prompt: " value
        printf '%s' "$value"
    fi
}

confirm() {
    local prompt="$1"
    [ "$YES" = true ] && return 0
    local answer
    read -r -p "$prompt (y/N): " answer
    [ "$answer" = "y" ] || [ "$answer" = "Y" ]
}

json_get() {
    local expr="$1"
    [ -f "$CONFIG_FILE" ] || return 0
    jq -r "$expr // empty" "$CONFIG_FILE" 2>/dev/null || true
}

install_local_deps() {
    local missing=("$@")
    [ "${#missing[@]}" -eq 0 ] && return 0
    if [ "$INSTALL_DEPS" != true ] && ! confirm "是否安装缺失依赖: ${missing[*]}"; then
        return 0
    fi
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y "${missing[@]}"
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y "${missing[@]}"
    elif command -v brew >/dev/null 2>&1; then
        brew install "${missing[@]}"
    else
        echo -e "${RED}未识别包管理器，请手动安装: ${missing[*]}${NC}"
    fi
}

require_deps() {
    local missing=()
    for dep in "$@"; do
        command -v "$dep" >/dev/null 2>&1 || missing+=("$dep")
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        echo -e "${RED}缺少必需依赖，无法继续: ${missing[*]}${NC}"
        echo "请安装后重试，或运行: bash install.sh --install-deps"
        exit 1
    fi
}

ssh_cmd() {
    if [ -z "${NAS_HOST:-}" ] || [ -z "${NAS_USER:-}" ]; then
        return 1
    fi
    if ssh -p "${SSH_PORT:-22}" -o BatchMode=yes -o ConnectTimeout=4 "$NAS_USER@$NAS_HOST" "echo ok" >/dev/null 2>&1; then
        SSH_CMD=(ssh -p "${SSH_PORT:-22}" -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$NAS_USER@$NAS_HOST")
    else
        SSH_CMD=(sshpass -p "${NAS_PASS:-}" ssh -p "${SSH_PORT:-22}" -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$NAS_USER@$NAS_HOST")
    fi
}

detect_remote() {
    DETECT_SOLARA_URL=""
    DETECT_MTW_URL=""
    DETECT_NAVIDROME_URL=""
    REMOTE_HAS_DOCKER=false
    REMOTE_CONTAINERS=""
    ssh_cmd || return 0
    if "${SSH_CMD[@]}" "command -v docker >/dev/null 2>&1" >/dev/null 2>&1; then
        REMOTE_HAS_DOCKER=true
        REMOTE_CONTAINERS=$("${SSH_CMD[@]}" "docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}'" 2>/dev/null || true)
    fi
    [ -z "$REMOTE_CONTAINERS" ] && return 0
    while IFS='|' read -r name image ports; do
        line="$(printf '%s %s' "$name" "$image" | tr '[:upper:]' '[:lower:]')"
        port=$(printf '%s' "$ports" | grep -oE '0\.0\.0\.0:[0-9]+->|:[0-9]+->' | head -1 | grep -oE '[0-9]+' | head -1 || true)
        case "$line" in
            *solara*|*music-downloader*) [ -n "$port" ] && DETECT_SOLARA_URL="http://$NAS_HOST:$port" ;;
            *music-tag-web*|*music_tag_web*|*mtw*) [ -n "$port" ] && DETECT_MTW_URL="http://$NAS_HOST:$port" ;;
            *navidrome*|*daoliyun*|*daap*) [ -n "$port" ] && DETECT_NAVIDROME_URL="http://$NAS_HOST:$port" ;;
        esac
    done <<< "$REMOTE_CONTAINERS"
}

write_plan() {
    cat > "$PLAN_FILE" <<EOF
# auto-music-download 环境检测结果

生成时间: $(date '+%Y-%m-%d %H:%M:%S')

## 本机依赖

- python3/jq/curl/ssh/sshpass 会由 install.sh 检测；如用户授权，可用 \`--install-deps\` 自动安装。

## NAS 检测

- NAS: ${NAS_USER:-?}@${NAS_HOST:-?}:${SSH_PORT:-22}
- Docker: ${REMOTE_HAS_DOCKER:-false}
- SolaraPlus: ${SOLARA_URL:-未配置}
- Music Tag Web: ${MTW_URL:-未配置}
- Navidrome/媒体库: ${DETECT_NAVIDROME_URL:-未检测}

## AI 后续动作

如果缺少容器，请 AI 根据用户 NAS 平台选择合适镜像部署：

1. SolaraPlus: 提供搜索、下载和登录接口，暴露给本机可访问端口。
2. Music Tag Web: 可选，用于下载后刮削音乐元数据。
3. 媒体库服务: 可选，用于下载后刷新媒体库。
4. 部署完成后重新运行 \`bash install.sh --reconfigure\`，自动识别端口并写入 config.json。

用户只需要授权安装，并提供 NAS SSH 密码、SolaraPlus 密码、音乐保存目录、可选 Music Tag Web 密码。
EOF
}

echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}auto-music-download 安装/更新向导${NC}"
echo -e "${BLUE}============================================${NC}"

NEW_INSTALL=true
[ -f "$CONFIG_FILE" ] && NEW_INSTALL=false

echo -e "${YELLOW}[1/5] 检测本机依赖${NC}"
missing=()
for dep in python3 jq curl ssh; do
    command -v "$dep" >/dev/null 2>&1 || missing+=("$dep")
done
command -v sshpass >/dev/null 2>&1 || missing+=("sshpass")
if [ "${#missing[@]}" -gt 0 ]; then
    echo "  缺失: ${missing[*]}"
    install_local_deps "${missing[@]}"
else
    echo "  本机依赖齐全"
fi
require_deps python3 jq curl ssh

echo -e "${YELLOW}[2/5] 判断安装模式${NC}"
if [ "$NEW_INSTALL" = false ] && [ "$RECONFIGURE" = false ]; then
    echo "  检测到已有配置：进入更新模式，保留原有接口/API/密码/目录。"
else
    echo "  进入新装/重新配置模式。"
fi

SOLARA_URL="$(json_get '.solara_url')"
SOLARA_PASSWORD="$(json_get '.solara_password')"
NAS_LOGIN_EXISTING="$(json_get '.nas_host')"
NAS_PASS="$(json_get '.nas_pass')"
SSH_PORT="$(json_get '.ssh_port')"
MEDIA_PATH="$(json_get '.media_path')"
MTW_URL="$(json_get '.mtw_url')"
MTW_USER="$(json_get '.mtw_user')"
MTW_PASS="$(json_get '.mtw_pass')"

NAS_USER="${NAS_LOGIN_EXISTING%@*}"
NAS_HOST="${NAS_LOGIN_EXISTING#*@}"
if [ "$NAS_LOGIN_EXISTING" = "$NAS_HOST" ]; then
    NAS_USER=""
fi

if [ "$NEW_INSTALL" = true ] || [ "$RECONFIGURE" = true ]; then
    NAS_LOGIN="$(ask 'NAS SSH 地址(user@IP)' "$NAS_LOGIN_EXISTING")"
    NAS_PASS="$(ask 'NAS SSH 密码' "$NAS_PASS")"
    SSH_PORT="$(ask 'NAS SSH 端口' "${SSH_PORT:-22}")"
    NAS_USER="${NAS_LOGIN%@*}"
    NAS_HOST="${NAS_LOGIN#*@}"
    if [ "$NAS_LOGIN" = "$NAS_HOST" ]; then
        NAS_USER="$(ask 'NAS SSH 用户名' "$NAS_USER")"
    fi
    echo -e "${YELLOW}[3/5] 自动识别 NAS 容器和端口${NC}"
    detect_remote
    SOLARA_URL="$(ask 'SolaraPlus 地址' "${SOLARA_URL:-${DETECT_SOLARA_URL:-http://$NAS_HOST:3010}}")"
    SOLARA_PASSWORD="$(ask 'SolaraPlus 密码' "$SOLARA_PASSWORD")"
    MEDIA_PATH="$(ask '音乐保存目录' "${MEDIA_PATH:-/vol1/xxx/music}")"
    MTW_URL="$(ask 'Music Tag Web 地址(可选)' "${MTW_URL:-$DETECT_MTW_URL}")"
    MTW_USER="$(ask 'Music Tag Web 用户名(可选)' "${MTW_USER:-admin}")"
    MTW_PASS="$(ask 'Music Tag Web 密码(可选)' "$MTW_PASS")"
else
    echo -e "${YELLOW}[3/5] 自动检测现有环境${NC}"
    detect_remote
    SOLARA_URL="${SOLARA_URL:-$DETECT_SOLARA_URL}"
    MTW_URL="${MTW_URL:-$DETECT_MTW_URL}"
fi

if [ "$INSTALL_CONTAINERS" = true ]; then
    echo "  容器自动安装由 AI 根据 $PLAN_FILE 执行；本脚本不硬编码第三方镜像，避免部署错误镜像。"
fi

NAS_LOGIN_VALUE="${NAS_USER:+$NAS_USER@}$NAS_HOST"

echo -e "${YELLOW}[4/5] 写入配置${NC}"
tmp="$CONFIG_FILE.tmp.$$"
jq -n \
  --arg solara_url "$SOLARA_URL" \
  --arg solara_password "$SOLARA_PASSWORD" \
  --arg nas_host "$NAS_LOGIN_VALUE" \
  --arg nas_pass "$NAS_PASS" \
  --argjson ssh_port "${SSH_PORT:-22}" \
  --arg media_path "${MEDIA_PATH:-/vol1/xxx/music}" \
  --arg mtw_url "$MTW_URL" \
  --arg mtw_user "${MTW_USER:-admin}" \
  --arg mtw_pass "$MTW_PASS" \
  '{
    solara_url: $solara_url,
    solara_password: $solara_password,
    nas_host: $nas_host,
    nas_pass: $nas_pass,
    ssh_port: $ssh_port,
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
rm -f "$SKILL_DIR/.solara_cookies.txt" 2>/dev/null || true
write_plan

echo -e "${YELLOW}[5/5] 语法检查${NC}"
python3 -m py_compile "$SKILL_DIR"/scripts/*.py >/dev/null
for sh in "$SKILL_DIR"/scripts/*.sh; do
    bash -n "$sh"
done

echo -e "${GREEN}完成。已有配置已保留并刷新为当前格式。${NC}"
echo "环境检测报告: $PLAN_FILE"
