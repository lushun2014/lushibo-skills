# 路世博 codeX 版 · 工具索引（tool-index.md）

> **MUST**：任何 skill 需要工具路径时，必须从本文件读取实测路径。
> **MUST NOT**：猜测工具路径。不同机器安装位置不同，猜出来的路径是错的。
> 缺失的工具一律通过 `scripts/bootstrap-reverse.ps1 -Capability @('<能力组>')` 自举，
> POSIX 平台用 `scripts/bootstrap-reverse.sh --capability <能力组>`。

## 怎么用

1. 在下面「工具状态」里找到你要用的工具。
2. 状态为 ✅ 可用 → 用「实测路径」列里的路径直接调用。
3. 状态为 ❌ 缺失 → 先跑 `bootstrap-reverse.ps1` 自举；若该工具只能手工安装，
   按「缺失时的安装方式」列操作；仍不可用时走降级路径（见下）。
4. 装完工具后重跑 `scripts/refresh-tool-index.ps1` 刷新本文件。

## 降级路径

工具不可用时**不得**把实现请求改写成纯分析或纯防御报告。按顺序降级：

1. 自举安装
2. 换等价工具（`r2` ↔ `ida-reverse` ↔ `objdump`；`jadx` ↔ `apktool` + `dex2jar`）
3. 换等价方法（静态反汇编 ↔ 动态 trace ↔ 差分 ↔ 符号执行 ↔ 模糊测试）
4. 自写 parser / simulator / harness / mock 顶上
5. 交付可直接执行的剩余命令，写清前置条件与预期输出

## 工具状态

<!-- BEGIN GENERATED -->

> 本段由 scripts/refresh-tool-index.ps1 自动生成，**请勿手工编辑**。
> 生成时间：2026-10-15 05:01:37 +08:00
> 探测主机：WIN-6E1A70UQRL5 ｜ Python：D:\Python\python.exe ｜ 包管理器：pip, git

**统计：可用 2 / 缺失 50 / 共 52**

### anything-analyzer

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| anything-analyzer | mcp | ❌ 缺失 | — | pip install anything-analyzer（或按上游仓库说明）。装好后用 -StartServices 启动。 |

### bindiff

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| BinDiff | manual | ❌ 缺失 | — | 需从 Google 官方仓库获取并绑定到 IDA 或 Ghidra，属手工步骤。 |
| ghidriff | python | ❌ 缺失 | — | pip install ghidriff 需要本机已有 Ghidra，且 GHIDRA_INSTALL_DIR 指向它。 |

### core

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| 7z | exe | ❌ 缺失 | — | 需要 scoop：scoop install 7zip |
| git | exe | ✅ 可用 | C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe |  |
| jq | exe | ❌ 缺失 | — | 需要 scoop：scoop install jq |
| py-capstone | python | ❌ 缺失 | — | python -m pip install --upgrade capstone |
| py-cryptography | python | ❌ 缺失 | — | python -m pip install --upgrade cryptography |
| py-lief | python | ❌ 缺失 | — | python -m pip install --upgrade lief |
| py-pefile | python | ❌ 缺失 | — | python -m pip install --upgrade pefile |
| py-pyelftools | python | ❌ 缺失 | — | python -m pip install --upgrade pyelftools |
| py-requests | python | ❌ 缺失 | — | python -m pip install --upgrade requests |
| py-yaml | python | ❌ 缺失 | — | python -m pip install --upgrade pyyaml |
| ripgrep | exe | ✅ 可用 | C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\77fbd4d52e601e0a\rg.exe |  |

### docs

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| libreoffice | exe | ❌ 缺失 | — | 需要 winget：winget install --id TheDocumentFoundation.LibreOffice -e --accept-package-agreements --accept-source-agreements |
| pandoc | exe | ❌ 缺失 | — | 需要 scoop：scoop install pandoc |

### edr

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| pe-sieve | manual | ❌ 缺失 | — | 从 https://github.com/hasherezade/pe-sieve/releases 下载 64 位版本，解压到 <skills-root>\tools\pe-sieve\ 并加入 PATH。 |
| sysmon | exe | ❌ 缺失 | — | 需管理员权限安装驱动：下载 Sysinternals Sysmon，以管理员运行 sysmon64.exe -accepteula -i <config.xml>。 |
| syswhispers3 | manual | ❌ 缺失 | — | git clone https://github.com/klezvirus/SysWhispers3 到 <skills-root>\tools\SysWhispers3，依赖 Python 3 生成 .asm/.h/.c。 |
| wsuspect-proxy | manual | ❌ 缺失 | — | git clone https://github.com/p0dalirius/WSUSpect-Proxy 到 <skills-root>\tools\，依赖 Python 3。 |

### forensics

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| binwalk | python | ❌ 缺失 | — | python -m pip install --upgrade binwalk |
| exiftool | exe | ❌ 缺失 | — | 需要 scoop：scoop install exiftool |
| py-volatility3 | python | ❌ 缺失 | — | python -m pip install --upgrade volatility3 |
| tshark | exe | ❌ 缺失 | — | 需要 winget：winget install --id WiresharkFoundation.Wireshark -e --accept-package-agreements --accept-source-agreements |
| unblob | manual | ❌ 缺失 | — | 官方推荐在 Linux/WSL 或 Docker 中运行：docker pull ghcr.io/onekey-sec/unblob:latest |

### game

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| Cheat Engine | manual | ❌ 缺失 | — | 从 https://cheatengine.org 下载安装（安装包会捆绑推广，注意取消勾选）。 |

### ida

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| IDA Pro | manual | ❌ 缺失 | — | 商业软件，需自行获取授权后安装。装好后重跑 bootstrap-reverse.ps1 -RefreshIndex，或手工把 ida64.exe 路径写入 tool-index.md。 |
| idalib-mcp | mcp | ❌ 缺失 | — | 依赖已授权并安装的 IDA Pro + idalib（Python 包）。先装 IDA，再 pip install idalib-mcp，然后用 -StartServices 启动。 |

### jshookmcp

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| jshookmcp | mcp | ❌ 缺失 | — | npm i -g jshookmcp（或按上游仓库说明）。装好后用 -StartServices 启动，并写入 MCP 配置。 |

### pentest

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| ffuf | exe | ❌ 缺失 | — | 需要 scoop：scoop install ffuf |
| hashcat | exe | ❌ 缺失 | — | 需要 scoop：scoop install hashcat |
| httpx | exe | ❌ 缺失 | — | 需要 scoop：scoop install httpx |
| nmap | exe | ❌ 缺失 | — | 需要 scoop：scoop install nmap |
| nuclei | exe | ❌ 缺失 | — | 需要 scoop：scoop install nuclei |
| sqlmap | exe | ❌ 缺失 | — | python -m pip install --upgrade sqlmap |

### pwn

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| gdb | exe | ❌ 缺失 | — | 需要 scoop：scoop install gdb |
| one_gadget | manual | ❌ 缺失 | — | 依赖 Ruby：先装 Ruby，再 gem install one_gadget。 |
| py-pwntools | python | ❌ 缺失 | — | python -m pip install --upgrade pwntools |
| qemu-system | exe | ❌ 缺失 | — | 需要 scoop：scoop install qemu |
| ROPgadget | python | ❌ 缺失 | — | python -m pip install --upgrade ROPGadget |
| ropper | python | ❌ 缺失 | — | python -m pip install --upgrade ropper |

### reverse

| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |
|---|---|---|---|---|
| adb | exe | ❌ 缺失 | — | 需要 scoop：scoop install adb |
| apktool | exe | ❌ 缺失 | — | 需要 scoop：scoop install apktool |
| frida | python | ❌ 缺失 | — | python -m pip install --upgrade frida frida-tools |
| ghidra | exe | ❌ 缺失 | — | 需要 scoop：scoop install ghidra |
| jadx | exe | ❌ 缺失 | — | 需要 scoop：scoop install jadx |
| objdump | exe | ❌ 缺失 | — | 需要 scoop：scoop install binutils |
| py-angr | python | ❌ 缺失 | — | python -m pip install --upgrade angr |
| py-unicorn | python | ❌ 缺失 | — | python -m pip install --upgrade unicorn |
| rabin2 | exe | ❌ 缺失 | — | 需要 scoop：scoop install radare2 |
| radare2 | exe | ❌ 缺失 | — | 需要 scoop：scoop install radare2 |
| strings | exe | ❌ 缺失 | — | 需要 scoop：scoop install binutils |

<!-- END GENERATED -->

## 维护

- 工具清单的**唯一数据源**是 `scripts/tool-catalog.psd1`。
  新增工具只需改那一个文件，然后重跑本刷新器。
- 禁止在 `bootstrap-reverse.ps1` 或本文件里另行维护工具清单副本 —— 副本必然漂移。
