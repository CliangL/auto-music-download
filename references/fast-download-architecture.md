# Fast Download Architecture

## 设计目标

**50秒内完成音乐下载全流程**

实测性能：~10.7秒（23-43MB FLAC）

## 核心优化点

### 1. GD API 直搜（无登录开销）

传统流程：
```
登录 SolaraPlus → 获取 cookie → 搜索 → 获取链接
```
耗时：~10-15秒（登录 + timeout）

快速流程：
```
GD API 搜索 → 直接返回歌曲列表 + ID
```
耗时：~2秒

GD API endpoint：
- 搜索：`https://music-api-hk.gdstudio.xyz/api.php?types=search&source=netease&name=...`
- 下载链接：`types=url&id=<song_id>&source=netease&br=999`
- 歌词：`types=lyric&id=<song_id>&source=netease`

**无登录，无 cookie，直接可用**

### 2. Mac 本地下载（绕过 NAS 外网问题）

问题：NAS 外网经常不通（curl 下载失败）

解决：
```
Mac curl 下载 → ~/Downloads/music/歌手/歌曲.flac
→ scp/ssh 直连 `fn-nas` 传到 NAS（Tailscale）；只有直连失败时才经 OECT 到 NAS LAN
```

Mac 外网稳定，下载 43MB FLAC 约 15-20秒

### 3. 并行获取歌词和下载链接

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    fut_url = executor.submit(get_download_url_gd, song_id, 999)
    fut_lyric = executor.submit(get_lyric_gd, song_id)
```

两个 HTTP 请求并行执行，总耗时约 2秒而非 4秒

### 4. 单次 SSH 执行所有 NAS 操作

传统流程：
```
SSH mkdir → SSH chmod → SSH ffmpeg → SSH docker restart
```
多次 SSH 连接开销

快速流程：
```python
# 单次 stdin 传 Python 脚本
nas_script = '''
chmod 660 lrc
ffmpeg 内嵌歌词
docker restart navidrome
'''
ssh fn-nas "python3 -" < nas_script
```

单次 SSH，~5秒完成所有操作

### 5. Python stdin 避免 SSH 引号炸裂

问题：多层 SSH（Mac → OECT → NAS）嵌套时，shell 引号层层解析会炸

错误示例：
```bash
ssh oect "ssh YOUR_USERNAME@... 'ffmpeg ... -metadata lyrics=\"$(cat 越过山丘.lrc)\"'"
# bash: syntax error near unexpected token
```

正确方式：
```bash
cat <<'NASPY' | ssh fn-nas "python3 -"
import subprocess
from pathlib import Path
# Python 代码，无需处理 shell 引号
NASPY
```

## 脚本位置

`$HOME/.openclaw/skills/media/auto-music-download/scripts/music-fast-download.py`

## 何时使用

- 默认音乐下载入口
- SolaraPlus API 挂掉时
- NAS 网络不通时
- 需要快速下载时（50秒目标）

## 何时不用

- 需要检查 NAS 本地是否已有同名歌曲（避免重复） → 用 music-manager.py
- GD API 返回空 → fallback 到 music-manager.py 其他音源
