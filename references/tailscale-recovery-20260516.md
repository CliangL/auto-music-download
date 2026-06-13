# NAS Tailscale 恢复排障记录

**日期**：2026-05-16
**问题**：NAS Tailscale IP `100.114.78.28` 无法访问

## 排障步骤

### 1. 确认状态
```bash
ssh oect "tailscale status | grep fn-nas"
# 结果：100.127.139.8 fn-nas false（离线）
```

### 2. 检查 NAS tailscaled
```bash
ssh oect "ssh YOUR_USERNAME@YOUR_NAS_LAN_IP 'systemctl status tailscaled'"
# 发现：tailscaled 不存在，软件被卸载或丢失
```

### 3. 修复 DNS
NAS `/etc/resolv.conf` 被 Tailscale 退出时损坏，无法解析外网：
```bash
ssh oect "ssh YOUR_USERNAME@YOUR_NAS_LAN_IP 'sudo cp /etc/resolv.pre-tailscale-backup.conf /etc/resolv.conf'"
```

### 4. 重装 Tailscale
```bash
ssh oect "ssh YOUR_USERNAME@YOUR_NAS_LAN_IP 'curl -fsSL https://tailscale.com/install.sh | sudo sh'"
# 安装 v1.96.4
```

### 5. 认证
`tailscale up` 需浏览器登录，SSH 无交互终端：
```bash
ssh oect "ssh YOUR_USERNAME@YOUR_NAS_LAN_IP 'sudo tailscale up'"
# 输出登录 URL：https://login.tailscale.com/a/19353e70012399
```

用户在浏览器完成登录后，NAS 获得新 IP。

### 6. 新 IP
```
旧 IP：100.114.78.28（已失效）
新 IP：YOUR_NAS_IP（hostname: cliang-nas）
```

## 配置更新清单

需更新的文件：
- `~/.ssh/config`：`HostName 100.114.78.28` → `HostName YOUR_NAS_IP`
- `~/.hermes/scripts/check_home_status.py`
- `~/.hermes/scripts/backup*.sh` / `backup*.py`
- `~/.hermes/skills/media/auto-music-download/scripts/music-fast-download.py`
- `~/.hermes/skills/media/auto-media-download/scripts/*.py`
- `~/.hermes/memories/MEMORY.md`
- `~/.hermes/wiki/entities/FN-NAS.md`

批量替换：
```bash
sed -i '' 's/100.114.78.28/YOUR_NAS_IP/g' ~/.ssh/config
# 其他文件用 patch 或 sed
```

## 经验教训

1. **Tailscale 状态文件丢失**：`/var/lib/tailscale/tailscaled.state` 只剩 machinekey，无认证信息
2. **DNS 被 Tailscale 覆盖**：退出后 resolv.conf 未恢复，导致无法访问外网
3. **认证需浏览器**：SSH 无法完成 OAuth 登录，必须提供登录 URL 给用户
4. **Auth Key 更方便**：可在 Tailscale 控制台生成 `--authkey` 免交互登录