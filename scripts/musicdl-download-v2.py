#!/usr/bin/env python3
"""
musicdl-download-v2.py - 优化版多源无损音乐下载
优化点：
  1. 仅下载 FLAC，拒绝有损格式
  2. 下载链接预验证（HEAD 请求）
  3. 下载后校验文件大小
  4. SSH key 连接（不再需要 sshpass/密码）
  5. 失败重试 + 自动清理
  6. 最大大小 150MB（FLAC 通常 30-100MB）

用法:
    python3 musicdl-download-v2.py "歌曲名" ["艺术家"]
"""

import sys
import os
import subprocess
import atexit
import urllib.request
import urllib.error

# ===== 配置 =====
NAS_HOST = "YOUR_USERNAME@YOUR_TAILSCALE_IP"
MEDIA_PATH = "/vol1/docker/daoliyu/media"
DAOLIYU_URL = "http://YOUR_NAS_IP:5173"

MUSIC_SOURCES = [
    "NeteaseMusicClient",  # 网易云 - FLAC 资源多且链接稳定
    "KuwoMusicClient",     # 酷我 - FLAC 丰富
    "KugouMusicClient",    # 酷狗
    "MiguMusicClient",     # 咪咕
    "QQMusicClient",       # QQ - 通常返回 OGG/MP3
]

MAX_SIZE = 150 * 1024 * 1024  # 150MB
MIN_FLAC_SIZE = 5 * 1024 * 1024  # 5MB（小于这个的不是真正的 FLAC）

PROXY = "http://127.0.0.1:7897"

_temp_files = []
def cleanup():
    for f in _temp_files:
        try:
            os.unlink(f)
        except:
            pass
atexit.register(cleanup)


def ssh(command, timeout=60):
    """执行 SSH 命令（使用 key 认证，不再需要密码）"""
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
           NAS_HOST, command]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r


def parse_size(size_str):
    """解析文件大小到字节"""
    if not size_str:
        return 0
    s = str(size_str).upper().strip()
    try:
        for unit, mult in [('GB', 1024**3), ('MB', 1024**2), ('KB', 1024)]:
            if unit in s:
                return float(s.replace(unit, '').strip()) * mult
        return float(s)
    except:
        return 0


def verify_download_url(url, max_size=MAX_SIZE):
    """预验证下载链接：HEAD 请求检查大小和格式"""
    try:
        proxy_handler = urllib.request.ProxyHandler({
            'http': PROXY, 'https': PROXY
        })
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        
        resp = opener.open(req, timeout=15)
        content_length = int(resp.headers.get('Content-Length', 0))
        content_type = resp.headers.get('Content-Type', '')
        
        if content_length < MIN_FLAC_SIZE:
            return False, f"文件太小 ({content_length}B)"
        if content_length > max_size:
            return False, f"文件超大 ({content_length/1024/1024:.1f}MB)"
        if 'text/html' in content_type:
            return False, f"返回网页 ({content_type})"
        
        return True, f"{content_length/1024/1024:.1f}MB"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:80]


def download_and_verify(url, local_path, timeout=180):
    """下载本地 + 验证完整性"""
    env = os.environ.copy()
    env['http_proxy'] = PROXY
    env['https_proxy'] = PROXY
    env['ALL_PROXY'] = PROXY
    
    cmd = f'curl -L --max-time {timeout} -f -o "{local_path}" "{url}"'
    r = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True, timeout=timeout+10)
    
    if r.returncode != 0:
        msg = r.stderr[:200] if r.stderr else "curl 失败"
        return False, msg
    
    if not os.path.exists(local_path):
        return False, "文件不存在"
    
    size = os.path.getsize(local_path)
    if size < MIN_FLAC_SIZE:
        try:
            os.unlink(local_path)
        except:
            pass
        return False, f"文件太小 ({size/1024/1024:.1f}MB)，可能被拒绝访问"
    
    return True, f"{size/1024/1024:.1f}MB"


def search_songs(query, artist=None):
    """搜索歌曲，返回按优先级排序的 FLAC 结果"""
    os.environ['http_proxy'] = PROXY
    os.environ['https_proxy'] = PROXY
    
    try:
        from musicdl.musicdl import MusicClient
    except ImportError:
        print("❌ musicdl 未安装: pip3 install musicdl pycryptodomex")
        sys.exit(1)
    
    client = MusicClient(music_sources=MUSIC_SOURCES)
    results = client.search(query)
    
    all_songs = []
    for source_name, songs in results.items():
        for song in songs:
            name = getattr(song, 'song_name', '') or getattr(song, 'songname', '')
            if not name:
                continue
            
            ext = getattr(song, 'ext', 'mp3') or 'mp3'
            flac = ext.lower() == 'flac'
            size_str = getattr(song, 'file_size', '')
            size_bytes = parse_size(size_str)
            url = getattr(song, 'download_url', '')
            singers = getattr(song, 'singers', '') or ''
            
            # 只保留 FLAC + 有链接的
            if not flac or not url:
                continue
            
            all_songs.append({
                "source": source_name.replace("MusicClient", ""),
                "name": name,
                "artist": singers,
                "url": url,
                "file_size": size_str,
                "file_size_bytes": size_bytes,
                "ext": ext,
            })
    
    # 按艺术家匹配筛选
    if artist:
        matched = [s for s in all_songs if artist.lower() in s["artist"].lower()]
        if matched:
            all_songs = matched
    
    # 过滤大小
    valid = [s for s in all_songs if s["file_size_bytes"] <= MAX_SIZE]
    if not valid:
        return []
    
    # 按大小降序排（大的往往音质更好）
    valid.sort(key=lambda s: -s["file_size_bytes"])
    return valid


def trigger_scan():
    """触发媒体库扫描"""
    print("\n📚 触发媒体库扫描...")
    
    # 触发 Navidrome 扫描
    r = ssh("docker exec navidrome /app/navidrome scan -f", timeout=30)
    if r.returncode == 0:
        print("✅ Navidrome 扫描已触发")
    else:
        print("⚠️ Navidrome 扫描失败")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 musicdl-download-v2.py \"歌曲名\" [\"艺术家\"]")
        sys.exit(1)
    
    query = sys.argv[1]
    artist = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"\n🎵 多源无损音乐下载 (v2 优化版)")
    print(f"🔍 搜索: {query}" + (f" - {artist}" if artist else ""))
    print(f"📊 优先: FLAC无损 | 原版 | <=150MB")
    print()
    
    # ── 搜索 ──
    songs = search_songs(query, artist)
    
    if not songs:
        print("❌ 未找到 FLAC 无损版本")
        sys.exit(1)
    
    print(f"📋 找到 {len(songs)} 个 FLAC 候选:")
    for i, s in enumerate(songs[:5]):
        mb = s["file_size_bytes"] / 1024 / 1024
        print(f"  [{i+1}] {s['name']} - {s['artist']} | {mb:.1f}MB | {s['source']}")
    print()
    
    # ── 逐个验证下载链接 ──
    print("🔗 验证下载链接...")
    good_songs = []
    
    for i, song in enumerate(songs[:5]):
        print(f"  [{i+1}/{min(5, len(songs))}] {song['source']}: {song['artist']} - ", end="", flush=True)
        
        ok, msg = verify_download_url(song["url"])
        if ok:
            print(f"✅ {msg}")
            song["real_size"] = msg  # 保存实际大小信息
            good_songs.append(song)
        else:
            print(f"❌ {msg}")
    
    if not good_songs:
        print("\n❌ 所有 FLAC 下载链接都不可用")
        sys.exit(1)
    
    # ── 选择最佳 ──
    best = good_songs[0]
    print(f"\n✅ 选择: {best['name']} - {best['artist']} | {best.get('real_size', best['file_size'])} | FLAC | {best['source']}")
    
    # ── 下载到本地 ──
    safe_artist = ''.join(c for c in best["artist"] if c.isalnum() or c in ' _-()（） ').strip() or "未知歌手"
    safe_name = ''.join(c for c in best["name"] if c.isalnum() or c in ' _-()（） ').strip() or "未知歌曲"
    local_path = f"/tmp/{safe_artist}_{safe_name}.flac"
    _temp_files.append(local_path)
    
    print(f"\n⏳ 下载到本地...")
    ok, msg = download_and_verify(best["url"], local_path)
    if not ok:
        print(f"❌ 下载失败: {msg}")
        sys.exit(1)
    print(f"✅ 下载完成 ({msg})")
    
    # ── 上传到 NAS ──
    remote_dir = f"{MEDIA_PATH}/{safe_artist}"
    remote_file = f"{remote_dir}/{safe_artist} - {safe_name}.flac"
    
    # 检查是否已存在
    r = ssh(f'test -f "{remote_file}" && stat -c "%s" "{remote_file}" || echo 0')
    if r.returncode == 0 and r.stdout.strip():
        exist_size = r.stdout.strip()
        if exist_size.isdigit() and int(exist_size) > MIN_FLAC_SIZE:
            print(f"\n⏭️  文件已存在 ({int(exist_size)/1024/1024:.1f}MB)，跳过")
            trigger_scan()
            cleanup()
            print(f"\n🎉 全部完成！")
            print(f" 播放: {DAOLIYU_URL}")
            sys.exit(0)
    
    print(f"\n📤 上传到 NAS...")
    
    # 创建目录
    ssh(f'mkdir -p "{remote_dir}"')
    
    # 用 cat | ssh 管道上传（无密码，支持中文路径）
    with open(local_path, 'rb') as f:
        local_size = os.path.getsize(local_path)
    
    cat_proc = subprocess.Popen(
        ["cat", local_path],
        stdout=subprocess.PIPE
    )
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
        NAS_HOST, f"cat > \"{remote_file}\""
    ]
    ssh_proc = subprocess.Popen(
        ssh_cmd,
        stdin=cat_proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    cat_proc.stdout.close()
    stdout, stderr = ssh_proc.communicate(timeout=120)
    
    if ssh_proc.returncode != 0:
        print(f"❌ 上传失败: {stderr.decode('utf-8', errors='ignore')[:200]}")
        sys.exit(1)
    
    print(f"✅ 上传完成 ({local_size/1024/1024:.1f}MB)")
    
    # ── 验证 NAS 上文件 ──
    r = ssh(f'test -f "{remote_file}" && stat -c "%s" "{remote_file}" || echo 0')
    remote_size_str = r.stdout.strip()
    if remote_size_str.isdigit():
        remote_size = int(remote_size_str)
        if remote_size < MIN_FLAC_SIZE:
            print(f"❌ NAS 上文件大小异常 ({remote_size}B)")
            sys.exit(1)
        print(f"✅ 验证通过: NAS 文件 {remote_size/1024/1024:.1f}MB")
    else:
        print("⚠️ 无法验证 NAS 文件大小")
    
    # ── 触发扫描 ──
    trigger_scan()
    
    # ── 理 ──
    cleanup()
    
    print(f"\n🎉 全部完成！")
    print(f"🎧 播放: {DAOLIYU_URL}")
    print(f"📁 路径: {remote_file}")


if __name__ == "__main__":
    main()
