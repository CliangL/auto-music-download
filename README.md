# auto-music-download

[English](#english) | [中文](#中文)

一个给 AI agent（Hermes / OpenClaw / Claude Code 等支持 Skill 的运行时）使用的**无损音乐自动下载** Skill。对 agent 说"我想听《XX》"，它就会从多个音源搜索、下载 FLAC 无损到你的 NAS 音乐库，自动写入标签、封面、歌词，并刷新 Navidrome 扫库。

> A **lossless music auto-download** Skill for AI agents. Say "play *X*" and it searches multiple sources, downloads FLAC to your NAS music library, writes tags/cover/lyrics, and refreshes Navidrome.

---

## 中文

### 它能做什么

- **自然语言下载**：对 agent 说"我想听/来一首/下载 XX"，自动搜索 → 下载无损 FLAC → 刮削 → 入库。
- **多源**：netease 优先、kuwo 保底（通过 GDStudio 公共音乐 API），自动按歌手精确匹配。
- **真无损校验**：`ffprobe` 实体验证是真 FLAC，不是改后缀的有损文件。
- **本地刮削**：用 `mutagen` 直接写标题/歌手/专辑 + 封面 + 歌词（外置 `.lrc` 和 FLAC 内嵌），不依赖额外刮削容器。
- **防冒名**：指定歌手时只接受精确匹配，拒绝"同名不同人"的蹭名假歌混进曲库。

### 环境要求

1. **一台 NAS**，可 SSH 登录（下载在 NAS 上执行，直接落到音乐库目录）。
2. NAS 上：`python3` + `mutagen`（`pip install mutagen`）、`ffprobe`（来自 ffmpeg）、`curl`。
3. （推荐）**Navidrome** 容器：播放/管理音乐库，下载后自动重启扫库。
4. **运行 agent 的机器**上：`python3` `ssh`（可选 `sshpass`）。
5. 音源走 **GDStudio 公共 API**（`music-api-hk.gdstudio.xyz`），无需注册、无需 key。

> 注：早期版本依赖 SolaraPlus / MusicTag Web 容器，现已不需要——下载和刮削都在 NAS 本地完成。`config.example.json` 里相关字段保留仅为向后兼容，可留空。

### 安装

```bash
# 1. 克隆到 agent 的 skills 目录
git clone https://github.com/CliangL/auto-music-download.git
cd auto-music-download

# 2. 运行安装脚本：检测依赖，只问 NAS SSH 信息和音乐库路径
bash install.sh
```

`install.sh` 会检测依赖、让你填 **NAS SSH 地址 + 密码** 和 **音乐库目录**，把真实配置写进 `config.json`（已被 `.gitignore` 排除，**不会进 git**）。

### 使用

对 agent 说："我想听《海阔天空》" / "来一首周杰伦的稻香" / "下载 海阔天空 Beyond" → 自动下载入库。

### 配置：哪些自动、哪些要你填

| 项 | 来源 |
|---|---|
| 音源 / GD API | **自动**（公共 API，无需 key） |
| 依赖检测 | **自动** |
| 刮削（标签/封面/歌词） | **自动**（本地 mutagen） |
| NAS SSH 地址 + 密码 | **需你填** |
| 音乐库目录 | 需你填（如 `/vol1/xxx/music`） |

### 已知限制

- **免费音源受版权限制**：全平台 VIP 独占的热门歌（如部分周杰伦官方版）可能没有可用源，脚本会**如实报告"官方版受版权限制"，绝不偷偷下个同名假货**。
- 能下的非独占华语/欧美歌通常 5–15 秒完成，真无损 + 标签齐全。
- kuwo 源依赖第三方 API 稳定性，偶有上游故障（脚本会自动切到 netease）。

---

## English

### What it does

- **Natural-language downloads**: "play *X*" → search, download lossless FLAC, scrape metadata, add to library.
- **Multi-source**: netease first, kuwo fallback (via the public GDStudio music API), with exact-artist matching.
- **Real-lossless verification**: `ffprobe` confirms a genuine FLAC, not a renamed lossy file.
- **Local scraping**: `mutagen` writes title/artist/album + cover + lyrics (external `.lrc` and embedded), no extra scraper container needed.
- **Counterfeit guard**: with a specified artist, only exact matches are accepted — same-title-different-artist fakes are rejected.

### Requirements

1. **A NAS reachable via SSH** (downloads run on the NAS, straight into the music library).
2. On the NAS: `python3` + `mutagen` (`pip install mutagen`), `ffprobe` (from ffmpeg), `curl`.
3. (Recommended) **Navidrome** container — auto-restarted to rescan after download.
4. On the **agent machine**: `python3` `ssh` (optional `sshpass`).
5. Sources use the **public GDStudio API** (`music-api-hk.gdstudio.xyz`) — no signup, no key.

> Note: older versions needed SolaraPlus / MusicTag Web containers — no longer required; download and scraping happen locally on the NAS. Those fields remain in `config.example.json` only for backward compatibility and can be left blank.

### Install

```bash
git clone https://github.com/CliangL/auto-music-download.git
cd auto-music-download
bash install.sh
```

`install.sh` checks deps, asks for **NAS SSH address + password** and the **music library path**, and writes the real config to `config.json` (git-ignored — **never committed**).

### Usage

Talk to the agent: "play *Bohemian Rhapsody*", "download *Hai Kuo Tian Kong* by Beyond".

### Auto vs. manual config

| Item | Source |
|---|---|
| Sources / GD API | **Auto** (public, no key) |
| Dependency detection | **Auto** |
| Scraping (tags/cover/lyrics) | **Auto** (local mutagen) |
| NAS SSH address + password | **You provide** |
| Music library path | You provide |

### Known limitations

- **Free sources are copyright-limited**: platform-exclusive VIP hits may have no available source; the script **honestly reports "official version is copyright-locked" and never silently downloads a same-title fake**.
- Non-exclusive tracks usually finish in 5–15s, real-lossless with full tags.
- kuwo depends on third-party API stability; on upstream failure the script falls back to netease.

---

**安全提示 / Security**: 真实密码只存在本地 `config.json`（已被 `.gitignore` 排除）。Real secrets live only in the git-ignored `config.json` — never commit it.
