# 跨平台环境细则：搭建 / PATH / 编码 / 排障

本文件是 `lushibo-sysenv` 的命令参考。

## 1. Windows 初始化命令

```powershell
# 系统信息
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsArchitecture
[System.Environment]::OSVersion.Version

# 开发者模式与长路径
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /v AllowDevelopmentWithoutDevLicense
reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f

# 包管理器
winget --version
winget install --id Microsoft.PowerShell -e
winget install --id Git.Git -e
winget install --id BurntSushi.ripgrep.MSVC -e

# 用户级 PATH（读原始值，避免变量展开）
[Environment]::GetEnvironmentVariable('Path', 'User')
```

## 2. Linux / Kali 初始化命令

```bash
# 系统信息
cat /etc/os-release; uname -a; id

# 基础包（Debian 系）
sudo apt update && sudo apt -y upgrade
sudo apt -y install build-essential git curl wget unzip jq ripgrep tmux htop \
  net-tools ca-certificates python3-venv pkg-config

# 时钟与时区
timedatectl set-timezone Asia/Shanghai
timedatectl status

# 监听端口与占用
ss -lntup
```

Kali 注意：不要混用其他发行版源；优先装 kali-linux-headless 再按需加元包；升级前打快照。

## 3. WSL 细则

```bash
# 启用 systemd：写入 /etc/wsl.conf
[boot]
systemd=true
[interop]
appendWindowsPath=false     # 避免 Windows PATH 污染 Linux PATH
```

- 项目放 Linux 侧家目录，跨 /mnt/c 访问 IO 会慢一个数量级。
- 备份：`wsl --export <发行版> backup.tar`；恢复：`wsl --import`。
- 网络：NAT 模式下 WSL 访问宿主用宿主 IP（/etc/resolv.conf 里的 nameserver）；宿主访问 WSL 服务需端口转发或镜像网络模式。

## 4. PATH 治理

**Windows**

| 项 | 要点 |
|---|---|
| 读取 | `[Environment]::GetEnvironmentVariable('Path','User')` 取原始字符串（含 %VAR%） |
| 写入 | `[Environment]::SetEnvironmentVariable('Path', $new, 'User')` |
| 去重 | 按分号拆分 → 去空 → 去重（忽略大小写）→ 保持原有相对顺序 |
| 生效 | 新进程自动继承；当前会话需广播 WM_SETTINGCHANGE 或重开终端 |
| 风险 | 用 Set-ItemProperty 直接写注册表可能破坏 %USERPROFILE% 这类变量展开 |

**Linux**

| 文件 | 何时加载 | 放什么 |
|---|---|---|
| /etc/profile、/etc/profile.d/*.sh | 登录 shell | 系统级 PATH、全局变量 |
| ~/.profile | 登录 shell | 用户级 PATH、环境变量（POSIX 兼容） |
| ~/.bashrc | 交互式非登录 shell | 别名、函数、补全、提示符 |
| ~/.zshrc | zsh 交互式 | 同上 |
| ~/.bash_profile | 登录 bash（若存在会屏蔽 .profile） | 一般只 source ~/.profile |

幂等写法：

```bash
MARK="# >>> lushibo env >>>"
if ! grep -qF "$MARK" ~/.profile 2>/dev/null; then
  {
    echo "$MARK"
    echo 'export PATH="$HOME/.local/bin:$PATH"'
    echo "# <<< lushibo env <<<"
  } >> ~/.profile
fi
```

## 5. 编码与换行检查

```powershell
# 判断是否 UTF-8 BOM
$bytes = [System.IO.File]::ReadAllBytes('script.ps1')
if ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { 'BOM' } else { 'no BOM' }

# 判断是否 CRLF
if ((Get-Content -Raw 'script.ps1') -match "`r`n") { 'CRLF' } else { 'LF' }
```

```bash
# Linux 侧
file script.sh
grep -c $'\r' script.sh      # 0 表示无 CRLF
```

## 6. 排障命令表

| 症状 | 命令 | 判据 |
|---|---|---|
| command not found | `command -v <cmd>` / `Get-Command <cmd>` | 返回路径即已安装 |
| 装了但找不到 | `echo $PATH` / `$env:PATH -split ';'` | 是否含安装目录 |
| 动态库缺失 | `ldd <binary>` | 有 not found 行 |
| 端口占用 | `ss -lntp` / `netstat -ano \| findstr :PORT` | 找到 PID |
| DNS 异常 | `dig +short <域名>`、`nslookup` | 返回预期 IP |
| 代理是否生效 | `curl -v <url>` 看是否走代理 | 连接目标为代理地址 |
| 权限被拒 | `ls -l`、`getfacl`、`getenforce` | 模式/ACL/SELinux |
| 磁盘满 | `df -h`、`du -sh *` | 使用率 >90% |
| 时间偏差 | `timedatectl` / `w32tm /query /status` | 偏差 <1 秒 |
| 乱码 | `locale`、终端编码设置 | 均为 UTF-8 |

## 7. 跨平台等价写法

| 任务 | PowerShell | POSIX shell |
|---|---|---|
| 脚本目录 | `Split-Path -Parent $MyInvocation.MyCommand.Path` | `cd "$(dirname "$0")" && pwd` |
| 判断命令 | `if (Get-Command x -EA SilentlyContinue) {}` | `if command -v x >/dev/null; then :; fi` |
| 失败即退出 | `$ErrorActionPreference='Stop'` + `exit 1` | `set -euo pipefail` |
| 读环境变量 | `$env:NAME` | `${NAME:-default}` |
| 创建目录 | `New-Item -ItemType Directory -Force` | `mkdir -p` |
| 下载 | `Invoke-WebRequest -Uri $u -OutFile $f` | `curl -fsSL -o "$f" "$u"` |
| 校验和 | `Get-FileHash -Algorithm SHA256` | `sha256sum` |
| 解压 | `Expand-Archive` / `tar -xzf` | `unzip` / `tar -xzf` |
| 查找文件 | `Get-ChildItem -Recurse -Filter *.py` | `find . -name '*.py'` |
| 文本替换 | `(Get-Content f) -replace 'a','b' \| Set-Content f` | `sed -i 's/a/b/g' f` |

## 8. 基线快照

| 环境 | 快照方式 | 时机 |
|---|---|---|
| 虚拟机 | 平台快照 | 装完系统、装完基础工具链、做实验前 |
| WSL | `wsl --export` 导出 tar | 环境配好后、大版本升级前 |
| 物理机 | 系统还原点 / 镜像备份 | 大改动前 |
| 容器 | 镜像 tag + 提交 | 每次成功构建后 |

恢复演练：至少演练一次恢复流程，确认能在 15 分钟内回到基线。

## 9. 使用边界

系统级改动（内核参数、安全策略、注册表）在生产环境执行前需评估影响并保留回滚手段。
