# auto-music-download - 多源无损音乐下载
# Multi-Source Lossless Music Downloader

🎵 自动从多个音源搜索下载 FLAC 无损音乐，支持自动刮削元数据（封面、歌词、歌手信息）并入库到媒体服务器。
🎵 Automatically searches and downloads FLAC lossless music from multiple sources, with auto-tagging (cover art, lyrics, artist info) and media server integration.

## 使用场景 / Use Cases

- 告诉 AI 助手"我想听 XXX"，自动搜索、下载、刮削、入库一条龙
- 批量下载歌曲到 NAS 媒体库
- 自动选择最佳音源和音质（优先无损 FLAC）
- 自动刮削元数据：封面、歌词、专辑、艺术家信息

## 系统要求 / Requirements

### 必备环境 / Prerequisites

| 组件 | 说明 | 安装方式 |
|------|------|----------|
| **Linux 主机** | 运行 agent（OpenClaw / Hermes）的机器 | 任何 Linux 发行版 |
| **NAS** | 飞牛/群晖等，用于存放音乐和运行服务 | Docker 支持 |
| **Python 3.8+** | 运行下载脚本 | `apt install python3` / `yum install python3` |
| **curl** | API 调用和文件下载 | `apt install curl` / `yum install curl` |
| **sshpass** | SSH 连接到 NAS（无密钥认证） | `apt install sshpass` / `yum install sshpass` |
| **Docker** | 运行音乐服务容器 | 见下方容器列表 |

### 必备 Docker 容器 / Required Containers

| 容器 | 端口 | 说明 | 获取方式 |
|------|------|------|----------|
| **SolaraPlus** | 3010 | 音乐搜索+下载 API，支持网易云/酷我等多源 | 需自行部署在 NAS 上 |
| **Music Tag Web** | 8010 | 自动刮削音乐元数据（封面、歌词、标签） | Docker Hub: `xhongc/music-tag-web` |
| **Navidrome** (可选) | 4533 | 音乐流媒体服务器，支持手机/网页播放 | Docker Hub: `deluan/navidrome` |

### 音源支持 / Supported Sources

| 音源 | 代码 | 说明 |
|------|------|------|
| 网易云音乐 | `netease` | 推荐，无损资源丰富 |
| 酷我音乐 | `kuwo` | 备选，周杰伦等版权多 |

## 配置清单 / Configuration

安装时需要提供以下信息。这些信息用于生成 `config.json`：

| 配置项 | 说明 | 是否必填 | 示例值 | 获取方式 |
|--------|------|----------|--------|----------|
| `solara_url` | SolaraPlus 服务地址 | ✅ 必填 | `http://YOUR_NAS_IP:3010` | NAS 上部署的 SolaraPlus 访问地址 |
| `solara_password` | SolaraPlus 访问密码 | ✅ 必填 | - | 部署 SolaraPlus 时设置的密码 |
| `nas_host` | NAS SSH 地址 | ✅ 必填 | `user@YOUR_NAS_IP` | NAS 的 SSH 用户名和 IP/域名 |
| `nas_pass` | NAS SSH 密码 | ✅ 必填 | - | NAS 的 SSH 登录密码 |
| `media_path` | 音乐存放路径 | ✅ 必填 | `/vol1/xxx/media` | NAS 上的目录路径，Music Tag Web 需挂载此目录 |
| `mtw_url` | Music Tag Web 地址 | ❌ 可选 | `http://YOUR_NAS_IP:8010` | NAS 上 Music Tag Web 的访问地址 |
| `mtw_pass` | Music Tag Web 密码 | ❌ 可选 | - | Music Tag Web 的管理密码 |

## 用户自定义信息 / User Customization

**安装者需要提供给终端或 AI 助手的信息：**

1. **NAS SSH 地址** — 格式：`用户名@IP`，例如 `YOUR_USERNAME@YOUR_NAS_IP`
2. **NAS SSH 密码** — 你的 NAS 登录密码
3. **音乐存放路径** — NAS 上的目录，例如 `/volume1/music`
4. **SolaraPlus 地址和密码** — 部署在 NAS 上的音乐 API 服务
5. **Music Tag Web 地址和密码**（可选）— 用于自动刮削元数据

## 一键安装 / Installation

### 方式一：AI 助手自动安装（推荐）/ AI Assistant Auto-Install

将本仓库链接发给你的 AI 助手（OpenClaw / Hermes 等），助手会自动：

1. 克隆仓库到 skills 目录
2. 运行安装脚本引导你填写配置
3. 自动生成 `config.json`
4. 检测环境依赖是否满足

```bash
# AI 助手会执行：
git clone https://github.com/CliangL/auto-music-download.git
cd auto-music-download
bash install.sh
```

### 方式二：手动安装 / Manual Install

```bash
# 1. 克隆仓库
git clone https://github.com/CliangL/auto-music-download.git
cd auto-music-download

# 2. 运行安装脚本（交互式引导配置）
bash install.sh

# 3. 测试下载
python3 scripts/music-manager.py "测试歌曲"
```

### 方式三：Docker 一键部署 / Docker One-Click Deploy

如果你还没有 SolaraPlus 和 Music Tag Web 容器：

```bash
# 启动 SolaraPlus（音乐搜索 API）
docker run -d --name solara-plus \
  -p 3010:3010 \
  -e PASSWORD=YOUR_PASSWORD \
  --restart unless-stopped \
  YOUR_SOLARA_IMAGE

# 启动 Music Tag Web（元数据刮削）
docker run -d --name music-tag-web \
  -p 8010:8010 \
  -v /your/music/path:/app/media \
  -e MUSIC_TAG_WEB_PASSWORD=YOUR_PASSWORD \
  --restart unless-stopped \
  xhongc/music-tag-web:latest
```

## 使用方法 / Usage

### 通过 AI 助手 / Via AI Assistant

直接告诉 AI 助手：
```
我想听周杰伦的晴天
```
AI 助手会自动调用 `music-manager.py` 完成搜索→下载→刮削→入库全流程。

### 命令行直接运行 / Via Command Line

```bash
# 基本用法 - 按歌名搜索
python3 scripts/music-manager.py "七月上"

# 指定歌手（提高匹配准确率）
python3 scripts/music-manager.py "晴天" "周杰伦"

# 指定音源和音质
python3 scripts/music-manager.py "童话" "光良" --source netease --quality 999

# 使用 MP3 音质（320kbps）
python3 scripts/music-manager.py "左手指月" "萨顶顶" --quality 320

# 使用 Bash 脚本
bash scripts/music-gd.sh "七月上"
bash scripts/music-gd.sh "晴天" "周杰伦"
bash scripts/music-gd.sh "童话" "光良" netease
```

### 环境变量覆盖 / Environment Variables

```bash
export NAS_HOST="user@nas.example.com"
export NAS_PASS="your_password"
export MEDIA_PATH="/music/library"
export QUALITY=320  # 临时使用 MP3
```

## 工作流程 / Workflow

```
1. 用户请求 → "我想听 XXX"
   ↓
2. 登录 SolaraPlus → 获取 session cookie
   ↓
3. 搜索歌曲 → SolaraPlus API 多源搜索（netease → kuwo）
   ↓
4. 获取下载链接 → 优先无损 FLAC（quality=999）
   ↓
5. SSH 下载到 NAS → curl 直接下载
   ↓
6. 刮削元数据 → Music Tag Web 容器（封面 + 歌词 + 标签）
   ↓
7. 触发媒体库扫描 → Navidrome 自动同步
   ↓
8. 立即可播放 🎉
```

## 配置示例 / Configuration Example

### config.json

```json
{
  "solara_url": "http://YOUR_NAS_IP:3010",
  "solara_password": "YOUR_SOLARA_PASSWORD",
  "nas_host": "YOUR_USERNAME@YOUR_NAS_IP",
  "nas_pass": "YOUR_NAS_PASSWORD",
  "media_path": "/vol1/1000/docker/daoliyu/media",
  "mtw_url": "http://YOUR_NAS_IP:8010",
  "mtw_user": "admin",
  "mtw_pass": "YOUR_MTW_PASSWORD",
  "prefer_hires": true,
  "sources": ["netease", "kuwo"],
  "default_quality": 999
}
```

## 故障排除 / Troubleshooting

### 常见问题 / Common Issues

**Q: 搜索不到歌曲 / Song not found**
1. 检查 SolaraPlus 服务：`curl -I http://YOUR_NAS_IP:3010`
2. 尝试切换音源：`--source kuwo`（周杰伦版权多在酷我）
3. 检查歌曲名拼写是否正确

**Q: 登录失败 / Login failed**
1. 检查 SolaraPlus 密码是否正确
2. 检查 NAS 网络连接
3. 重启 SolaraPlus 容器

**Q: 下载失败 / Download failed**
1. 检查 SSH 连接：`sshpass -p '密码' ssh 用户名@主机 'echo ok'`
2. 检查 NAS 存储空间
3. 检查下载目录权限

**Q: 刮削失败 / Scraping failed**
1. 检查 Music Tag Web 容器运行状态：`docker ps | grep music-tag-web`
2. 即使刮削失败，文件也已下载，可以手动补刮削

### 调试模式 / Debug Mode

```bash
# 启用详细输出
export DEBUG=1
python3 scripts/music-manager.py "测试歌曲"

# 检查容器状态
ssh $NAS_HOST "docker ps | grep music-tag-web"
ssh $NAS_HOST "docker logs music-tag-web --tail 20"
```

## 实战经验 / Practical Tips

### 音源选择策略 / Source Selection

- **周杰伦/索尼版权歌曲**：优先 `kuwo`，netease 经常无版权或只有翻唱
- **其他流行歌曲**：优先 `netease`，FLAC 资源更丰富
- **如果 netease 返回翻唱版**：立即换 `kuwo`

### 刮削必须在扫描之前 / Scraping Before Scanning

完整流程：下载 → **刮削 (Music Tag Web)** → 扫描 (Navidrome)
如果先扫描再刮削，Navidrome 不会自动更新元数据。

## 已知限制 / Known Limitations

1. **歌词获取**：依赖酷我音乐，部分歌曲可能失败
2. **音质依赖**：无损音质需要音源有版权
3. **SolaraPlus 依赖**：需要 NAS 上运行 SolaraPlus 服务

## 更新日志 / Changelog

### v3.0.0 (2026-04-17)
- ✅ 完整发布版本，中英双语文档
- ✅ 新增一键安装脚本 (install.sh)
- ✅ 完善系统要求和容器说明
- ✅ 优化配置清单和获取方式说明
- ✅ 修复刮削逻辑（music-tag-web 容器内执行）

### v2.2.0 (2026-04-12)
- ✅ 简化歌词处理：仅使用 Music Tag Web 刮削内嵌歌词
- ✅ 移除单独 .lrc 歌词文件生成功能

### v2.1.0 (2026-04-12)
- ✅ 切换至 SolaraPlus-ForNas API
- ✅ 支持网易云、酷我双音源
- ✅ 支持 FLAC 无损下载

## 许可证 / License

MIT License

---

**维护者 / Maintainer**: CliangL
**适用平台 / Platforms**: OpenClaw, Hermes, NAS (飞牛/群晖等), Linux, macOS
