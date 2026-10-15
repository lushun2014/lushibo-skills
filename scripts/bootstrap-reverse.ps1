<#
.SYNOPSIS
    路世博 codeX 版 · 工具链自举安装器（Windows）

.DESCRIPTION
    探测本机逆向 / 渗透 / 取证 / 游戏安全工具链，安装缺失项，并重写 tool-index.md。

    设计原则：
      1. 幂等 —— 已装的不重装，重复运行安全。
      2. 诚实 —— 装不了的（如需商业授权的 IDA Pro）明确标记 MANUAL，不假装成功。
      3. 可审计 —— 每一步写日志，输出"装了 / 已有 / 失败 / 需手工"四类结果。
      4. 无破坏 —— 不覆盖已有安装，不修改系统 PATH 之外的注册表项，不删任何文件。

.PARAMETER Capability
    要确保可用的能力组。可多选。默认 'core'。
    可用值：
      core               基础：git / 7z / python 分析库 / 文本工具
      reverse            通用逆向：radare2 / jadx / apktool / frida / adb / ghidra
      ida                IDA Pro 与 idalib-mcp（商业授权，多为 MANUAL）
      bindiff            二进制差分：bindiff / ghidriff
      pwn                漏洞利用：pwntools / ROPgadget / ropper / one_gadget / qemu
      pentest            渗透：nmap / sqlmap / ffuf / nuclei / hashcat / httpx
      forensics          取证：tshark / volatility3 / binwalk / unblob / exiftool
      edr                EDR 研究：pe-sieve / syswhispers3 / sysmon / wsuspect-proxy
      game               游戏安全：cheat-engine / jshookmcp
      jshookmcp          JS Hook MCP 服务
      anything-analyzer  Anything Analyzer MCP 服务
      docs               文档：pandoc / libreoffice

.PARAMETER StartServices
    安装完成后尝试启动 MCP 类常驻服务（jshookmcp / anything-analyzer / idalib-mcp）。

.PARAMETER DryRun
    只探测与报告，不做任何安装。

.PARAMETER RefreshIndex
    安装完成后重新生成 <skills-root>/tool-index.md 的机器生成段。

.PARAMETER Json
    以 JSON 输出结果，便于程序消费。

.PARAMETER LogPath
    日志文件路径。默认写到 %TEMP%\lushibo-bootstrap-<timestamp>.log

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap-reverse.ps1
    # 默认确保 core 可用

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap-reverse.ps1 -Capability @('jshookmcp')

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap-reverse.ps1 -Capability @('pe-sieve','syswhispers3','sysmon') -StartServices

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap-reverse.ps1 -DryRun -Json
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string[]]$Capability = @('core'),

    # 兼容 `powershell -File ... -Capability @('a','b','c')`：
    # 经 native 调用时 @(...) 会被拆成多个 argv，多出来的 token 落到这里。
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraCapability,

    [switch]$StartServices,
    [switch]$DryRun,
    [switch]$RefreshIndex,
    [switch]$Json,
    [string]$LogPath
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

# 归一化能力组入参：兼容全部四种写法
#   -Capability reverse
#   -Capability reverse,pentest
#   -Capability 'reverse','pentest'
#   -Capability @('reverse','pentest')   ← -File 下被拆成多 token，多余部分进 $ExtraCapability
$Capability = @(
    @($Capability) + @($ExtraCapability) |
        ForEach-Object { $_ -split ',' } |
        ForEach-Object { $_ -replace '[@()\[\]''"\s]', '' } |
        Where-Object { $_ -ne '' } |
        Select-Object -Unique
)
if (-not $Capability -or $Capability.Count -eq 0) { $Capability = @('core') }

# ─────────────────────────── 路径与日志 ───────────────────────────

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsRoot  = Split-Path -Parent $ScriptDir
$IndexPath   = Join-Path $SkillsRoot 'tool-index.md'

if (-not $LogPath) {
    $LogPath = Join-Path $env:TEMP ("lushibo-bootstrap-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}

$script:Log = New-Object System.Collections.Generic.List[string]

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'HH:mm:ss'), $Level, $Message
    $script:Log.Add($line) | Out-Null
    if (-not $Json) {
        switch ($Level) {
            'ERROR' { Write-Host $line -ForegroundColor Red }
            'WARN'  { Write-Host $line -ForegroundColor Yellow }
            'OK'    { Write-Host $line -ForegroundColor Green }
            'SKIP'  { Write-Host $line -ForegroundColor DarkGray }
            default { Write-Host $line }
        }
    }
}

function Save-Log {
    try {
        $dir = Split-Path -Parent $LogPath
        if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $script:Log -join [Environment]::NewLine | Set-Content -Path $LogPath -Encoding UTF8
    } catch {
        Write-Host ("[WARN] 日志写入失败: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
}

# ─────────────────────────── 探测原语（共享库） ───────────────────────────
# 探测逻辑统一定义在 tool-detect.ps1，本脚本与 refresh-tool-index.ps1 共用。
# 禁止在此重新实现探测函数 —— 两份探测逻辑漂移会导致工具状态判断互相矛盾。

. (Join-Path $ScriptDir 'tool-detect.ps1')
# ─────────────────────────── 工具目录（单一数据源） ───────────────────────────
# 目录定义在 tool-catalog.json，本脚本与 refresh-tool-index.ps1 共用同一份。
# 禁止各自维护副本 —— 两份目录会互相漂移，这正是本包要消灭的缺陷类别。

$CatalogPath = Join-Path $ScriptDir 'tool-catalog.json'
try {
    $Catalog = Import-ToolCatalog -Path $CatalogPath
} catch {
    Write-Host ("[FATAL] {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 2
}

$ToolCatalog = $Catalog.Tools
$GroupAlias  = $Catalog.GroupAlias
# ─────────────────────────── 能力组展开 ───────────────────────────

$GroupAlias = @{
    'core'      = @('core')
    'reverse'   = @('core', 'reverse')
    'ida'       = @('core', 'reverse', 'ida')
    'bindiff'   = @('core', 'reverse', 'bindiff')
    'pwn'       = @('core', 'pwn')
    'pentest'   = @('core', 'pentest')
    'forensics' = @('core', 'forensics')
    'edr'       = @('core', 'edr')
    'game'      = @('core', 'reverse', 'game')
    'docs'      = @('core', 'docs')
}

$Requested = New-Object System.Collections.Generic.HashSet[string]
foreach ($cap in $Capability) {
    $c = $cap.Trim().ToLowerInvariant()
    if ($GroupAlias.ContainsKey($c)) {
        foreach ($g in $GroupAlias[$c]) { [void]$Requested.Add($g) }
    } else {
        # 直接指定单个工具名或组名
        [void]$Requested.Add($c)
    }
}

$Selected = $ToolCatalog | Where-Object { $Requested.Contains($_.Group.ToLowerInvariant()) -or $Requested.Contains($_.Name.ToLowerInvariant()) }

# ─────────────────────────── 主流程 ───────────────────────────

if (-not $Json) {
    Write-Host ''
    Write-Host '════════════════════════════════════════════════════════════' -ForegroundColor Cyan
    Write-Host ' 路世博 codeX 版 · 工具链自举' -ForegroundColor Cyan
    Write-Host '════════════════════════════════════════════════════════════' -ForegroundColor Cyan
    Write-Host (" skills-root : {0}" -f $SkillsRoot)
    Write-Host (" 能力组      : {0}" -f (($Requested | Sort-Object) -join ', '))
    Write-Host (" 待检查工具  : {0}" -f $Selected.Count)
    Write-Host (" 模式        : {0}" -f $(if ($DryRun) { 'DryRun（只探测）' } else { '安装' }))
    Write-Host ''
}

Write-Log ("skills-root = {0}" -f $SkillsRoot)
Write-Log ("请求能力组 = {0}" -f (($Requested | Sort-Object) -join ', '))
Write-Log ("可用包管理器 = {0}" -f ((Get-PackageManager) -join ', '))

$PackageManagers = Get-PackageManager
$PythonExe = Get-PythonExe

$Results = @()

foreach ($tool in $Selected) {
    $name = $tool.Name
    $kind = $tool.Kind
    $found = $null

    $found = Test-ToolPresent -Tool $tool -PythonExe $PythonExe

    if ($found) {
        Write-Log ("[已有] {0,-22} {1}" -f $name, $found) 'SKIP'
        $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='PRESENT'; Path=$found; Note='' }
        continue
    }

    # 缺失 —— 决定怎么装
    if ($tool.Install) {
        $chosen = $null
        foreach ($pm in @('winget', 'choco', 'scoop', 'pip')) {
            if ($tool.Install.ContainsKey($pm) -and $PackageManagers -contains $pm) { $chosen = $pm; break }
        }
        if (-not $chosen) {
            Write-Log ("[失败] {0,-22} 缺少可用包管理器（需要 winget/choco/scoop/pip 之一）" -f $name) 'ERROR'
            $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='NO_PM'; Path=''; Note='缺少包管理器' }
            continue
        }
        $cmd = $tool.Install[$chosen]
        if ($DryRun) {
            Write-Log ("[待装] {0,-22} ({1}) {2}" -f $name, $chosen, $cmd) 'WARN'
            $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='WOULD_INSTALL'; Path=''; Note="$chosen : $cmd" }
            continue
        }
        Write-Log ("[安装] {0,-22} ({1}) {2}" -f $name, $chosen, $cmd)
        try {
            $parts = $cmd -split '\s+'
            $exe = $parts[0]; $rest = @()
            if ($parts.Length -gt 1) { $rest = $parts[1..($parts.Length - 1)] }
            & $exe @rest 2>&1 | ForEach-Object { $script:Log.Add("    $_") | Out-Null }
            $code = $LASTEXITCODE
        } catch {
            Write-Log ("[失败] {0,-22} {1}" -f $name, $_.Exception.Message) 'ERROR'
            $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='FAILED'; Path=''; Note=$_.Exception.Message }
            continue
        }
        # 重新探测
        $after = Test-ToolPresent -Tool $tool -PythonExe $PythonExe
        if ($after) {
            Write-Log ("[完成] {0,-22} {1}" -f $name, $after) 'OK'
            $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='INSTALLED'; Path=$after; Note=$chosen }
        } else {
            Write-Log ("[失败] {0,-22} 安装命令退出码 {1}，重新探测仍未找到" -f $name, $code) 'ERROR'
            $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='FAILED'; Path=''; Note="exit=$code" }
        }
    } else {
        Write-Log ("[手工] {0,-22} {1}" -f $name, $tool.Manual) 'WARN'
        $Results += [pscustomobject]@{ Tool=$name; Group=$tool.Group; Status='MANUAL'; Path=''; Note=$tool.Manual }
    }
}

# ─────────────────────────── 服务启动 ───────────────────────────

if ($StartServices -and -not $DryRun) {
    Write-Host ''
    Write-Log '尝试启动 MCP 常驻服务 ...'
    $services = @(
        @{ Name='idalib-mcp';        Cmd='idalib-mcp' },
        @{ Name='jshookmcp';         Cmd='jshookmcp' },
        @{ Name='anything-analyzer'; Cmd='anything-analyzer' }
    )
    foreach ($svc in $services) {
        $exe = Get-CommandPath $svc.Cmd
        if (-not $exe) { Write-Log ("[跳过] {0} 未安装" -f $svc.Name) 'SKIP'; continue }
        try {
            Start-Process -FilePath $exe -WindowStyle Hidden -ErrorAction Stop
            Write-Log ("[启动] {0}" -f $svc.Name) 'OK'
        } catch {
            Write-Log ("[失败] {0} 启动失败: {1}" -f $svc.Name, $_.Exception.Message) 'ERROR'
        }
    }
}

# ─────────────────────────── 汇总 ───────────────────────────

$present   = @($Results | Where-Object { $_.Status -eq 'PRESENT' })
$installed = @($Results | Where-Object { $_.Status -eq 'INSTALLED' })
$manual    = @($Results | Where-Object { $_.Status -eq 'MANUAL' })
$failed    = @($Results | Where-Object { $_.Status -in @('FAILED', 'NO_PM') })
$would     = @($Results | Where-Object { $_.Status -eq 'WOULD_INSTALL' })

# 注意：本段必须受 -Json 保护，否则汇总框会混进 stdout 破坏 JSON 可解析性
if (-not $Json) {
    Write-Host ''
    Write-Host '──────────────────── 汇总 ────────────────────' -ForegroundColor Cyan
    Write-Host (" 已有 : {0}" -f $present.Count)   -ForegroundColor Green
    Write-Host (" 已装 : {0}" -f $installed.Count) -ForegroundColor Green
    if ($would.Count)   { Write-Host (" 待装 : {0}" -f $would.Count)   -ForegroundColor Yellow }
    if ($manual.Count)  { Write-Host (" 手工 : {0}" -f $manual.Count)  -ForegroundColor Yellow }
    if ($failed.Count)  { Write-Host (" 失败 : {0}" -f $failed.Count)  -ForegroundColor Red }
}

if ($manual.Count -and -not $Json) {
    Write-Host ''
    Write-Host ' 需手工处理：' -ForegroundColor Yellow
    foreach ($m in $manual) { Write-Host ("   - {0}：{1}" -f $m.Tool, $m.Note) -ForegroundColor Yellow }
}
if ($failed.Count -and -not $Json) {
    Write-Host ''
    Write-Host ' 安装失败：' -ForegroundColor Red
    foreach ($f in $failed) { Write-Host ("   - {0}：{1}" -f $f.Tool, $f.Note) -ForegroundColor Red }
}

Write-Log ("汇总: 已有={0} 已装={1} 手工={2} 失败={3}" -f $present.Count, $installed.Count, $manual.Count, $failed.Count)

# ─────────────────────────── 刷新索引 ───────────────────────────

if ($RefreshIndex) {
    $refresh = Join-Path $ScriptDir 'refresh-tool-index.ps1'
    if (Test-Path $refresh) {
        Write-Log '刷新 tool-index.md ...'
        if (-not $DryRun) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $refresh 2>&1 | ForEach-Object { $script:Log.Add("    $_") | Out-Null }
        }
    } else {
        Write-Log ("未找到 {0}，跳过索引刷新" -f $refresh) 'WARN'
    }
}

Save-Log
if (-not $Json) {
    Write-Host ''
    Write-Host (" 日志: {0}" -f $LogPath) -ForegroundColor DarkGray
}

# ─────────────────────────── 输出 ───────────────────────────

if ($Json) {
    $payload = [pscustomobject]@{
        skillsRoot    = $SkillsRoot
        requested     = @($Requested | Sort-Object)
        dryRun        = [bool]$DryRun
        logPath       = $LogPath
        results       = $Results
        summary       = [pscustomobject]@{
            present   = $present.Count
            installed = $installed.Count
            manual    = $manual.Count
            failed    = $failed.Count
            wouldInstall = $would.Count
        }
    }
    $payload | ConvertTo-Json -Depth 6
}

# 退出码：有硬失败（装了但没成 / 无包管理器）→ 1；其余 → 0
if ($failed.Count -gt 0) { exit 1 }
exit 0
