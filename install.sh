#!/bin/bash
# ============================================================
# auto-music-download 一键安装脚本
# One-click install script for auto-music-download
# ============================================================
# 功能 / Features:
#   1. 检查环境依赖 (Check dependencies)
#   2. 引导填写配置 (Interactive config setup)
#   3. 生成 config.json (Generate config)
#   4. 测试连接 (Test connectivity)
# ============================================================

set -e

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SKILL_DIR/config.json"

# 颜色输出 / Colored output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  🎵 auto-music-download 安装向导${NC}"
echo -e "${GREEN}  Installation Wizard${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ---- Step 1: 检查依赖 / Check Dependencies ----
echo -e "${YELLOW}[1/4] 检查环境依赖... / Checking dependencies...${NC}"

check_dep() {
    if command -v "$1" &>/dev/null; then
        echo -e "  ✅ $1 已安装 / installed"
    else
        echo -e "  ❌ $1 未安装 / NOT installed"
        MISSING_DEPS="$MISSING_DEPS $1"
    fi
}

MISSING_DEPS=""
check_dep python3
check_dep curl
check_dep sshpass

if [ -n "$MISSING_DEPS" ]; then
    echo ""
    echo -e "${RED}缺少依赖 / Missing dependencies:$MISSING_DEPS${NC}"
    echo ""
    echo "安装命令 / Install commands:"
    echo "  Debian/Ubuntu: sudo apt install $MISSING_DEPS"
    echo "  CentOS/RHEL:   sudo yum install $MISSING_DEPS"
    echo "  macOS:         brew install $MISSING_DEPS"
    echo ""
    read -p "是否继续？(y/n) / Continue anyway? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        echo "退出安装 / Exiting."
        exit 1
    fi
fi

echo ""

# ---- Step 2: 引导配置 / Config Setup ----
echo -e "${YELLOW}[2/4] 请填写配置信息 / Please fill in configuration:${NC}"
echo ""

# 如果已有配置文件，询问是否覆盖
if [ -f "$CONFIG_FILE" ]; then
    echo -e "  发现已有配置文件 / Existing config found"
    read -p "  是否覆盖？(y/n) / Overwrite? (y/n): " OVERWRITE
    if [ "$OVERWRITE" != "y" ]; then
        echo -e "${GREEN}保留现有配置 / Keeping existing config.${NC}"
        exit 0
    fi
    echo ""
fi

read -p "  SolaraPlus 地址 (http://YOUR_NAS_IP:3010): " SOLARA_URL
read -p "  SolaraPlus 密码: " SOLARA_PASSWORD
read -p "  NAS SSH 地址 (user@IP): " NAS_HOST
read -p "  NAS SSH 密码: " NAS_PASS
read -p "  音乐存放路径 (/vol1/xxx/media): " MEDIA_PATH
read -p "  Music Tag Web 地址 (可选, http://YOUR_NAS_IP:8010): " MTW_URL
read -p "  Music Tag Web 密码 (可选): " MTW_PASS

# 设置默认值 / Set defaults
SOLARA_URL="${SOLARA_URL:-http://YOUR_NAS_IP:3010}"
MEDIA_PATH="${MEDIA_PATH:-/vol1/1000/docker/daoliyu/media}"

echo ""

# ---- Step 3: 生成配置 / Generate Config ----
echo -e "${YELLOW}[3/4] 生成配置文件... / Generating config...${NC}"

cat > "$CONFIG_FILE" << EOF
{
  "solara_url": "$SOLARA_URL",
  "solara_password": "$SOLARA_PASSWORD",
  "nas_host": "$NAS_HOST",
  "nas_pass": "$NAS_PASS",
  "media_path": "$MEDIA_PATH",
  "mtw_url": "${MTW_URL:-$SOLARA_URL}",
  "mtw_user": "admin",
  "mtw_pass": "${MTW_PASS:-}",
  "prefer_hires": true,
  "sources": ["netease", "kuwo"],
  "default_quality": 999
}
EOF

echo -e "  ✅ 配置已生成 / Config saved to: $CONFIG_FILE"
echo ""

# ---- Step 4: 测试连接 / Test Connection ----
echo -e "${YELLOW}[4/4] 测试连接... / Testing connectivity...${NC}"
echo ""

echo "  测试 SSH 连接到 NAS... / Testing SSH connection to NAS..."
if sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$NAS_HOST" "echo ok" 2>/dev/null; then
    echo -e "  ✅ SSH 连接成功 / SSH connected"
else
    echo -e "  ⚠️  SSH 连接失败，请检查地址和密码 / SSH failed, check host and password"
fi

echo ""
echo "  测试 SolaraPlus 服务... / Testing SolaraPlus..."
if sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$NAS_HOST" "curl -s --max-time 5 '${SOLARA_URL}/api/login' -X POST -H 'Content-Type: application/json' -d '{\"password\":\"test\"}'" 2>/dev/null; then
    echo -e "  ✅ SolaraPlus 可访问 / SolaraPlus accessible"
else
    echo -e "  ⚠️  SolaraPlus 无法访问，请检查地址 / SolaraPlus not accessible"
fi

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  🎉 安装完成！/ Installation Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "测试下载 / Test download:"
echo "  python3 scripts/music-manager.py \"测试歌曲\""
echo ""
echo "通过 AI 助手使用 / Use with AI assistant:"
echo "  告诉助手: \"我想听 XXX\""
echo ""
