# auto-music-download

Hermes/OpenClaw 多源音乐自动下载 skill。它通过 SolaraPlus 搜索和下载音乐，写入 NAS 媒体目录，可调用 Music Tag Web 刮削元数据，并尽量减少重复 SSH 操作来提升速度。

auto-music-download is a Hermes/OpenClaw skill for searching, downloading, organizing, and tagging music through SolaraPlus and optional Music Tag Web.

## 给 AI 的一键安装指令

把这段发给 Hermes、OpenClaw 或其他能操作终端的 AI：

```text
请安装或更新这个 Hermes/OpenClaw skill：
https://github.com/CliangL/auto-music-download

如果本机或 NAS 缺少依赖/容器，请先检测环境，把缺失项列出来并请求我授权安装。
安装过程中只向我询问必须由我提供的信息：NAS SSH 密码、SolaraPlus 密码、音乐保存目录、可选 Music Tag Web 密码。
其他事情请自动完成：判断新装还是更新、保留旧配置、检测 Docker 容器、识别端口、写入配置、运行语法检查。
```

English handoff:

```text
Install or update this Hermes/OpenClaw skill:
https://github.com/CliangL/auto-music-download

Detect the local/NAS environment first. Ask for authorization before installing missing dependencies or containers.
Only ask me for required secrets and paths: NAS SSH password, SolaraPlus password, music save directory, optional Music Tag Web password.
Automatically decide install vs update, preserve existing config, detect Docker services and ports, write config, and run checks.
```

## 它怎么工作

1. Hermes 读取 `SKILL.md`，把用户的自然语言下载请求交给音乐管理脚本。
2. `scripts/music-manager.py` 调用 SolaraPlus 搜索并选择音源。
3. 脚本把下载、目录创建、文件校验等 NAS 操作合并，减少 SSH 往返。
4. 可选调用 Music Tag Web 补刮元数据；刮削失败不会阻塞已下载文件。
5. 下载后文件保存在用户配置的 NAS 音乐目录，供 Navidrome、Jellyfin、Emby 等媒体库扫描。

The workflow is: parse request -> search SolaraPlus -> download to NAS -> verify file -> optionally tag -> refresh or prepare for media library scan.

## 环境要求

本机或 AI 执行环境：

- `bash`
- `python3`
- `jq`
- `curl`
- `ssh`
- `sshpass`，如果没有 SSH key 则需要
- `git`

NAS/服务器：

- 可 SSH 登录
- Docker，推荐用于运行 SolaraPlus、Music Tag Web 和媒体库
- SolaraPlus：必需，用于音乐搜索和下载，常见端口 `3010`
- Music Tag Web：可选，用于元数据刮削，常见端口 `8010`
- Navidrome/Jellyfin/Emby：可选，用于媒体库播放和扫描

## 新安装

```bash
git clone https://github.com/CliangL/auto-music-download.git ~/.hermes/skills/media/auto-music-download
cd ~/.hermes/skills/media/auto-music-download
bash install.sh
```

安装脚本会：

- 检测本机依赖，缺失时可用 `bash install.sh --install-deps` 在用户授权后安装。
- 通过 NAS SSH 检测 Docker 和正在运行的容器。
- 根据容器名、镜像名和端口推断 SolaraPlus、Music Tag Web、Navidrome 地址。
- 生成 `config.json`。
- 生成 `install-plan.md`，给 AI 后续部署缺失容器或复核环境用。
- 运行 Python 和 Shell 语法检查。

## 更新已安装版本

```bash
cd ~/.hermes/skills/media/auto-music-download
git pull
bash install.sh
```

更新模式会保留：

- `config.json` 里的接口、密码、目录
- 用户自行补充的未知配置字段
- 现有 SolaraPlus/NAS/Music Tag Web 配置

如果要重新识别端口或重新填写配置：

```bash
bash install.sh --reconfigure
```

## AI 自动部署缺失环境

本仓库不在脚本里硬编码第三方容器镜像，避免不同 NAS 平台拉错镜像。AI 应按 `install-plan.md` 执行：

1. 检测系统、Docker、端口占用和已有容器。
2. 缺少 SolaraPlus、Music Tag Web 或媒体库容器时，向用户请求授权安装。
3. 根据当前平台选择官方或用户指定镜像。
4. 自动记录实际端口。
5. 重新运行 `bash install.sh --reconfigure`，把端口写回 skill 配置。

用户只需要提供授权、容器密码和音乐保存目录。

## 使用示例

在 Hermes/OpenClaw 中可以直接说：

```text
下载周杰伦 七里香 无损
下载邓紫棋 光年之外
下载这个歌手的专辑并优先无损
```

也可以手动运行：

```bash
python3 scripts/music-manager.py "七里香" "周杰伦" --quality 999
python3 scripts/music-manager.py "光年之外" "邓紫棋" --source kuwo --quality 320
```

## 关键配置

配置文件：`config.json`

- `solara_url`：SolaraPlus 地址
- `solara_password`：SolaraPlus 密码
- `nas_host`：NAS SSH 地址，格式 `user@IP`
- `nas_pass`：NAS SSH 密码
- `ssh_port`：NAS SSH 端口
- `media_path`：音乐保存目录
- `mtw_url/mtw_user/mtw_pass`：Music Tag Web 可选配置
- `sources`：默认音源顺序
- `default_quality`：默认音质，`999` 表示优先无损

## 重要规则

- 主入口是 `scripts/music-manager.py`。
- 默认音源顺序是 `netease -> kuwo`。
- 默认优先无损，找不到时可按脚本策略降级。
- 更新 skill 不会删除用户配置、密码、接口和媒体目录。
- Music Tag Web 失败只提示补刮，不阻塞已下载音乐。

## Troubleshooting

- 下载慢：确认 NAS SSH 能复用连接，SolaraPlus 容器响应正常。
- 搜不到歌：尝试换音源或降低音质要求。
- 写入失败：检查 `media_path` 是否存在，NAS 用户是否有写权限。
- Music Tag Web 不工作：检查 `mtw_url`、账号密码和容器端口。
- 端口变了：运行 `bash install.sh --reconfigure` 重新检测。
