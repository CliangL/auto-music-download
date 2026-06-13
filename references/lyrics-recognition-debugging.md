# 歌词识别排障：空 LRC、内嵌歌词、Navidrome/Daoliyu 分流

## 背景
本次《迷失幻境》下载后播放器无歌词。初看 `.lrc` 文件存在，但播放器仍不显示。

## 关键结论
1. **不能只判断 `.lrc` 文件存在**：该文件可能只有 1 字节换行，播放器不会识别。
2. 正常歌曲通常同时具备：
   - 旁挂 `.lrc`
   - FLAC/MP3 内嵌 `lyrics` tag
3. 部分播放器/客户端优先读内嵌歌词，旁挂 LRC 不一定生效。
4. Navidrome 与 Daoliyu/飞牛不是同一套库：
   - Navidrome DB 可显示 `media_file.lyrics` 已入库；
   - Daoliyu 后端 `Track` 表可能完全没有这首歌，说明还没扫描进 Daoliyu。
5. Daoliyu 日志出现 `Auto scan processor disabled. Use manual incremental scans only.` 时，重启容器不等于扫描媒体库。

## 快速对比命令
```bash
ssh fn-nas 'python3 - <<"PY"
from pathlib import Path
import re
files = [
  "/vol1/1000/docker/daoliyu/media/歌手/歌手 - 歌名.lrc",
  "/vol1/1000/docker/daoliyu/media/周杰伦/晴天.lrc",
]
for f in files:
    p = Path(f)
    b = p.read_bytes() if p.exists() else b""
    s = b.decode("utf-8-sig", errors="ignore")
    print("===", p, "===")
    print("size", len(b), "lines", len(s.splitlines()), "time_lines", sum(1 for l in s.splitlines() if re.search(r"\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]", l)))
    print("first", s.splitlines()[:3])
PY'
```

## 判断内嵌歌词
```bash
ssh fn-nas 'ffprobe -v error -show_entries format_tags -of json "/vol1/1000/docker/daoliyu/media/歌手/歌手 - 歌名.flac" | grep -i lyric -C 2 || true'
```

## 写入多种 FLAC 歌词 tag
有些播放器认 `lyrics`，有些认大小写或 `UNSYNCEDLYRICS/SYNCEDLYRICS`。修复时统一写入多种 tag：

```bash
ssh fn-nas 'set -e
F="/vol1/1000/docker/daoliyu/media/歌手/歌手 - 歌名.flac"
L="/vol1/1000/docker/daoliyu/media/歌手/歌手 - 歌名.lrc"
TMP="${F%.flac}.tmp.flac"
ffmpeg -y -hide_banner -loglevel error -i "$F" -map 0 -c copy \
  -metadata lyrics="$(cat "$L")" \
  -metadata LYRICS="$(cat "$L")" \
  -metadata UNSYNCEDLYRICS="$(cat "$L")" \
  -metadata SYNCEDLYRICS="$(cat "$L")" \
  "$TMP"
mv -f "$TMP" "$F"
touch "$F" "$L"
'
```

## Navidrome 验证
```bash
ssh fn-nas 'docker restart navidrome >/dev/null || true
sleep 5
sqlite3 /vol1/1000/docker/navidrome/navidrome.db "select title,path,length(lyrics),substr(lyrics,1,120),updated_at from media_file where path like \"%歌名%\";"'
```

## Daoliyu/飞牛验证
```bash
ssh fn-nas 'docker exec daoliyu-postgres psql -h localhost -p 5433 -U daoliyu -d daoliyu -c "select \"id\",\"title\",\"filePath\",length(\"lyrics\") from \"Track\" where \"title\" like '\''%歌名%'\'' or \"filePath\" like '\''%歌名%'\'';"'
```

若 Navidrome 有歌词但 Daoliyu `Track` 没记录，问题不是歌词文件，而是 Daoliyu 扫描/入库链路。

## 坑
- **LRC 文件权限**：脚本默认新建 LRC 权限为 `600`，但 Navidrome/Daoliyu 容器以非 owner 用户运行，读不到。确认 `stat -c '%a'` 返回 >= `660`，否则 `chmod 660`。
- **music-manager.py "含内嵌歌词"声明不可靠**：脚本日志说"元数据刮削成功（含内嵌歌词）"不代表 FLAC 真有 `lyrics` tag。必须 `ffprobe` 实体验证。
- 不要把备份 FLAC 留在媒体目录，否则 Navidrome/Daoliyu 会把 `*.bak-before-lyrics.flac` 也扫成一首歌。
- 备份应移到媒体根目录外，例如 `/vol1/1000/docker/daoliyu/.hermes-backups/lyrics-fix/YYYYMMDD/`。
- `docker restart navidrome` 可让 Navidrome 重读 tag，但不能代表 Daoliyu 已入库。
