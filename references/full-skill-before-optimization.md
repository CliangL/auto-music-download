# auto-music-download - 多源无损音乐下载
Multi-Source Lossless Music Downloader for OpenClaw

🎵 自动从 6+ 音源搜索下载 FLAC 无损音乐，支持自动刮削入库到媒体服务器。
Auto-download FLAC lossless music from 6+ sources, with auto-tagging and media server integration.

## ⚠️ 执行铁律 (强制)

**每次执行此 Skill 时，必须先输出以下主要步骤清单，然后严格按顺序执行：**

1. **登录 SolaraPlus**：获取 session cookie
2. **搜索歌曲**：多源搜索（netease → kuwo），验证结果匹配
3. **获取下载链接**：优先无损 FLAC（quality=999）
4. **下载到 NAS**：SSH 执行 curl 下载
5. **刮削元数据**：调用 Music Tag Web 容器引擎
6. **触发扫描**：重启 Daoliyu/Navidrome 容器

**禁止跳步、禁止简化、禁止自创流程。输出清单后再继续读下方详细步骤。**

## 使用场景 / Use Cases

- 想听某首歌，自动搜索下载无损版本
- 批量下载歌曲到 NAS 媒体库
- 自动选择最佳音源和格式
- 自动刮削元数据（封面、歌词、艺术家信息）

## 系统要求 / Requirements

- **Python 3.8+**（推荐 3.10+）
- **curl**
- **sshpass**（用于 NAS SSH 连接）
- **OpenClaw** 运行环境
- **NAS 或本地存储**（用于存放音乐文件）
- **Music Tag Web**（可选，用于自动刮削元数据）
- **Daoliyu / Navidrome**（可选，音乐播放服务器）

### 依赖说明

本技能基于 **GD 音乐台 API**，无需安装额外的 Python 包（如 musicdl）。

**必需工具**：
- `sshpass` - 用于 NAS SSH 连接
- `curl` - 用于 API 调用和文件下载
- `python3` - 用于脚本执行
- `docker` - 用于调用 Music Tag Web 容器（刮削用）

## 配置清单 / Configuration

| 配置项 | 说明 | 获取方式 | 是否必填 |
|--------|------|----------|----------|
| `solara_url` | SolaraPlus-ForNas 地址 | NAS 上的服务地址 | ✅ 必填 |
| `solara_password` | SolaraPlus 访问密码 | 默认 `YOUR_PASSWORD` | ✅ 必填 |
| `nas_host` | NAS SSH 地址 | `用户名@IP 或域名` | ✅ 必填 |
| `nas_pass` | NAS SSH 密码 | 你的 NAS 密码 | ✅ 必填 |
| `media_path` | 音乐存放路径 | NAS 上的目录路径 | ✅ 必填 |
| `prefer_hires` | 优先无损音质 | `true`/`false` | ❌ 可选 |
| `sources` | 音源优先级列表 | JSON 数组 | ❌ 可选 |
| `default_quality` | 默认音质 | `999`=FLAC, `320`=MP3 | ❌ 可选 |

### 音源列表

| 音源 | 代码 | 说明 |
|------|------|------|
| 网易云音乐 | `netease` | 推荐，无损资源丰富 |
| 酷我音乐 | `kuwo` | 备选，音质较好 |

> 💡 **注意**：QQ 音乐、酷我音乐、JOOX 因版权要求已下架，目前仅支持网易云和酷我。

## 用户自定义信息 / User Customization

安装时 OpenClaw 会询问以下信息：

1. **NAS SSH 地址** — 例如 `YOUR_USERNAME@YOUR_NAS_IP`
2. **NAS SSH 密码** — 你的 NAS 密码
3. **音乐存放路径** — 例如 `/vol1/xxx/docker/daoliyu/media`

其他配置会自动使用默认值。

## 一键安装 / Installation

### 通过 OpenClaw 安装（推荐）

在 OpenClaw 对话中发送：

```
安装 skill: https://github.com/CliangL/auto-music-download
```

OpenClaw 会自动：

1. 克隆仓库到 `skills/` 目录
2. 检测环境依赖（sshpass, curl, python3）
3. 提示你填写 NAS 地址、密码、路径
4. 自动替换配置文件中的设置

### 手动安装

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/CliangL/auto-music-download.git auto-music-download
cd auto-music-download

# 编辑配置文件
nano config.json

# 测试运行
python3 scripts/music-manager.py "测试歌曲"
```

## 使用方法 / Usage

### 通过 OpenClaw

告诉 OpenClaw：

```
我想听周杰伦的晴天
```

OpenClaw 会自动调用 `music-manager.py` 脚本。

### 直接运行脚本

```bash
# 基本用法
python3 scripts/music-manager.py "七月上"

# 指定歌手
python3 scripts/music-manager.py "晴天" "周杰伦"

# 指定音源和音质
python3 scripts/music-manager.py "童话" "光良" --source netease --quality 999

# 使用 MP3 品质
python3 scripts/music-manager.py "左手指月" "萨顶顶" --quality 320
```

### 使用 Bash 脚本

```bash
# 基本用法
bash scripts/music-gd.sh "七月上"

# 指定歌手
bash scripts/music-gd.sh "晴天" "周杰伦"

# 指定音源
bash scripts/music-gd.sh "童话" "光良" netease

# 使用 MP3 品质
QUALITY=320 bash scripts/music-gd.sh "左手指月" "萨顶顶"
```

## 配置示例 / Configuration Example

### config.json

```json
{
  "solara_url": "http://YOUR_NAS_IP:3010",
  "solara_password": "YOUR_PASSWORD",
  "nas_host": "YOUR_USERNAME@YOUR_NAS_IP",
  "nas_pass": "YOUR_NAS_PASSWORD",
  "media_path": "/vol1/xxx/docker/daoliyu/media",
  "prefer_hires": true,
  "sources": ["netease", "kuwo"],
  "default_quality": 999
}
```

### 环境变量覆盖

支持通过环境变量覆盖配置：

```bash
export NAS_HOST="user@nas.example.com"
export NAS_PASS="your_password"
export MEDIA_PATH="/music/library"
export QUALITY=320  # 临时使用 MP3 品质
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
5. 下载到 NAS → SSH 执行 curl 下载
   ↓
6. 刮削元数据 → 调用 Music Tag Web 容器引擎
   ↓
7. 触发扫描 → 重启 Daoliyu/Navidrome 容器
   ↓
8. 立即可播放 → 媒体库已更新
```

## 刮削机制 / Scraping Mechanism

**直接调用容器内引擎，绕过 Web API**

```python
# 在 NAS 上执行
docker exec music-tag-web python -c """
# 使用容器内的 KuwoClient
# 搜索元数据、获取歌词、下载封面
# 写入完整 ID3 标签
"""
```

**优势**：
- ✅ 绕过有问题的 Web API
- ✅ 直接访问功能引擎
- ✅ 避免网络延迟和序列化
- ✅ 更高的成功率

**刮削内容**：
- 标题（title）
- 艺术家（artist）
- 专辑（album）
- 歌词（lyrics）
- 封面（artwork）

## 故障排除 / Troubleshooting

### 常见问题

**Q: 搜索不到歌曲**

A: 
1. 检查 SolaraPlus 服务：`curl -I http://YOUR_NAS_IP:3010`
2. 尝试不同音源：`--source kuwo`
3. 检查歌曲名是否正确（支持中文）

**Q: 登录失败**

A:
1. 检查 SolaraPlus 密码是否正确
2. 检查 NAS 网络连接
3. 重启 SolaraPlus 容器

**Q: 下载失败**

A:
1. 检查 SSH 连接：`sshpass -p '密码' ssh 用户名@主机 'echo 测试'`
2. 检查 NAS 存储空间
3. 检查文件权限

**Q: 刮削失败**

A:
1. 检查 Music Tag Web 容器：`docker ps | grep music-tag-web`
2. 检查容器内 Python 环境
3. 即使刮削失败，文件也已下载，可以手动刮削

**Q: 文件无法播放**

A:
1. 检查实际文件格式：`file 歌曲.flac`
2. 从网易云音乐重新下载：`--source netease`
3. 检查媒体服务器状态

### 调试模式

```bash
# 启用详细输出
export DEBUG=1
python3 scripts/music-manager.py "测试歌曲"

# 检查容器状态
ssh $NAS_HOST "docker ps | grep music-tag-web"
ssh $NAS_HOST "docker logs music-tag-web --tail 20"
```

## 性能指标 / Performance

| 操作 | 平均耗时 | 成功率 |
|------|----------|--------|
| 搜索歌曲 | 2-5 秒 | 95% |
| 获取下载链接 | 1-3 秒 | 90% |
| 下载文件 | 10-30 秒 | 90% |
| 刮削元数据 | 3-10 秒 | 85% |
| 完整流程 | 15-45 秒 | 80% |

## 实战经验 / Practical Tips

### ⚠️ 常见陷阱

**1. 脚本位置**
脚本在 `scripts/` 子目录，不是 skill 根目录：
```bash
bash scripts/music-gd.sh "歌曲名"
# 不是 bash music-gd.sh
```

**2. 搜索结果验证**
GD API 搜索可能返回错误匹配。例如搜索 `"双节棍 周杰伦"` 可能返回 `"花海 - 周杰伦"`。
**必须验证搜索结果**，不匹配时换音源：
```bash
# 换酷我源（周杰伦版权多在酷我）
bash scripts/music-gd.sh "双截棍" "周杰伦" kuwo
```

**3. 音源选择策略**
- **周杰伦/索尼版权歌曲**：优先 `kuwo`，netease 经常无版权或只有翻唱
- **其他流行歌曲**：优先 `netease`，FLAC 资源更丰富
- **如果 netease 返回翻唱版**：立即换 `kuwo`

**4. 刮削必须在扫描之前**
完整流程：下载 → **刮削(Music Tag Web)** → 扫描(Navidrome)
如果先扫描再刮削，Navidrome 不会自动更新元数据。

**5. 路径映射**
Music Tag Web 容器内路径：`/vol1/xxx/docker/daoliyu/media` → `/app/media`
刮削时要用容器内路径。

### ⚠️ 脚本已知问题 (music-gd.sh v2.3)

**问题 1: NAS 本机无 music_tag 模块**
脚本刮削函数直接在 NAS 调用 `python3 music_tag`，但 NAS 没有此模块。
**解决**: 必须在 `music-tag-web` Docker 容器内执行刮削。

**问题 2: 文件路径多了艺术家子目录**
下载路径为 `${MEDIA_PATH}/${artist}/${artist} - ${song}.flac`，刮削时路径不匹配。
**解决**: 刮削路径应为 `/app/media/${artist}/${artist} - ${song}.flac`。

**问题 3: 容器名错误**
脚本写 `docker exec daoliyu` 但实际容器名是 `daoliyu-backend`，且不支持 CLI 扫描。
**解决**: 扫描应触发 `navidrome`，Daoliyu 会自动同步。

### 手动补刮削（下载后漏了刮削）

**推荐方法：在 music-tag-web 容器内执行，路径要包含艺术家子目录**

```bash
sshpass -p '密码' ssh 用户@NAS "docker exec music-tag-web python3 -c \"
import music_tag
filepath = '/app/media/艺术家/艺术家 - 歌曲名.flac'  # 注意子目录！
f = music_tag.load_file(filepath)
f['title'] = '歌曲名'
f['artist'] = '艺术家'
f['album'] = '歌曲名'
f.save()
print('✅ 标签写入完成')
\""
```

**触发媒体库扫描**

```bash
# Navidrome 扫描（主要）
sshpass -p '密码' ssh 用户@NAS "docker exec navidrome /app/navidrome scan -f"

# Daoliyu 后端重启（可选）
sshpass -p '密码' ssh 用户@NAS "docker restart daoliyu-backend"
```

---

## 已知限制 / Known Limitations

1. **歌词获取**：依赖酷我音乐的 musicrid，部分歌曲可能失败
2. **音质依赖**：无损音质需要 netease 源有版权
3. **文件格式**：实际文件格式可能不是 FLAC（由音源决定）
4. **SolaraPlus 依赖**：需要 NAS 上运行 SolaraPlus-ForNas 服务

## 更新日志 / Changelog

### v2.3.0 (2026-04-19)
- ✅ **刮削容错优化**：忽略 `UserWarning`，改用文件大小校验替代退出码，避免误报失败。
- ✅ **歌手匹配优化**：当音源返回的歌手不匹配时，打印明确警告而非静默选取。
- ✅ **音源策略调整**：华语流行优先推荐 `kuwo`，网易云作为备选。

### v2.2.0 (2026-04-12)
- ✅ 简化歌词处理：仅使用 Music Tag Web 刮削内嵌歌词
- ✅ 移除单独 .lrc 歌词文件生成功能
- ✅ 优化工作流程：下载 → 刮削（含歌词）→ 入库

### v2.1.0 (2026-04-12)
- ✅ 切换至 SolaraPlus-ForNas API
- ✅ 支持网易云、酷我双音源
- ✅ 优化中文搜索（URL 编码）
- ✅ 简化配置（移除 GD API 依赖）
- ✅ 支持 FLAC 无损下载

### v2.0.0 (2026-04-12)
- ✅ 适配飞牛 NAS 环境
- ✅ 修复 GD API 访问问题
- ✅ 整合 Music Tag Web 刮削功能
- ✅ 创建 Python 和 Bash 双版本脚本
- ✅ 添加配置文件管理
- ✅ 支持代理配置

### v1.0.0 (原始版本)
- 基于 musicdl 多源下载
- 支持 10+ 音源
- 自动安装依赖

## 贡献 / Contributing

欢迎提交 Issue 和 Pull Request！

GitHub: https://github.com/CliangL/auto-music-download

## 许可证 / License

MIT License

---

**最后更新**: 2026-04-12 (v2.2.0)  
**维护者**: CliangL  
**适用平台**: OpenClaw, NAS (飞牛/群晖等), Linux, macOS