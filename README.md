# auto-music-download

Hermes/OpenClaw 多源无损音乐下载 skill：通过 SolaraPlus 搜索下载音乐，写入 NAS 媒体目录，调用 Music Tag Web 刮削元数据，并触发媒体库扫描。

## 安装

把仓库复制或克隆到 Hermes skill 目录后运行：

```bash
git clone https://github.com/CliangL/auto-music-download.git ~/.hermes/skills/media/auto-music-download
cd ~/.hermes/skills/media/auto-music-download
bash install.sh
```

新安装只需要提供关键地址和密码：SolaraPlus 地址/密码、NAS SSH、音乐目录、可选 Music Tag Web 地址/密码。安装脚本会生成 `config.json`。

## 更新

已安装用户更新时不要重新安装，也不要删除配置：

```bash
cd ~/.hermes/skills/media/auto-music-download
git pull
bash install.sh
```

`install.sh` 会保留已有 `config.json` 中的接口、API、密码和目录配置，只补齐缺失字段并做语法检查。

## 当前规则

- 使用 `scripts/music-manager.py` 作为主入口。
- SSH 使用 ControlMaster 复用连接，减少多步骤下载流程耗时。
- 下载、目录创建、文件大小校验合并在一次 SSH 中完成。
- Music Tag Web 刮削失败不阻塞已下载文件，但会提示后续补刮。
- 默认音源顺序为 `netease -> kuwo`，默认优先无损 `quality=999`。

## 主要入口

```bash
python3 scripts/music-manager.py "歌曲名" "歌手" --quality 999
python3 scripts/music-manager.py "歌曲名" --source kuwo --quality 320
```

Hermes 会读取 `SKILL.md` 中的执行铁律。完整历史说明见 `references/full-skill-before-optimization.md`。
