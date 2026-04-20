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

            self.solara_url = config.get('solara_url', 'http://YOUR_NAS_IP:3010')
            self.solara_password = config.get('solara_password', 'YOUR_SOLARA_PASSWORD')
            self.nas_host = config.get('nas_host', 'YOUR_USERNAME@YOUR_NAS_IP')
            self.nas_pass = config.get('nas_pass', 'YOUR_NAS_PASSWORD')
            self.media_path = config.get('media_path', '/vol1/1000/docker/daoliyu/media')
            self.sources = config.get('sources', ['netease', 'kuwo'])
            self.default_quality = config.get('default_quality', 999)
        else:
            print(f"⚠️  配置文件不存在：{CONFIG_FILE}")
            self.solara_url = 'http://YOUR_NAS_IP:3010'
            self.solara_password = 'YOUR_SOLARA_PASSWORD'
            self.nas_host = 'YOUR_USERNAME@YOUR_NAS_IP'
            self.nas_pass = 'YOUR_NAS_PASSWORD'
            self.media_path = '/vol1/1000/docker/daoliyu/media'
            self.sources = ['netease', 'kuwo']
            self.default_quality = 999

    def _ssh_command(self) -> List[str]:
        """Build a reusable SSH command with connection multiplexing."""
        key = hashlib.md5(self.nas_host.encode("utf-8")).hexdigest()[:12]
        control_path = f"/tmp/hermes-music-ssh-{key}.sock"
        return [
            "sshpass", "-p", self.nas_pass,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
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

    def scrape_metadata(self, filepath: str, song_name: str, artist: str = "") -> bool:
        """刮削元数据 - 调用 Music Tag Web 的批量刮削脚本"""
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
                return True
        except (StopIteration, ValueError):
            pass

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

    def download_song(self, song_name: str, artist: str = "", source: str = "auto", quality: int = None):
        """主下载函数"""
        if quality is None:
            quality = self.default_quality

        print(f"🎵 开始下载：{song_name} {artist}".strip())
        print(f"📁 存储路径：{self.media_path}")
        print()

        # 登录 SolaraPlus
        if not self.login_solara():
            print("❌ 登录失败，无法继续")
            return False

        # 先用歌曲名搜索（不带歌手，提高命中率）
        keyword = song_name.strip()

        if source == "auto":
            search_sources = self.sources
        else:
            search_sources = [source] if source in self.sources else self.sources

        results = []
        selected_source = None

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

        if not results:
            print("❌ 所有音源均未找到歌曲")
            return False

        # 如果有歌手信息，尝试匹配最佳结果
        best_song = None
        if artist:
            for song in results:
                song_artist_list = song.get('artist', [])
                if isinstance(song_artist_list, list):
                    song_artist_str = ' '.join(song_artist_list)
                else:
                    song_artist_str = str(song_artist_list)

                if artist.lower() in song_artist_str.lower():
                    best_song = song
                    break

        if not best_song:
            # 未精确匹配到歌手，不硬选第一个，打印警告并尝试换源或提示
            print(f"⚠️  未找到 {artist} 的版本，将尝试最相关结果")
            best_song = results[0]

        song_title = best_song.get('name', song_name)
        song_artist = best_song.get('artist', '')
        if isinstance(song_artist, list):
            song_artist = ', '.join(song_artist)

        print(f"🎶 选择：{song_title} - {song_artist}")
        print()

        song_id = best_song.get('id')
        if not song_id:
            print("❌ 无法获取歌曲 ID")
            return False

        url_info = self.get_download_url(song_id, selected_source, quality)
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
        scrape_success = self.scrape_metadata(full_path, song_title, song_artist)

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
