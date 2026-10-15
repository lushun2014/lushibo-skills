---
name: lushibo-sysenv
description: "跨平台环境工程（Windows / Linux / Kali 环境搭建与运维）。能力：从裸机到可用工作环境的搭建流程、工具链自举（包管理器与离线安装、版本锁定、镜像源）、持久化配置（环境变量、shell/PSProfile、PATH 治理、别名与函数、服务自启）、环境排障（PATH 冲突、编码与换行、权限、代理、动态库、端口占用）、跨平台脚本（同一任务在 PowerShell 与 POSIX shell 下的等价实现）。Use when 用户提到 Windows环境、Linux环境、kali环境、环境搭建、工具链自举、持久化配置、环境变量、排障、跨平台脚本、依赖安装、shell配置、WSL环境、虚拟机环境，或给出报错、PATH 异常、命令找不到、编码乱码要求诊断与修复。交付物：环境审计报告（Markdown + JSON）、搭建脚本（Python/PowerShell）、持久化配置清单、排障决策树、跨平台等价命令对照表。"
triggers:
  - Windows环境
  - Linux环境
  - kali环境
  - 环境搭建
  - 工具链自举
  - 持久化配置
  - 环境变量
  - 排障
  - 跨平台脚本
  - 依赖安装
  - shell配置
  - WSL环境
  - 虚拟机环境
---

# Lushibo Sysenv · 跨平台环境工程

环境问题的 80% 来自四处：**PATH 顺序、编码与换行、权限与所有权、代理与镜像源**。按这个顺序查，不要重启。

## 触发条件

- **加载时机**：用户要搭环境、装工具链、配持久化、修命令找不到/乱码/权限/网络问题，或要一份跨平台脚本。
- **中文关键词**：Windows 环境、Linux 环境、Kali、环境搭建、工具链、自举、持久化、环境变量、PATH、别名、排障、报错、乱码、权限、依赖安装、shell 配置、WSL、虚拟机、镜像源、代理。
- **英文关键词**：environment setup、bootstrap、PATH、profile、rc file、venv、nvm、pyenv、winget、choco、scoop、apt、dnf、pacman、WSL、CRLF、BOM、encoding、permission denied、command not found。
- **不加载的情况**：只问"CI 流水线怎么写"走 `$lushibo-github`；只问"代码结构/重构/测试"走 `$lushibo-code`。
- **边界**：本 skill 管**机器与工具链**，仓库与流水线归 github。

## 执行步骤

### 第 1 步：环境审计（先测量，再动手）

```bash
D:\Python\python.exe scripts\env_audit.py --check-persist --out env-report.md
```

审计产出四块：系统与身份（OS/版本/架构/是否管理员/WSL/容器）、工具链清单（是否存在、版本、路径）、持久化配置（rc 文件、PATH 来源、代理变量）、期望清单比对（缺什么、按平台给安装命令）。

判断标准：先确认"缺什么"，再确认"为什么缺"（没装 vs 装了但不在 PATH）。两者修法完全不同。

### 第 2 步：平台初始化

**Windows**

1. 包管理器优先级：winget（系统自带）→ scoop（用户级，免管理员）→ choco（需管理员）。
2. 开发者模式打开（支持符号链接）；长路径支持打开（注册表 LongPathsEnabled=1）。
3. 终端：Windows Terminal + PowerShell 7（不要依赖 5.1 跑新语法）。
4. 编码：全局 UTF-8（系统区域设置勾选 Beta UTF-8，或对单个脚本用 BOM 保证 5.1 兼容）。
5. 路径：用户级 PATH 只放用户工具，系统级 PATH 保持干净，避免安装器污染。

**Linux（Debian/Ubuntu 系）**

1. 换镜像源（按区域），`apt update && apt -y upgrade`。
2. 基础包：build-essential、git、curl、wget、unzip、jq、ripgrep、tmux、htop、net-tools、ca-certificates。
3. 时区与时钟同步：`timedatectl set-timezone`、确认 NTP 同步。
4. 用户与权限：日常操作不用 root，sudo 授权按需最小化。

**Kali**

1. `apt update && apt full-upgrade`；不要混用其他发行版的源，会炸依赖。
2. 元包按需装（kali-linux-headless 最小、kali-linux-large 常用），不要装 kali-linux-everything（体积与冲突）。
3. 服务默认关闭，用 systemctl 按需开；无线相关操作注意网卡驱动与监听模式支持。
4. 快照：装完基础环境先打快照，后续实验可回滚。

**WSL**

1. 版本与发行版：WSL2 + 目标发行版；启用 systemd（/etc/wsl.conf 里 systemd=true）。
2. 文件系统：跨系统访问走 /mnt/c 会很慢，项目放在 Linux 侧家目录。
3. 网络：WSL2 NAT 模式下访问宿主服务用宿主 IP；需要被外部访问时配端口转发。
4. 备份：导出 tar 做基线备份（wsl --export）。

### 第 3 步：工具链自举

原则：**版本可锁定、来源可审计、失败可回滚**。

| 工具类型 | 推荐方式 | 理由 |
|---|---|---|
| 语言运行时 | 版本管理器（nvm/pyenv/rustup/go 直接下载） | 多版本共存与切换 |
| CLI 工具 | 包管理器或官方二进制 | 避免编译耗时 |
| Python 库 | 虚拟环境 + 锁定文件 | 隔离依赖 |
| 系统级依赖 | 发行版包管理器 | 库兼容性由发行版保证 |
| 安全工具 | 官方源或容器镜像 | 版本与签名可验证 |

Python 环境规范：

```bash
python -m venv .venv
. .venv/bin/activate        # Linux
.venv\Scripts\Activate.ps1  # Windows PowerShell
python -m pip install -U pip
pip install -r requirements.txt
```

不要在系统 Python 里装项目依赖；不要用 sudo pip install。

### 第 4 步：持久化配置

**PATH 治理**：先查当前 PATH 的每一段来源，再去重与排序。

- Windows：用户级 PATH（注册表 HKCU\Environment）优先于系统级；用脚本读取注册表原始值（不要用会展开变量的方式），改完广播环境变更消息。
- Linux：rc 文件分工——.profile 给登录 shell 用（POSIX 兼容）、.bashrc 给交互式 shell、.zshrc 给 zsh。PATH 追加写 .profile，别名与函数写 .bashrc。

**配置项清单**：PATH 追加、代理变量（http_proxy/https_proxy/no_proxy，含大小写两套）、编辑器、语言运行时的默认版本、常用别名、函数（如 mkcd、gpr）、历史记录与补全、umask。

**幂等要求**：写入前先检查是否已存在，避免重复追加导致 PATH 越来越长。推荐用带标记块的写法：

```
# >>> lushibo env >>>
export PATH="$HOME/.local/bin:$PATH"
# <<< lushibo env <<<
```

**服务自启**：Linux 用 systemd user unit（`systemctl --user enable --now`），Windows 用计划任务或服务；都要写清"如何停用"。

### 第 5 步：编码与换行（跨平台头号坑）

| 场景 | 规则 |
|---|---|
| 含非 ASCII 的 .ps1 | 必须存为 UTF-8 with BOM，否则 Windows PowerShell 5.1 按 ANSI 解码并破坏行结构 |
| 脚本换行 | 统一 LF；在 Windows 上编辑也要确认没被改成 CRLF |
| Python 源文件 | UTF-8 无 BOM；源文件编码声明可省（默认 UTF-8） |
| shell 脚本 | LF + 可执行位；CRLF 会导致 `bad interpreter` |
| 数据文件 | 显式指定编码读写，不要依赖系统默认 |
| 终端显示 | Windows Terminal 设 UTF-8；Linux 确认 locale 为 UTF-8 |

自检命令：PowerShell 读字节看是否以 EF BB BF 开头；`file` 命令看是否含 CRLF。

### 第 6 步：排障决策树

```
命令找不到
├─ which/Get-Command 是否找到？
│  ├─ 找不到 → 是否已安装？
│  │  ├─ 没装 → 装
│  │  └─ 装了 → PATH 是否含其目录？
│  │     ├─ 不含 → 加 PATH（注意持久化 + 新会话生效）
│  │     └─ 含 → 文件名/扩展名/大小写问题
│  └─ 找到 → 是否执行权限？是否 shebang 行尾是 CRLF？是否依赖缺失（ldd）？
网络不通
├─ DNS 解析 → /etc/resolv.conf 或 Windows DNS 设置
├─ 代理变量是否设置且生效 → 是否区分大小写变量名
├─ 端口是否被占用 → ss -lntp / netstat -ano
└─ 防火墙与安全组
乱码
├─ 文件编码与终端编码是否一致
├─ 是否 BOM 问题（PS 5.1）
└─ 数据库/终端字符集
权限
├─ 文件所有权与模式（chmod/chown）
├─ 是否被 ACL 或 SELinux/AppArmor 拦
└─ 是否需要 sudo 而非 root 登录
```

每条分支都给出验证命令与预期输出，不要写"尝试重启"。

### 第 7 步：跨平台脚本

同一件事写两份等价实现，避免用一层抽象硬套：

| 任务 | PowerShell | POSIX shell |
|---|---|---|
| 判断命令存在 | Get-Command name | command -v name |
| 取脚本目录 | Split-Path -Parent $MyInvocation.MyCommand.Path | dirname "$0" |
| 环境变量 | $env:NAME | $NAME |
| 下载 | Invoke-WebRequest | curl -fsSL |
| 解压 zip | Expand-Archive | unzip |
| 权限位 | 不适用 | chmod +x |
| 文本替换 | (Get-Content) -replace | sed -i |
| 进程查询 | Get-Process | ps aux |

脚本规范：带 --help/参数校验、幂等（重复执行结果一致）、失败即退出并给出原因、所有破坏性操作前打印将要做什么。

### 第 8 步：固化与文档

把环境固化成三件产物：审计报告（现状）、搭建脚本（可重放）、配置清单（人工步骤与理由）。换机器时按脚本 + 清单重建，不靠记忆。

## 交付物

| 文件名 | 格式 | 内容要求 |
|---|---|---|
| 环境审计报告.md / .json | Markdown + JSON | 系统信息、工具链表、持久化检查、缺失项（由审计脚本产出） |
| 搭建脚本 | Python / PowerShell | 幂等、带参数校验、失败可回滚 |
| 持久化配置清单.md | Markdown | 配置项/写哪个文件/幂等写法/生效方式/如何撤销 |
| 排障决策树.md | Markdown | 四类问题（PATH/网络/编码/权限）的判定命令与预期输出 |
| 跨平台对照表.md | Markdown | 任务/PS 实现/POSIX 实现/差异说明 |
| 基线快照说明.md | Markdown | 快照方式（WSL export / 虚拟机快照）、恢复步骤、快照时机 |

文件默认落在工作目录的 `sysenv-<目标环境>/` 下。

## 验证方式

1. **审计可复现**：重跑 `scripts/env_audit.py` 输出与报告一致（同一台机器、同一时间窗内）。
2. **搭建可重放**：在干净环境（新容器/新虚拟机/新 WSL 发行版）按脚本执行，无需人工补命令即可得到审计报告中"全部存在"的工具链。
3. **幂等**：连续执行搭建脚本 2 次，第二次不产生重复的 PATH 条目、不重复追加 rc 配置（对比 rc 文件 diff 为空）。
4. **持久化生效**：新开一个会话（新终端/重新登录）后，命令可直接调用、环境变量可读取，无需手动 source。
5. **编码正确**：所有含非 ASCII 的 .ps1 有 UTF-8 BOM；所有脚本为 LF；用工具验证而非目测。
6. **排障可判定**：决策树每个分支都有命令与预期输出；随机抽 3 条实测，结论与文档一致。
7. **跨平台等价**：对照表里每行任务在两平台各跑一次，输出语义一致（允许格式差异），并记录差异原因。

## 参考文档

- `references/env-playbooks.md` — Windows/Linux/Kali/WSL 搭建命令清单、PATH 与 rc 文件治理细则、编码与权限排障命令、跨平台等价写法。搭环境或排障前读。
