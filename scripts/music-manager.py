#!/usr/bin/env python3
"""
music-manager.py - 音乐下载管理器
基于 SolaraPlus-ForNas API

用法:
    python3 music-manager.py "歌曲名" ["艺术家"] [--source netease]
"""

import os
import sys
import json
import subprocess
import urllib.parse
import shlex
import hashlib
import re
import base64
from typing import Optional, Dict, List
from pathlib import Path

# 配置
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR.parent / 'config.json'
COOKIE_FILE = SCRIPT_DIR.parent / '.solara_cookies.txt'

class SolaraMusicManager:
    def __init__(self):
        self.load_config()
        self.session_cookies = None
        
    def load_config(self):
        """加载配置文件"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.solara_url = config.get('solara_url', 'http://YOUR_NAS_LAN_IP:3010')
            self.solara_password = config.get('solara_password', 'YOUR_SOLARA_PASSWORD')
            self.nas_host = config.get('nas_host', 'fn-nas')
            self.nas_pass = config.get('nas_pass', 'YOUR_NAS_PASSWORD')
            self.media_path = config.get('media_path', '/vol1/1000/docker/daoliyu/media')
            self.sources = config.get('sources', ['netease', 'kuwo'])
            self.default_quality = config.get('default_quality', 999)
            self.gd_api_base = config.get('gd_api_base', 'https://music-api-hk.gdstudio.xyz/api.php')
        else:
            print(f"⚠️  配置文件不存在：{CONFIG_FILE}")
            self.solara_url = 'http://YOUR_NAS_LAN_IP:3010'
            self.solara_password = 'YOUR_SOLARA_PASSWORD'
            self.nas_host = 'fn-nas'
            self.nas_pass = 'YOUR_NAS_PASSWORD'
            self.media_path = '/vol1/1000/docker/daoliyu/media'
            self.sources = ['netease', 'kuwo']
            self.default_quality = 999
            self.gd_api_base = 'https://music-api-hk.gdstudio.xyz/api.php'
    
    def _ssh_command(self) -> List[str]:
        """Build a reusable SSH command with connection multiplexing."""
        key = hashlib.md5(self.nas_host.encode("utf-8")).hexdigest()[:12]
        control_path = f"/tmp/hermes-music-ssh-{key}.sock"
        return [
            "sshpass", "-p", self.nas_pass,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=15",
            "-o", "ControlMaster=auto",
            "-o", "ControlPersist=120",
            "-o", f"ControlPath={control_path}",
            self.nas_host,
        ]

    def run_ssh(self, cmd: str, timeout: int = 60) -> tuple:
        """执行 SSH 命令。

        Use argv mode instead of shell=True locally, and keep a short-lived SSH
        control socket so the many required workflow steps do not each pay a
        full SSH handshake.
        """
        try:
            result = subprocess.run(
                self._ssh_command() + [cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "SSH 命令执行超时"
        except Exception as e:
            return 1, "", f"SSH 命令执行异常：{str(e)}"
    
    def login_solara(self) -> bool:
        """登录 SolaraPlus"""
        print("🔐 登录 SolaraPlus...")
        
        # 在 NAS 上执行登录 - 使用 base64 编码避免转义问题
        import base64
        json_data = json.dumps({"password": self.solara_password})
        login_data = base64.b64encode(json_data.encode()).decode()
        
        login_cmd = f"echo '{login_data}' | base64 -d | curl -s -X POST '{self.solara_url}/api/login' -H 'Content-Type: application/json' -d @- -c /tmp/solara_cookies.txt"
        
        code, stdout, stderr = self.run_ssh(login_cmd)
        
        if code == 0 and '"success":true' in stdout:
            print("✅ SolaraPlus 登录成功")
            return True
        else:
            print(f"❌ SolaraPlus 登录失败：{stderr or stdout}")
            return False
    
    def search_song(self, keyword: str, source: str = "netease", count: int = 5) -> List[Dict]:
        """搜索歌曲"""
        encoded_kw = urllib.parse.quote(keyword)
        
        # 移除 URL 末尾的斜杠（如果有）
        base_url = self.solara_url.rstrip('/')
        
        search_cmd = f"curl -s '{base_url}/proxy?types=search&source={source}&name={encoded_kw}&count={count}&pages=1&s=test' -b /tmp/solara_cookies.txt"
        
        code, stdout, stderr = self.run_ssh(search_cmd)
        
        if code != 0 or not stdout or stdout == '[]':
            return []
        
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                for item in data:
                    item['_source'] = source
                return data
            return []
        except json.JSONDecodeError:
            return []
    
    def get_download_url(self, song_id: str, source: str = "netease", quality: int = 999) -> Optional[Dict]:
        """获取下载链接"""
        url_cmd = f"""
curl -s '{self.solara_url}/proxy?types=url&id={song_id}&source={source}&br={quality}&s=test' \
  -b /tmp/solara_cookies.txt
"""
        
        code, stdout, stderr = self.run_ssh(url_cmd)
        
        if code != 0 or not stdout:
            return None
        
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return None
    
    # ========== GD API Fallback (when SolaraPlus fails) ==========
    
    def search_song_gd_api(self, keyword: str, source: str = "netease", count: int = 5) -> List[Dict]:
        """搜索歌曲 - GD API fallback（直接从 Mac 调用，不需 NAS 中转）"""
        import urllib.request
        encoded_kw = urllib.parse.quote(keyword)
        url = f"{self.gd_api_base}?types=search&source={source}&name={encoded_kw}&count={count}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list):
                for item in data:
                    item['_source'] = source
                    item['_gd_api'] = True  # 标记来源
                return data
            return []
        except Exception as e:
            print(f"⚠️  GD API 搜索失败：{str(e)[:80]}")
            return []
    
    def get_download_url_gd_api(self, song_id: str, source: str = "netease", quality: int = 999) -> Optional[Dict]:
        """获取下载链接 - GD API fallback"""
        import urllib.request
        url = f"{self.gd_api_base}?types=url&id={song_id}&source={source}&br={quality}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
            if data and 'url' in data:
                data['_gd_api'] = True
                return data
            return None
        except Exception as e:
            print(f"⚠️  GD API 获取链接失败：{str(e)[:80]}")
            return None
    
    def fetch_lyric_gd_api(self, song_id: str, source: str = "netease") -> str:
        """获取歌词 - GD API fallback"""
        import urllib.request
        url = f"{self.GD_API_BASE}?types=lyric&id={song_id}&source={source}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
            lyric = data.get('lyric') or data.get('lrc') or ''
            return lyric if self._is_valid_lrc_text(lyric) else ''
        except Exception:
            return ''
    
    def download_to_nas(self, url: str, filepath: str) -> bool:
        """下载文件到 NAS，并在同一次 SSH 中完成目录创建、下载和大小校验。"""
        dir_path = os.path.dirname(filepath)
        q_dir = shlex.quote(dir_path)
        q_url = shlex.quote(url)
        q_file = shlex.quote(filepath)
        cmd = (
            f"mkdir -p {q_dir} && "
            f"curl -s -L --fail --max-time 180 {q_url} -o {q_file}; "
            "rc=$?; "
            f"size=$(stat -c%s {q_file} 2>/dev/null || echo 0); "
            "echo __CURL_RC:$rc; echo __FILE_SIZE:$size; "
            f"if [ $rc -ne 0 ] || [ $size -le 1024 ]; then rm -f {q_file}; exit 2; fi"
        )
        code, stdout, stderr = self.run_ssh(cmd, timeout=240)

        size = 0
        for line in stdout.splitlines():
            if line.startswith("__FILE_SIZE:"):
                try:
                    size = int(line.split(":", 1)[1].strip())
                except ValueError:
                    size = 0

        if code == 0 and size > 1024:
            print(f"✅ 下载成功：{size // 1024}KB")
            return True

        if size and size <= 1024:
            print(f"❌ 文件太小可能无效：{size}字节")
        else:
            print(f"❌ 下载失败：{stderr or stdout}")
        return False
    
    def _container_media_path(self, filepath: str) -> str:
        """Map NAS host media path to music-tag-web container media path."""
        media_root = self.media_path.rstrip('/')
        if filepath.startswith(media_root + '/'):
            rel = filepath[len(media_root):].lstrip('/')
            return f"/app/media/{rel}"
        if filepath == media_root:
            return "/app/media"
        return filepath

    def _is_valid_lrc_text(self, text: str) -> bool:
        """Return True only when lyrics contain real timestamped LRC lines."""
        compact = (text or "").strip()
        if not compact or compact == "None":
            return False
        return bool(re.search(r"\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]", compact))

    def fetch_lyric_from_solara(self, song_id: str, source: str = "netease") -> str:
        """Fetch timestamped lyrics directly from SolaraPlus. Used when tags have no valid lyrics."""
        if not song_id:
            return ""
        cmd = f"curl -s {shlex.quote(self.solara_url.rstrip() + f'/proxy?types=lyric&id={song_id}&source={source}&s=test')} -b /tmp/solara_cookies.txt"
        code, stdout, stderr = self.run_ssh(cmd, timeout=30)
        if code != 0 or not stdout:
            return ""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return ""
        lyric = data.get("lyric") or data.get("lrc") or ""
        return lyric if self._is_valid_lrc_text(lyric) else ""

    def write_lrc_file(self, lrc_path: str, lyric: str) -> bool:
        """Write a validated .lrc file on NAS."""
        if not self._is_valid_lrc_text(lyric):
            return False
        import base64
        payload = base64.b64encode((lyric.rstrip() + "\n").encode("utf-8")).decode()
        q_lrc_path = shlex.quote(lrc_path)
        cmd = f"mkdir -p $(dirname {q_lrc_path}) && echo {shlex.quote(payload)} | base64 -d > {q_lrc_path}; stat -c%s {q_lrc_path}"
        code, stdout, stderr = self.run_ssh(cmd, timeout=30)
        try:
            return code == 0 and int(stdout.strip().splitlines()[-1]) > 32
        except Exception:
            return False

    def scrape_metadata(self, filepath: str, song_name: str, artist: str = "", source: str = "netease", song_id: str = "") -> bool:
        """刮削元数据 - 调用 Music Tag Web 的批量刮削脚本，并生成有效 .lrc 文件"""
        print(f"🔍 刮削元数据：{song_name}")
        
        # 直接运行 Music Tag Web 的批量刮削脚本，屏蔽 Python 警告避免误判。
        # 刮削和文件存在性检查合并为一次 SSH，减少固定等待时间。
        q_file = shlex.quote(filepath)
        cmd = (
            "docker exec music-tag-web python -W ignore /app/scrape_music.py; "
            "rc=$?; "
            f"size=$(stat -c%s {q_file} 2>/dev/null || echo 0); "
            "echo __SCRAPE_RC:$rc; echo __FILE_SIZE:$size; exit 0"
        )
        code, stdout, stderr = self.run_ssh(cmd, timeout=120)

        try:
            size_line = next((line for line in stdout.splitlines() if line.startswith("__FILE_SIZE:")), "__FILE_SIZE:0")
            size = int(size_line.split(":", 1)[1].strip())
            if size > 1024:
                print("✅ 元数据刮削完成（文件已就绪）")
        except (StopIteration, ValueError):
            pass

        # 生成 .lrc 文件：从元数据提取歌词。注意 music-tag-web 容器内媒体目录是 /app/media，
        # 宿主机路径 /vol1/.../media 在容器内不可见，必须映射后再读标签。
        lrc_path = filepath.rsplit('.', 1)[0] + '.lrc'
        container_filepath = self._container_media_path(filepath)
        q_container_file = shlex.quote(container_filepath)
        q_lrc_path = shlex.quote(lrc_path)
        lrc_cmd = f'''
lrc_tmp=$(mktemp)
docker exec music-tag-web python3 -c "
import music_tag, sys
f = music_tag.load_file(sys.argv[1])
lyrics = str(f.get('lyrics') or '')
print(lyrics)
" {q_container_file} > "$lrc_tmp" 2>/dev/null
if [ -s "$lrc_tmp" ] && [ "$(tr -d '\\r\\n ' < "$lrc_tmp")" != "None" ]; then
    cp "$lrc_tmp" {q_lrc_path}
    rm -f "$lrc_tmp"
    echo "__LRC_OK:1"
else
    rm -f "$lrc_tmp"
    echo "__LRC_OK:0"
fi
'''
        lrc_code, lrc_stdout, lrc_stderr = self.run_ssh(lrc_cmd, timeout=30)
        
        # Validate generated LRC: a 1-byte/blank .lrc also makes players think lyrics are missing.
        validate_cmd = rf'''
python3 - <<'PY'
from pathlib import Path
import re
p = Path({lrc_path!r})
s = p.read_text(encoding='utf-8-sig', errors='ignore') if p.exists() else ''
print('1' if re.search(r'\[\d{{1,2}}:\d{{2}}(?:\.\d{{1,3}})?\]', s) else '0')
PY
'''
        _, validate_stdout, _ = self.run_ssh(validate_cmd, timeout=15)
        if validate_stdout.strip().endswith("1"):
            print(f"✅ 歌词文件已生成：{os.path.basename(lrc_path)}")
        else:
            lyric = self.fetch_lyric_from_solara(song_id, source)
            if self.write_lrc_file(lrc_path, lyric):
                print(f"✅ 歌词文件已从 Solara 补全：{os.path.basename(lrc_path)}")
            else:
                # GD API fallback for lyrics
                lyric = self.fetch_lyric_gd_api(song_id, source)
                if self.write_lrc_file(lrc_path, lyric):
                    print(f"✅ 歌词文件已从 GD API 补全：{os.path.basename(lrc_path)}")
                else:
                    # Remove invalid blank file so players do not cache an empty lyric.
                    self.run_ssh(f"rm -f {shlex.quote(lrc_path)}", timeout=10)
                    print(f"⚠️  未找到有效歌词，已移除无效 .lrc")

        if code == 0 and ("✅" in stdout or "成功" in stdout or "歌词" in stdout):
            print("✅ 元数据刮削成功")
            return True
        elif code == 0:
            return True
        else:
            print(f"⚠️  刮削脚本返回异常：{stderr[:100] if stderr else '未知'}（文件已下载，可稍后补刮）")
            return True  # 文件已存在，不阻塞流程
    
    def trigger_library_scan(self) -> bool:
        """触发媒体库扫描"""
        print("🔄 触发媒体库扫描...")
        
        # 尝试重启 navidrome 或 daoliyu-backend
        code, stdout, stderr = self.run_ssh("docker restart navidrome 2>/dev/null || docker restart daoliyu-backend", timeout=30)
        
        if code == 0:
            print("✅ 媒体库扫描已触发")
            return True
        else:
            print(f"⚠️  媒体库扫描失败：{stderr}")
            return False
    
    def sanitize_filename(self, text: str) -> str:
        """清理文件名"""
        import re
        text = re.sub(r'[^\w\u4e00-\u9fa5_-]', '', text)
        return text.strip()[:100]

    def _normalize_match_text(self, text: str) -> str:
        return re.sub(r'[\s\-_·・（）()【】\[\]《》"\'“”‘’]+', '', (text or '').lower())

    def _stringify_artist(self, artist_value) -> str:
        if isinstance(artist_value, list):
            return ', '.join(str(x) for x in artist_value if x)
        return str(artist_value or '')

    def select_best_search_result(self, results: List[Dict], artist: str = "") -> Optional[Dict]:
        """Pick the best Solara search result for the requested artist/title."""
        best_song = None
        artist_norm = self._normalize_match_text(artist)
        if artist_norm:
            for song in results:
                song_artist = self._stringify_artist(song.get('artist', ''))
                if artist_norm and artist_norm in self._normalize_match_text(song_artist):
                    best_song = song
                    break
        if not best_song and results:
            best_song = results[0]
        return best_song

    def find_existing_track(self, song_name: str, artist: str = "") -> Optional[Dict]:
        """Search NAS media library for an existing local track candidate."""
        print("🔎 检查 NAS 本地是否已有歌曲...")
        payload = base64.b64encode(json.dumps({
            "media_path": self.media_path,
            "song": song_name,
            "artist": artist,
        }, ensure_ascii=False).encode("utf-8")).decode("ascii")
        cmd = """python3 - <<'PY'
import base64
import json
import re
from pathlib import Path

cfg = json.loads(base64.b64decode(PAYLOAD_PLACEHOLDER).decode("utf-8"))
root = Path(cfg["media_path"])
song = cfg["song"]
artist = cfg["artist"]
audio_exts = {".flac", ".mp3", ".m4a", ".ape", ".wav"}

def norm(text: str) -> str:
    return re.sub(r'[\\s\\-_·・（）()【】\\[\\]《》"\\'“”‘’]+', '', (text or '').lower())

song_norm = norm(song)
artist_norm = norm(artist)
hits = []
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in audio_exts:
        continue
    rel = str(path.relative_to(root))
    stem_norm = norm(path.stem)
    rel_norm = norm(rel)
    if song_norm and song_norm not in stem_norm and song_norm not in rel_norm:
        continue
    score = 0
    if song_norm and song_norm in stem_norm:
        score += 8
    if song_norm and song_norm in rel_norm:
        score += 4
    if artist_norm:
        if artist_norm in rel_norm or artist_norm in stem_norm:
            score += 5
        else:
            score -= 3
    if path.suffix.lower() == ".flac":
        score += 2
    hits.append({
        "score": score,
        "path": str(path),
        "size": path.stat().st_size,
        "suffix": path.suffix.lower(),
        "name": path.name,
    })

hits.sort(key=lambda item: (item["score"], item["size"]), reverse=True)
print(json.dumps({
    "count": len(hits),
    "best": hits[0] if hits else None,
    "candidates": hits[:5],
}, ensure_ascii=False))
PY""".replace("PAYLOAD_PLACEHOLDER", repr(payload))
        code, stdout, stderr = self.run_ssh(cmd, timeout=45)
        if code != 0 or not stdout.strip():
            if stderr.strip():
                print(f"⚠️  本地歌曲检查失败：{stderr.strip()[:160]}")
            return None
        try:
            payload = json.loads(stdout.strip().splitlines()[-1])
        except Exception:
            return None
        best = payload.get("best")
        if not best:
            print("📭 本地未找到同名候选，走下载流程")
            return None
        print(f"✅ 命中本地候选：{best['path']} (score={best['score']}, size={best['size'] // 1024}KB)")
        return best

    def _remote_lrc_is_valid(self, lrc_path: str) -> bool:
        cmd = f"""python3 - <<'PY'
from pathlib import Path
import re
p = Path({lrc_path!r})
text = p.read_text(encoding='utf-8-sig', errors='ignore') if p.exists() else ''
print('1' if re.search(r'\\[\\d{{1,2}}:\\d{{2}}(?:\\.\\d{{1,3}})?\\]', text) else '0')
PY"""
        code, stdout, _ = self.run_ssh(cmd, timeout=15)
        return code == 0 and stdout.strip().endswith("1")

    def _ensure_lrc_permissions(self, lrc_path: str) -> bool:
        q_lrc = shlex.quote(lrc_path)
        code, stdout, _ = self.run_ssh(
            f"test -f {q_lrc} || exit 2; chmod 660 {q_lrc}; stat -c '%a' {q_lrc}",
            timeout=15,
        )
        return code == 0 and stdout.strip().splitlines()[-1] >= "660"

    def _has_embedded_lyrics(self, filepath: str) -> bool:
        q_file = shlex.quote(filepath)
        code, stdout, _ = self.run_ssh(
            f"ffprobe -v error -show_entries format_tags -of json {q_file}",
            timeout=20,
        )
        if code != 0 or not stdout.strip():
            return False
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return False
        tags = (data.get("format") or {}).get("tags") or {}
        for key, value in tags.items():
            if "LYRIC" in str(key).upper() and str(value or "").strip():
                return True
        return False

    def _embed_lyrics_tags(self, filepath: str, lrc_path: str) -> bool:
        if not self._remote_lrc_is_valid(lrc_path):
            return False
        ext = Path(filepath).suffix or ".flac"
        tmp_path = f"{filepath}.tmp{ext}"
        q_file = shlex.quote(filepath)
        q_lrc = shlex.quote(lrc_path)
        q_tmp = shlex.quote(tmp_path)
        cmd = f"""set -e
F={q_file}
L={q_lrc}
TMP={q_tmp}
ffmpeg -y -hide_banner -loglevel error -i "$F" -map 0 -c copy \
  -metadata lyrics="$(cat "$L")" \
  -metadata LYRICS="$(cat "$L")" \
  -metadata UNSYNCEDLYRICS="$(cat "$L")" \
  -metadata SYNCEDLYRICS="$(cat "$L")" \
  "$TMP"
mv -f "$TMP" "$F"
touch "$F" "$L"
"""
        code, _, stderr = self.run_ssh(cmd, timeout=120)
        if code != 0:
            print(f"⚠️  内嵌歌词写入失败：{stderr[:160] if stderr else '未知错误'}")
            return False
        return self._has_embedded_lyrics(filepath)

    def _verify_library_lyrics(self, song_name: str, filepath: str) -> None:
        needle = song_name.replace("'", "''")
        basename = Path(filepath).stem.replace("'", "''")
        nav_cmd = (
            "sqlite3 /vol1/1000/docker/navidrome/navidrome.db "
            + shlex.quote(
                f"select title,length(lyrics) from media_file "
                f"where title like '%{needle}%' or path like '%{basename}%';"
            )
        )
        _, nav_stdout, nav_stderr = self.run_ssh(nav_cmd, timeout=20)
        if nav_stdout.strip():
            print(f"📚 Navidrome 验证：{nav_stdout.strip().splitlines()[:3]}")
        elif nav_stderr.strip():
            print(f"⚠️  Navidrome 验证失败：{nav_stderr.strip()[:160]}")
        else:
            print("📚 Navidrome 验证：未查到匹配记录")

        psql_sql = (
            f"select \"title\",length(\"lyrics\") from \"Track\" "
            f"where \"title\" like '%{needle}%' or \"filePath\" like '%{basename}%';"
        )
        psql_cmd = (
            "docker exec daoliyu-postgres psql -h localhost -p 5433 "
            "-U daoliyu -d daoliyu -At -F '|' -c "
            + shlex.quote(psql_sql)
        )
        _, pg_stdout, pg_stderr = self.run_ssh(psql_cmd, timeout=25)
        if pg_stdout.strip():
            print(f"🎼 Daoliyu 验证：{pg_stdout.strip().splitlines()[:3]}")
        elif pg_stderr.strip():
            print(f"⚠️  Daoliyu 验证失败：{pg_stderr.strip()[:160]}")
        else:
            print("🎼 Daoliyu 验证：未查到匹配记录")

    def repair_existing_track(self, filepath: str, song_name: str, artist: str = "") -> bool:
        """Repair/verify an already-downloaded track instead of re-downloading it."""
        print(f"🩹 进入本地已有歌曲快路径：{filepath}")
        lrc_path = filepath.rsplit('.', 1)[0] + '.lrc'
        lrc_valid = self._remote_lrc_is_valid(lrc_path)
        embedded_ok = self._has_embedded_lyrics(filepath)
        if lrc_valid and embedded_ok:
            print("✅ 本地歌曲已具备有效 LRC 和内嵌歌词，直接触发扫描验证")
            self._ensure_lrc_permissions(lrc_path)
            self.trigger_library_scan()
            self._verify_library_lyrics(song_name, filepath)
            print("🎉 完成！复用本地歌曲，无需重新下载")
            return True

        if not self.login_solara():
            print("❌ 登录失败，无法修复本地歌曲歌词/元数据")
            return False

        results = []
        selected_source = None
        for src in self.sources:
            src_results = self.search_song(song_name.strip(), src)
            if src_results:
                print(f"✅ {src}: 找到 {len(src_results)} 个结果用于补全元数据")
                results = src_results
                selected_source = src
                break
        best_song = self.select_best_search_result(results, artist) if results else None
        song_id = str(best_song.get('id')) if best_song and best_song.get('id') else ""
        song_artist = artist or (self._stringify_artist(best_song.get('artist', '')) if best_song else "")
        source_name = selected_source or (self.sources[0] if self.sources else "netease")

        print("🔍 补刮元数据与歌词...")
        self.scrape_metadata(filepath, song_name, song_artist, source_name, song_id)
        if not self._remote_lrc_is_valid(lrc_path) and song_id:
            lyric = self.fetch_lyric_from_solara(song_id, source_name)
            if self.write_lrc_file(lrc_path, lyric):
                print("✅ 已从 Solara 直接补写有效 LRC")
        if self._remote_lrc_is_valid(lrc_path):
            self._ensure_lrc_permissions(lrc_path)
            if self._embed_lyrics_tags(filepath, lrc_path):
                print("✅ 已补写内嵌歌词 tag")
            else:
                print("⚠️  旁挂 LRC 已修好，但内嵌歌词仍未确认")
        else:
            print("⚠️  仍未拿到有效 LRC，保留现有音频文件")

        self.trigger_library_scan()
        self._verify_library_lyrics(song_name, filepath)
        print("🎉 完成！本地已有歌曲已走修复快路径")
        return True
    
    def download_song(self, song_name: str, artist: str = "", source: str = "auto", quality: int = None):
        """主下载函数"""
        if quality is None:
            quality = self.default_quality
            
        print(f"🎵 开始下载：{song_name} {artist}".strip())
        print(f"📁 存储路径：{self.media_path}")
        print()

        existing_track = self.find_existing_track(song_name, artist)
        if existing_track and existing_track.get("path"):
            return self.repair_existing_track(existing_track["path"], song_name, artist)
        
        # 登录 SolaraPlus
        if not self.login_solara():
            print("⚠️  SolaraPlus 登录失败，尝试 GD API fallback")
            use_gd_api = True
        else:
            use_gd_api = False
        
        # 先用歌曲名搜索（不带歌手，提高命中率）
        keyword = song_name.strip()
        
        if source == "auto":
            search_sources = self.sources
        else:
            search_sources = [source] if source in self.sources else self.sources
        
        results = []
        selected_source = None
        
        # 优先尝试 SolaraPlus，失败则切换 GD API
        if not use_gd_api:
            for src in search_sources:
                src_results = self.search_song(keyword, src)
                if src_results:
                    print(f"✅ {src}: 找到 {len(src_results)} 个结果")
                    results.extend(src_results)
                    if not selected_source:
                        selected_source = src
                    break
                else:
                    print(f"⚠️  {src}: 无结果")
            
            # SolaraPlus 全音源失败 → GD API fallback
            if not results:
                print("⚠️  SolaraPlus 所有音源均无结果，切换 GD API")
                use_gd_api = True
        
        if use_gd_api:
            print("🔍 使用 GD API fallback 搜索...")
            for src in search_sources:
                gd_results = self.search_song_gd_api(keyword, src)
                if gd_results:
                    print(f"✅ GD API {src}: 找到 {len(gd_results)} 个结果")
                    results.extend(gd_results)
                    if not selected_source:
                        selected_source = src
                    break
                else:
                    print(f"⚠️  GD API {src}: 无结果")
        
        if not results:
            print("❌ 所有音源均未找到歌曲")
            return False
        
        # 如果有歌手信息，尝试匹配最佳结果
        best_song = self.select_best_search_result(results, artist)
        if not best_song:
            print("❌ 搜索结果为空，无法继续")
            return False
        if artist and self._normalize_match_text(artist) not in self._normalize_match_text(self._stringify_artist(best_song.get('artist', ''))):
            print(f"⚠️  未找到 {artist} 的精确版本，将尝试最相关结果")
        
        song_title = best_song.get('name', song_name)
        song_artist = self._stringify_artist(best_song.get('artist', ''))
        
        print(f"🎶 选择：{song_title} - {song_artist}")
        print()
        
        song_id = best_song.get('id')
        if not song_id:
            print("❌ 无法获取歌曲 ID")
            return False
        
        # 获取下载链接 - 根据来源选择 API
        is_gd_api_song = best_song.get('_gd_api', False)
        if is_gd_api_song:
            url_info = self.get_download_url_gd_api(song_id, selected_source, quality)
        else:
            url_info = self.get_download_url(song_id, selected_source, quality)
            # SolaraPlus 失败 → GD API fallback
            if not url_info or 'url' not in url_info:
                print("⚠️  SolaraPlus 无法获取下载链接，尝试 GD API fallback")
                url_info = self.get_download_url_gd_api(song_id, selected_source, quality)
        
        if not url_info or 'url' not in url_info:
            print("❌ 无法获取下载链接")
            return False
        
        download_url = url_info['url']
        actual_br = url_info.get('br', 0)
        file_size = url_info.get('size', 0)
        
        print(f"📊 音质：{actual_br}kbps, 大小：{file_size // 1024 // 1024}MB")
        print(f"🔗 来源：{selected_source}")
        print()
        
        safe_artist = self.sanitize_filename(song_artist) if song_artist else "未知歌手"
        safe_title = self.sanitize_filename(song_title)
        ext = "flac" if actual_br >= 500 else "mp3"
        filename = f"{safe_artist}/{safe_artist} - {safe_title}.{ext}"
        full_path = os.path.join(self.media_path, filename)
        
        print(f"⬇️  下载到：{filename}")
        
        if not self.download_to_nas(download_url, full_path):
            return False
        
        print()
        print("🔍 开始刮削元数据...")
        scrape_success = self.scrape_metadata(full_path, song_title, song_artist, selected_source, song_id)
        
        if scrape_success:
            print("✅ 元数据刮削成功（含内嵌歌词）")
        else:
            print("⚠️  元数据刮削部分失败，但文件已下载")
        
        print()
        self.trigger_library_scan()
        
        print()
        print(f"🎉 完成！歌曲已添加到媒体库：{filename}")
        return True

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 music-manager.py \"歌曲名\" [\"歌手\"] [--source netease|kuwo] [--quality 999]")
        print("")
        print("示例:")
        print("  python3 music-manager.py \"感官先生\"")
        print("  python3 music-manager.py \"晴天\" \"周杰伦\"")
        print("  python3 music-manager.py \"童话\" \"光良\" --source netease --quality 999")
        sys.exit(1)
    
    song_name = sys.argv[1]
    artist = ""
    source = "auto"
    quality = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--source" and i + 1 < len(sys.argv):
            source = sys.argv[i + 1]
            i += 1
        elif sys.argv[i] == "--quality" and i + 1 < len(sys.argv):
            quality = int(sys.argv[i + 1])
            i += 1
        elif not artist and not sys.argv[i].startswith("--"):
            artist = sys.argv[i]
        i += 1
    
    manager = SolaraMusicManager()
    success = manager.download_song(song_name, artist, source, quality)
    
    if not success:
        print("❌ 下载失败，请检查网络或尝试其他歌曲")
        sys.exit(1)

if __name__ == "__main__":
    main()
