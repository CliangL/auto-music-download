---
name: auto-music-download
description: 多源无损音乐下载、刮削元数据并加入 NAS 媒体库。
version: "3.1.0"
author: "CoPaw (integrated from Hermes)"
commands:
  - name: "/music <歌曲名>"
    description: "搜索并下载音乐到 NAS，自动刮削元数据。"
---

# auto-music-download - 多源无损音乐下载

触发场景：用户要求下载/添加歌曲、无损音乐、FLAC、歌词/封面刮削、加入 Daoliyu/Navidrome 媒体库。

## 执行铁律
每次执行必须先向用户输出主要步骤清单，然后按顺序执行，不能跳步：

1. 登录 SolaraPlus，获取 session cookie。
2. 搜索歌曲，按配置音源顺序执行 `netease -> kuwo`，校验歌名/歌手匹配。
3. 获取下载链接，优先 FLAC/无损，默认 `quality=999`。
4. 下载到 NAS 媒体目录。
5. 调用 Music Tag Web 容器刮削标题、艺术家、专辑、歌词、封面。
6. 触发 Daoliyu/Navidrome 媒体库扫描。

## 推荐入口

```bash
python3 /Users/cliang/.hermes/skills/media/auto-music-download/scripts/music-manager.py "歌曲名" "歌手" --quality 999
```

可选参数：
- `--source netease|kuwo`：指定音源。
- `--quality 999|320`：999 优先 FLAC，无资源时可用 320。

配置文件：`/Users/cliang/.hermes/skills/media/auto-music-download/config.json`。

## 性能约定
- 使用 `music-manager.py`，不要手写多段 SSH。脚本已使用 SSH ControlMaster 复用连接。
- 下载、文件大小校验合并在同一次 SSH 中完成。
- 刮削和文件就绪检查合并在同一次 SSH 中完成。
- 若只是测试，不要直接跑完整下载；用 Python import 调用 `login_solara/search_song/get_download_url`。

## 失败处理
- 搜不到：换音源或补充歌手名后重试。
- 下载链接为空：降低到 `--quality 320` 或换源。
- 刮削失败：不阻塞下载完成，但要告知用户可稍后补刮。
- 媒体库扫描失败：文件仍已下载，提示用户稍后手动刷新。

完整历史说明和排障细节见 `references/full-skill-before-optimization.md`。
