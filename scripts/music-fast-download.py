#!/usr/bin/env python3
"""
music-fast-download.py - NAS 直接下载无损音乐
架构：Mac 端 SSH 到 NAS，NAS 直接下载，MusicTag 自动刮削元数据和歌词。
目标：30秒内完成。

用法:
    python3 music-fast-download.py "歌曲名" "歌手"
"""

import sys
import os
import subprocess
import json
import time
from pathlib import Path

# ===== 配置 =====
NAS_HOST = "YOUR_USERNAME@YOUR_NAS_IP"
SSH_CONTROL_PATH = Path("/tmp/hermes-music-nas-ssh-%r@%h:%p")
SSH_OPTIONS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "ConnectTimeout=5",
    "-o", "LogLevel=ERROR",
    "-o", "ControlMaster=auto",
    "-o", "ControlPersist=60",
    "-o", f"ControlPath={SSH_CONTROL_PATH}",
]

# NAS 端执行的完整脚本
NAS_SCRIPT_TEMPLATE = r'''
import sys, os, json, subprocess, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

SONG_NAME = {song_name_repr}
ARTIST = {artist_repr}
ALLOW_FUZZY_ARTIST = {allow_fuzzy_repr}
MEDIA_DIR = "/vol1/1000/docker/daoliyu/media"
GD_API = "https://music-api-hk.gdstudio.xyz/api.php"
# 2026-06-13: kuwo 在 GD API 上游全码率挂死(主/HK实例都一样),netease 是当前唯一
# 稳定无损源,故 netease 优先;kuwo 留作保底以备上游恢复。
SOURCES = ["netease", "kuwo"]
CANDIDATES_PER_SOURCE = 6
MAX_NO_LINK_PER_SOURCE = 3
URL_LOOKUP_TIMEOUT = 5
# 单候选码率回退:999(无损FLAC)拿不到时降试 740。后续 ffprobe 真 FLAC 校验
# 仍然把关,若 740 给的不是 FLAC 会被 validate_flac 拒绝,不会混入有损文件。
BR_FALLBACK = [999, 740]

def curl_json(url, timeout=15):
    try:
        req = Request(url, headers={{"User-Agent": "Mozilla/5.0"}})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except:
        return None

def norm_text(text):
    return "".join(ch.lower() for ch in (text or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")

def artist_match_level(r, artist):
    """0=不匹配 1=可疑(疑似冒名,如'周杰伦-A-LNK'蹭名) 2=精确。

    冒名账号专门构造'目标歌手名+杂质'的名字蹭搜索(netease 上充斥这类
    假歌:同名歌名、完全不同的作品)。指定歌手时只有整体精确相等才算 2。
    """
    if not artist:
        return 2
    t = norm_text(artist)
    joined = norm_text("".join(r.get("artist", [])))
    if joined == t:
        return 2
    if t in joined:
        return 1
    return 0

def search_candidates(song_name, artist="", source="kuwo", count=CANDIDATES_PER_SOURCE):
    """搜索单个音源，返回过滤+按歌手匹配度排序的候选。"""
    kw = f"{{song_name}} {{artist}}" if artist else song_name
    candidates = []
    url = f"{{GD_API}}?types=search&source={{source}}&name={{quote(kw)}}&count={{count}}"
    results = curl_json(url, timeout=10)
    if not results:
        return candidates
    for r in results:
        candidate_name = r.get("name", "")
        q_norm = norm_text(song_name)
        c_norm = norm_text(candidate_name)
        if q_norm and q_norm not in c_norm and c_norm not in q_norm:
            continue
        r["_source"] = source
        r["_artist_level"] = artist_match_level(r, artist)
        if r["_artist_level"] == 0 and artist:
            continue
        candidates.append(r)
    candidates.sort(key=lambda r: -r["_artist_level"])
    return candidates[:count]

def validate_flac(path):
    """Verify the downloaded file is a decodable FLAC, not just a large blob."""
    try:
        if path.read_bytes()[:4] != b"fLaC":
            return False, "不是 FLAC 文件头"
    except Exception as exc:
        return False, "读取失败: " + str(exc)[:80]

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,bit_rate:stream=codec_name,sample_rate",
            "-of", "default=noprint_wrappers=1",
            str(path),
        ],
        capture_output=True, text=True, timeout=15,
    )
    if probe.returncode != 0:
        return False, (probe.stderr or probe.stdout or "ffprobe 验证失败").strip()[:120]

    info = probe.stdout or ""
    if "codec_name=flac" not in info or "sample_rate=0" in info or "duration=N/A" in info:
        return False, "ffprobe 未读到有效 FLAC 音频参数"
    return True, "FLAC 验证通过"

# ===== 主流程 =====
start = time.time()
print(f"🔍 搜索：{{SONG_NAME}} {{ARTIST}}")

selected = None
last_error = ""
searched_any = False
for source in SOURCES:
    print(f"🎧 尝试音源：{{source}}")
    candidates = search_candidates(SONG_NAME, ARTIST, source=source)
    if not candidates:
        last_error = f"{{source}} 未找到候选"
        print("  ↳ 当前源无候选，切换下一个源")
        continue

    searched_any = True
    no_link_count = 0
    for song in candidates:
        song_id = song.get("id")
        found_artist = "".join(song.get("artist", []))
        found_name = song.get("name", SONG_NAME)

        # 防冒名：指定了歌手但候选歌手非精确匹配(如'周杰伦-/A-LNK')时,
        # 默认拒绝——这类条目多为蹭名假歌(同名不同曲),宁可失败不下假歌。
        if ARTIST and song.get("_artist_level", 0) < 2 and not ALLOW_FUZZY_ARTIST:
            last_error = f"仅找到疑似冒名资源({{found_artist}}),官方版本可能受版权限制"
            print(f"  ↳ 跳过疑似冒名：{{found_name}} - {{found_artist}}")
            continue
        print(f"✅ 候选：{{found_name}} - {{found_artist}} [{{source}}]")

        url_data = None
        for br in BR_FALLBACK:
            data = curl_json(
                f"{{GD_API}}?types=url&id={{song_id}}&source={{source}}&br={{br}}",
                timeout=URL_LOOKUP_TIMEOUT,
            )
            if data and data.get("url"):
                url_data = data
                if br != 999:
                    print(f"  ↳ 无损(999)无链接，降用 br={{br}}（仍须通过 FLAC 校验）")
                break
        if not url_data:
            no_link_count += 1
            last_error = f"{{source}} 无下载链接"
            print("  ↳ 跳过：无下载链接")
            if no_link_count >= MAX_NO_LINK_PER_SOURCE:
                print("  ↳ 当前源连续无下载链接，切换下一个源")
                break
            continue
        no_link_count = 0

        safe_artist = found_artist.replace("/", "_").replace("\\", "_").strip() or "未知歌手"
        safe_name = found_name.replace("/", "_").replace("\\", "_").strip() or SONG_NAME
        artist_dir = Path(MEDIA_DIR) / safe_artist
        artist_dir.mkdir(parents=True, exist_ok=True)
        flac_path = artist_dir / f"{{safe_name}}.flac"

        print("⬇️ 下载中...")
        dl_cmd = ["curl", "-s", "-L", "--fail", "--max-time", "25", "-o", str(flac_path), url_data["url"]]
        result = subprocess.run(dl_cmd, capture_output=True, timeout=30)
        if result.returncode != 0 or not flac_path.exists() or flac_path.stat().st_size < 500000:
            last_error = (result.stderr.decode(errors="ignore") if isinstance(result.stderr, bytes) else result.stderr) or "下载失败"
            print("  ↳ 跳过：下载失败")
            try:
                flac_path.unlink()
            except FileNotFoundError:
                pass
            continue

        ok, reason = validate_flac(flac_path)
        if not ok:
            last_error = reason
            print(f"  ↳ 跳过：{{reason}}")
            try:
                flac_path.unlink()
            except FileNotFoundError:
                pass
            continue

        selected = (song, source, found_name, found_artist, safe_artist, safe_name, artist_dir, flac_path)
        break

    if selected:
        break
    print(f"  ↳ {{source}} 源不可用，切换下一个源")

if not selected:
    reason = last_error or ("所有音源均无候选" if not searched_any else "候选均不可用")
    print(f"❌ 未下载到有效 FLAC：{{reason}}")
    sys.exit(1)

song, source, found_name, found_artist, safe_artist, safe_name, artist_dir, flac_path = selected
actual_size = flac_path.stat().st_size // 1024 // 1024
os.chmod(str(flac_path), 0o664)
print(f"✅ 下载完成 ({{actual_size}}MB, FLAC)")

# 刮削：mutagen 在 NAS 本地直接写标签+封面。
# 不再依赖 music-tag-web 容器（旧方案 docker exec 的 scrape_music.py 是手工
# 塞进容器的，容器更新重建即丢失；且 MTW 只挂载 /vol2 音乐库，本就看不见
# 本下载目录）。GD API types=pic 提供封面。
print("🔍 写入元数据/封面...")
has_lyrics = False
try:
    from mutagen.flac import FLAC, Picture
    audio = FLAC(str(flac_path))
    audio["title"] = found_name
    audio["artist"] = found_artist
    album_name = song.get("album") or ""
    if album_name:
        audio["album"] = album_name
    pic_id = song.get("pic_id") or ""
    if pic_id:
        try:
            pic_data = curl_json(
                f"{{GD_API}}?types=pic&id={{quote(str(pic_id))}}&source={{source}}&size=500",
                timeout=10,
            )
            pic_url = pic_data.get("url") if pic_data else ""
            if pic_url:
                pic_req = Request(pic_url, headers={{"User-Agent": "Mozilla/5.0"}})
                img = urlopen(pic_req, timeout=15).read()
                if img and len(img) > 1000:
                    pic = Picture()
                    pic.type = 3
                    pic.mime = "image/jpeg" if img[:3] == b"\xff\xd8\xff" else "image/png"
                    pic.data = img
                    audio.clear_pictures()
                    audio.add_picture(pic)
        except Exception as exc:
            print(f"  ↳ 封面获取失败：{{exc}}")
    audio.save()
    print("✅ 元数据/封面写入完成")
except Exception as exc:
    print(f"⚠️ 刮削异常：{{exc}}")

# 补歌词：如果刮削没有获取到歌词，从 GD API 获取并同时写 .lrc + FLAC 内嵌歌词
if not has_lyrics:
    lyric_data = curl_json(GD_API + "?types=lyric&id=" + str(song_id) + "&source=" + source, timeout=10)
    lyric_text = lyric_data.get("lyric", "") if lyric_data else ""
    if lyric_text and "[" in lyric_text:
        lrc_path = artist_dir / (safe_name + ".lrc")
        lrc_path.write_text(lyric_text, encoding="utf-8")
        os.chmod(str(lrc_path), 0o664)
        embedded_ok = False
        try:
            from mutagen.flac import FLAC
            audio = FLAC(flac_path)
            audio["lyrics"] = lyric_text
            audio.save()
            embedded_ok = True
        except Exception as exc:
            print(f"⚠️ 内嵌歌词失败：{{str(exc)[:120]}}")
        if embedded_ok:
            print("✅ 歌词已补全（.lrc + 内嵌）")
        else:
            print("✅ 歌词已补全（.lrc）")

# 触发 Navidrome 扫库
subprocess.run(["docker", "restart", "navidrome"], capture_output=True, timeout=10)

elapsed = time.time() - start
print(f"✅ 完成！{{found_name}} - {{found_artist}} | {{elapsed:.1f}}秒")
'''


def run_on_nas(song_name, artist=""):
    """通过 SSH 在 NAS 上直接执行下载+刮削"""
    script = NAS_SCRIPT_TEMPLATE.format(
        song_name_repr=repr(song_name),
        artist_repr=repr(artist),
        allow_fuzzy_repr=repr(os.environ.get("MUSIC_ALLOW_FUZZY_ARTIST", "") == "1"),
    )

    cmd = ["ssh", *SSH_OPTIONS, NAS_HOST, "python3", "-"]
    result = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=90)

    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(f"⚠️ stderr: {result.stderr.strip()[:200]}")

    return result.returncode == 0


if __name__ == "__main__":
    song_name = sys.argv[1] if len(sys.argv) > 1 else ""
    artist = sys.argv[2] if len(sys.argv) > 2 else ""

    if not song_name:
        print("用法: python3 music-fast-download.py 歌曲名 [歌手]")
        sys.exit(1)

    success = run_on_nas(song_name, artist)
    sys.exit(0 if success else 1)
