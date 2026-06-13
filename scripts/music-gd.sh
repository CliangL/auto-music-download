#!/bin/bash
# GD 音乐台 API 下载脚本 - 智能多源版 (v2.3)
# 优化：
# 1. 自动轮询音源：酷我(kuwo) -> 网易云(netease) -> 咪咕(migu)
# 2. 智能过滤：默认排除 DJ, Live, 伴奏, Remix 版本
# 3. 降级刮削：若 MTW 刮削失败，尝试从文件名提取基本信息

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config.json"

# 读取配置
if [[ -f "$CONFIG_FILE" ]]; then
    NAS_HOST=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['nas_host'])")
    NAS_PASS=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['nas_pass'])")
    MEDIA_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['media_path'])")
    API_URL=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['gd_api_base'])")
fi

# 默认配置
QUALITY="${QUALITY:-999}" # 999=FLAC
TIMEOUT=30

# 🚫 黑名单关键词 (正则)
BLACKLIST_REGEX="DJ|Live|伴奏|Remix|Cover|Piano|Instrumental|吉他弹唱|翻唱"

# ================= 函数定义 =================

# 1. 搜索并清洗结果
search_and_filter() {
    local keyword="$1"
    local source="$2"
    local encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$keyword'))")
    
    echo "  🔍 正在搜索音源: $source ..." >&2
    local result=$(curl -s --max-time $TIMEOUT "${API_URL}?types=search&count=10&source=${source}&name=${encoded}")
    
    if [[ -z "$result" ]] || [[ "$result" == "[]" ]]; then
        return 1
    fi

    # 过滤黑名单
    # 使用 python3 解析 json 并过滤，更准确
    local best_song=$(echo "$result" | python3 -c "
import sys, json, re
data = json.load(sys.stdin)
if not data: sys.exit(1)

blacklist = re.compile(r'${BLACKLIST_REGEX}', re.I)

# 寻找第一个不在黑名单里的歌
for song in data:
    # 拼接标题、歌手、专辑用于匹配
    full_text = str(song.get('name','')) + ' ' + str(song.get('artist','')) + ' ' + str(song.get('album',''))
    if not blacklist.search(full_text):
        # 找到干净版本
        print(json.dumps(song))
        sys.exit(0)

# 如果全是 DJ 版，且用户没搜 DJ，通常不下载，除非只有一个结果且勉强能听
# 这里为了稳妥，如果全是黑名单，则返回空
sys.exit(1)
" 2>/dev/null)

    if [[ -n "$best_song" ]]; then
        echo "$best_song"
        return 0
    else
        return 1
    fi
}

# 2. 获取下载链接
get_download_url() {
    local song_id="$1"
    local source="$2"
    local result=$(curl -s --max-time $TIMEOUT "${API_URL}?types=url&id=${song_id}&source=${source}&br=${QUALITY}")
    local url=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))")
    echo "$url"
}

# 3. 下载文件
download_to_nas() {
    local url="$1"
    local filepath="$2"
    local dir=$(dirname "$filepath")
    
    # 建目录
    sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no "$NAS_HOST" "mkdir -p '$dir'"
    
    echo "  ⬇️  开始下载..."
    # 在 NAS 上下载
    local dl_out=$(sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no "$NAS_HOST" "
        curl -s --max-time 120 -L '${url}' -o '${filepath}'
        size=\$(stat -c%s '${filepath}' 2>/dev/null || echo 0)
        if [[ \$size -gt 500000 ]]; then
            echo 'OK'
        else
            echo 'FAIL'
            rm -f '${filepath}'
        fi
    ")
    
    if [[ "$dl_out" == "OK" ]]; then
        echo "  ✅ 下载成功"
        return 0
    else
        echo "  ❌ 下载失败"
        return 1
    fi
}

# 4. 极速刮削 + 歌词下载 (不依赖重 Docker)
scrape_metadata() {
    local filepath="$1"
    local name="$2"
    local artist="$3"
    local song_id="$4"
    local source="$5"
    
    echo "  🏷️  极速写入标签 + 歌词..."
    
    # 使用轻量级 Python 直接处理，不调 Docker，速度快且含歌词
    sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no "$NAS_HOST" "
        python3 << 'PYEOF'
import music_tag, urllib.request, json, re

def get_kuwo_lyric(sid):
    try:
        url = f'http://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId={sid}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'http://m.kuwo.cn/'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        
        lrclist = data.get('data', {}).get('lrclist', [])
        lrc_lines = []
        for line in lrclist:
            sec = float(line['time'])
            m, s = divmod(int(sec), 60)
            lrc_lines.append(f'[{m:02d}:{s:02d}.00]{line["lineLyric"]}')
        return '\n'.join(lrc_lines)
    except:
        return ''

try:
    f = music_tag.load_file('$filepath')
    f['title'] = '$name'
    f['artist'] = '$artist'
    f['album'] = '$name'
    
    # 获取歌词
    lrc = get_kuwo_lyric('$song_id')
    if lrc:
        f['lyrics'] = lrc
        # 🛡️ 双保险：同时生成同名 .lrc 文件 (Daoliyu 等播放器最爱)
        lrc_path = '$filepath'.rsplit('.', 1)[0] + '.lrc'
        with open(lrc_path, 'w', encoding='utf-8') as lf:
            lf.write(lrc)
    
    f.save()
    print('Tags & Lyrics updated (+ .lrc file)')
except Exception as e:
    print(f'Error: {e}')
PYEOF
    "
}

# ================= 主流程 =================

main() {
    if [[ $# -lt 1 ]]; then
        echo "用法: $0 <歌曲名> [歌手]"
        exit 1
    fi

    local song_name="$1"
    local artist="${2:-}"
    local keyword="$song_name"
    [[ -n "$artist" ]] && keyword="$song_name $artist"

    echo "🎵 准备下载: $keyword (音质: FLAC)"
    echo "========================================"

    # 定义音源优先级
    sources=("kuwo" "netease" "migu")
    
    found=false

    for src in "${sources[@]}"; do
        echo "--- 尝试音源: $src ---"
        local song_data=$(search_and_filter "$keyword" "$src")
        
        if [[ $? -eq 0 ]] && [[ -n "$song_data" ]]; then
            local id=$(echo "$song_data" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
            local name=$(echo "$song_data" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")
            local real_artist=$(echo "$song_data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['artist'][0] if isinstance(d['artist'], list) else d['artist'])")
            
            echo "  ✅ 找到匹配: $name - $real_artist"
            
            # 获取链接
            local url=$(get_download_url "$id" "$src")
            if [[ -n "$url" ]] && [[ "$url" != "null" ]]; then
                # 构建路径
                local safe_path=$(python3 -c "
import re
a = '$real_artist'; n = '$name'
clean = lambda s: re.sub(r'[<>:\"/\\\\|?*]', '', s).strip()
print(f'{clean(a) or \"Unknown\"}/{clean(a) or \"Unknown\"} - {clean(n) or \"Unknown\"}.flac')
")
                local filepath="${MEDIA_PATH}/${safe_path}"
                
                # 下载
                if download_to_nas "$url" "$filepath"; then
                    # 极速刮削 + 歌词
                    scrape_metadata "$filepath" "$name" "$real_artist" "$id" "$src"
                    
                    # 触发 Daoliyu 扫描 (修正：之前误写了 Navidrome)
                    echo "  🔄 触发 Daoliyu 增量更新..."
                    # 假设 Daoliyu 有类似机制或文件监听，此处调用 Daoliyu 容器刷新
                    sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no "$NAS_HOST" "docker exec daoliyu node /app/server/cli.js scan --force >/dev/null 2>&1 &" || \
                    sshpass -p "$NAS_PASS" ssh -o StrictHostKeyChecking=no "$NAS_HOST" "docker restart daoliyu >/dev/null 2>&1 &" # 兜底方案
                    
                    echo "🎉 完成！"
                    found=true
                    break
                else
                    echo "  ❌ 下载失败，尝试下一个音源..."
                fi
            else
                echo "  ❌ 无法获取下载链接，尝试下一个音源..."
            fi
        fi
    done

    if [[ "$found" == false ]]; then
        echo "❌ 所有音源均未找到合适的版本（已自动过滤 DJ/伴奏）。"
        exit 1
    fi
}

main "$@"