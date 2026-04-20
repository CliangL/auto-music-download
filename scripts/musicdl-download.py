#!/usr/bin/env python3
"""
musicdl-download.py - 多源无损音乐下载脚本
支持平台：酷狗、网易云、酷我、QQ、咪咕等

用法:
    python3 musicdl-download.py "歌曲名" ["艺术家"]
    python3 musicdl-download.py "体面" "于文文"
"""

import sys
import os
import subprocess
import time
from musicdl.musicdl import MusicClient

# ===== 用户配置（请修改为你的配置）=====
NAS_HOST = "YOUR_USERNAME@YOUR_TAILSCALE_IP"   # NAS SSH 地址
NAS_PASS = "YOUR_PASSWORD"                   # NAS SSH 密码
MEDIA_PATH = "/vol1/docker/daoliyu/media"  # 音乐存放路径 (Daoliyu监控目录)
DAOLIYU_URL = "http://YOUR_NAS_IP:5173"       # 播放器地址
DAOLIYU_EMAIL = "YOUR_EMAIL"                  # 登录邮箱
DAOLIYU_PASS = "YOUR_PASSWORD"                # 登录密码
# =====================================

# 大小限制：优先 50MB 以内
MAX_SIZE = 50 * 1024 * 1024  # 50MB

# 音源优先级
MUSIC_SOURCES = [
    "KugouMusicClient",   # 酷狗
    "KuwoMusicClient",    # 酷我
    "NeteaseMusicClient", # 网易云
    "QQMusicClient",      # QQ音乐
    "MiguMusicClient",    # 咪咕
]


def sanitize(s):
    """清理文件名"""
    return ''.join(c for c in s if c.isalnum() or c in ' _-').strip()


def parse_file_size(size_str):
    """解析文件大小字符串，返回字节数"""
    if not size_str:
        return 0
    size_str = str(size_str).upper().strip()
    try:
        if 'GB' in size_str:
            return float(size_str.replace('GB', '').strip()) * 1024 * 1024 * 1024
        elif 'MB' in size_str:
            return float(size_str.replace('MB', '').strip()) * 1024 * 1024
        elif 'KB' in size_str:
            return float(size_str.replace('KB', '').strip()) * 1024
        else:
            return float(size_str)
    except:
        return 0


def search_song(query, artist=None):
    """搜索歌曲"""
    print(f"🔍 搜索: {query}")
    
    # 设置代理
    os.environ['http_proxy'] = 'http://127.0.0.1:7897'
    os.environ['https_proxy'] = 'http://127.0.0.1:7897'
    
    client = MusicClient(music_sources=MUSIC_SOURCES)
    results = client.search(query)
    
    all_songs = []
    for source, songs in results.items():
        for song in songs:
            singer = song.singers if hasattr(song, 'singers') and song.singers else ""
            name = ""
            if hasattr(song, 'song_name') and song.song_name:
                name = song.song_name
            elif hasattr(song, 'songname') and song.songname:
                name = song.songname
            ext = song.ext if hasattr(song, 'ext') else "mp3"
            file_size = song.file_size if hasattr(song, 'file_size') else ""
            file_size_bytes = parse_file_size(file_size)
            name_lower = name.lower()
            
            # 判断是否是特殊版本
            is_special = any(kw in name_lower for kw in [
                'live', 'dj', 'remix', '伴奏', '纯音乐', '翻唱', 'with', '&', '合唱', 'feat'
            ])
            
            all_songs.append({
                "source": source.replace("MusicClient", ""),
                "name": name,
                "artist": singer,
                "album": song.album if hasattr(song, 'album') else "",
                "url": song.download_url if hasattr(song, 'download_url') else "",
                "file_size": file_size,
                "file_size_bytes": file_size_bytes,
                "ext": ext,
                "is_flac": ext.lower() == "flac",
                "is_special": is_special,
            })
    
    # 筛选匹配艺术家的歌曲
    valid_songs = [s for s in all_songs if s["url"]]
    if not valid_songs:
        return None
    
    if artist:
        matched = [s for s in valid_songs if artist.lower() in s["artist"].lower()]
        if matched:
            valid_songs = matched
    
    # 分类显示
    small_songs = [s for s in valid_songs if s["file_size_bytes"] <= MAX_SIZE]
    big_songs = [s for s in valid_songs if s["file_size_bytes"] > MAX_SIZE]
    
    print(f"\n📋 找到 {len(valid_songs)} 首候选歌曲：")
    
    if small_songs:
        print(f"  📦 50MB以内 ({len(small_songs)}首)：")
        for i, song in enumerate(small_songs[:5]):
            size_mb = song["file_size_bytes"] / 1024 / 1024
            flac_tag = "🔊" if song["is_flac"] else "🎵"
            print(f"    {i+1}. {flac_tag} {song['name']} - {song['artist']} | {size_mb:.1f}MB | {song['source']}")
    
    if big_songs:
        print(f"  📀 超过50MB ({len(big_songs)}首)，默认跳过：")
        for song in big_songs[:3]:
            size_mb = song["file_size_bytes"] / 1024 / 1024
            print(f"    - {song['name']} | {size_mb:.1f}MB | {song['source']}")
    
    if not small_songs:
        print("❌ 没有50MB以内的歌曲")
        return None
    
    # 选择最佳版本：录音室原版优先 > FLAC > MP3
    def is_studio_original(s):
        return not s["is_special"]
    
    def select_best(songs, prefer_flac=True):
        if not songs:
            return None
        songs = [s for s in songs if is_studio_original(s)]
        if not songs:
            return None
        songs.sort(key=lambda s: -s["file_size_bytes"])
        return songs[0]
    
    flac_songs = [s for s in small_songs if s["is_flac"]]
    best_flac = select_best(flac_songs)
    
    mp3_songs = [s for s in small_songs if not s["is_flac"]]
    best_mp3 = select_best(mp3_songs)
    
    if best_flac:
        print(f"\n✅ 选择 FLAC：{best_flac['name']} - {best_flac['artist']} ({best_flac['file_size']})")
        return best_flac
    elif best_mp3:
        print(f"\n✅ 选择 MP3：{best_mp3['name']} - {best_mp3['artist']} ({best_mp3['file_size']})")
        return best_mp3
    else:
        print("❌ 没有找到合适的歌曲")
        return None


def download_to_nas(song):
    """下载到 NAS"""
    if not song["url"]:
        print("❌ 无下载链接")
        return False
    
    safe_artist = sanitize(song["artist"]) or "未知歌手"
    safe_name = sanitize(song["name"]) or "未知歌曲"
    ext = song["ext"] or "flac"
    filename = f"{safe_artist} - {safe_name}.{ext}"
    remote_path = f"{MEDIA_PATH}/{safe_artist}/{filename}"
    
    # 检查文件是否存在
    check_cmd = f'[ -f "{remote_path}" ] && stat -c "%s" "{remote_path}" || echo 0'
    try:
        result = subprocess.run(
            ["sshpass", "-p", NAS_PASS, "ssh", "-o", "StrictHostKeyChecking=no", NAS_HOST, check_cmd],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip() not in ["0", ""]:
            size = int(result.stdout.strip())
            if size > 1000000:
                print(f"⏭️  文件已存在，跳过下载")
                return True
    except:
        pass
    
    print(f"📥 下载: {filename}")
    print(f"   音源: {song['source']} | 大小: {song['file_size']}")
    
    download_cmd = f'''mkdir -p "{MEDIA_PATH}/{safe_artist}" && curl -L --max-time 300 -o "{remote_path}" '{song["url"]}' && ls -lh "{remote_path}"'''
    
    result = subprocess.run(
        ["sshpass", "-p", NAS_PASS, "ssh", "-o", "StrictHostKeyChecking=no", NAS_HOST, download_cmd],
        capture_output=True, text=True, timeout=360
    )
    
    if result.returncode == 0:
        print("✅ 下载完成")
        return True
    else:
        print(f"❌ 下载失败: {result.stderr}")
        return False


def trigger_scan():
    """触发 Daoliyu 媒体库扫描 + 歌词刮削（通过 SSH 在 NAS 上执行）"""
    print("\n📚 触发媒体库扫描...")
    
    try:
        # SSH 到 NAS 执行扫描命令
        scan_cmd = '''
            TOKEN=$(curl -s --max-time 10 'http://localhost:5173/api/auth/login' \
                -X POST -H 'Content-Type: application/json' \
                -d '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}' | jq -r '.token // empty')
            
            if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
                echo "LOGIN_FAIL"
                exit 1
            fi
            
            echo "✅ 登录成功"
            
            # 媒体扫描
            curl -s --max-time 30 'http://localhost:5173/api/admin/scan' -X POST \
                -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
                -d '{"kind":"MEDIA"}'
            echo ''
            
            sleep 2
            
            # 歌词刮削
            curl -s --max-time 30 'http://localhost:5173/api/admin/scan' -X POST \
                -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
                -d '{"kind":"LYRICS"}'
            echo ''
        '''
        
        result = subprocess.run(
            ["sshpass", "-p", NAS_PASS, "ssh", "-o", "StrictHostKeyChecking=no", 
             NAS_HOST, scan_cmd],
            capture_output=True, text=True, timeout=60
        )
        
        if "LOGIN_FAIL" in result.stdout:
            print("⚠️ Daoliyu 登录失败")
        elif "STARTED" in result.stdout or "OK" in result.stdout:
            print("✅ 媒体扫描已启动")
            if "STARTED" in result.stdout:
                print("✅ 歌词刮削已启动")
        else:
            print(f"⚠️ 扫描结果: {result.stdout[:200]}")
            
    except Exception as e:
        print(f"⚠️ 扫描失败: {e}")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 musicdl-download.py \"歌曲名\" [\"艺术家\"]")
        print("示例: python3 musicdl-download.py \"像我这样的人\" \"毛不易\"")
        sys.exit(1)
    
    query = sys.argv[1]
    artist = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"\n🎵 多源音乐下载")
    print(f"歌曲: {query}")
    if artist:
        print(f"艺术家: {artist}")
    print(f"优先: 50MB以内 | FLAC无损 | 原版")
    
    song = search_song(query, artist)
    if not song:
        sys.exit(1)
    
    print(f"\n✅ 选择: {song['name']} - {song['artist']}")
    print(f"   📦 {song['file_size']} | {song['source']} | {song['ext']}")
    
    if download_to_nas(song):
        trigger_scan()
        print(f"\n🎉 全部完成！")
        print(f"🎧 播放: {DAOLIYU_URL}")


if __name__ == "__main__":
    main()
