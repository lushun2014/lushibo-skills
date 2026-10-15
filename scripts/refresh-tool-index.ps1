<#
.SYNOPSIS
    路世博 codeX 版 · 工具索引刷新器

.DESCRIPTION
    探测本机工具链，重写 <skills-root>/tool-index.md 的机器生成段。

    为什么需要它：
      不同机器上工具的安装位置不同。任何 skill 都**禁止猜测工具路径**，
      必须从 tool-index.md 读取实测路径。本脚本负责把实测结果写进去。

    生成段由下列标记界定，标记之外的正文（使用说明、降级指引）会被保留：
        <!-- BEGIN GENERATED -->
        <!-- END GENERATED -->

.PARAMETER Json
    以 JSON 输出探测结果，不写文件。

.PARAMETER Quiet
    不打印进度，只输出最终统计。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File refresh-tool-index.ps1
#>

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsRoot = Split-Path -Parent $ScriptDir
$IndexPath  = Join-Path $SkillsRoot 'tool-index.md'
$CatalogPath = Join-Path $ScriptDir 'tool-catalog.json'

. (Join-Path $ScriptDir 'tool-detect.ps1')

if (-not (Test-Path -LiteralPath $CatalogPath)) {
    Write-Error "缺少工具目录: $CatalogPath"
    exit 2
}

$Catalog = Import-ToolCatalog -Path $CatalogPath
$Tools   = $Catalog.Tools
$PythonExe = Get-PythonExe
$PkgMgrs   = Get-PackageManager

if (-not $Quiet -and -not $Json) {
    Write-Host ("探测 {0} 项工具 ..." -f $Tools.Count) -ForegroundColor Cyan
}

$Rows = @()
foreach ($t in $Tools) {
    $path = Test-ToolPresent -Tool $t -PythonExe $PythonExe
    $status = if ($path) { 'PRESENT' } else { 'MISSING' }

    # 给出"缺了怎么装"的一行命令
    # 注意：PowerShell 里空哈希表 @{} 的布尔值是 $true，不能用 `if ($t.Install)` 判断有无安装命令，
    #       必须按 Key 计数判断，否则无安装命令的工具会走进这里并索引空 Keys 得到 $null。
    $installHint = ''
    if (-not $path) {
        $installKeys = @()
        if ($t.Install) { $installKeys = @($t.Install.Keys) }

        if ($installKeys.Count -gt 0) {
            foreach ($pm in @('winget', 'choco', 'scoop', 'pip')) {
                if ($installKeys -contains $pm -and $PkgMgrs -contains $pm) {
                    $installHint = $t.Install[$pm]
                    break
                }
            }
            if (-not $installHint) {
                # 本机没有对应包管理器，给出通用建议
                $anyKey = $installKeys[0]
                $installHint = ("需要 {0}：{1}" -f $anyKey, $t.Install[$anyKey])
            }
        } elseif ($t.Manual) {
            $installHint = $t.Manual
        } else {
            $installHint = '无自动安装方式'
        }
    }

    $Rows += [pscustomobject]@{
        Tool    = $t.Name
        Group   = $t.Group
        Kind    = $t.Kind
        Status  = $status
        Path    = if ($path) { $path } else { '—' }
        Install = $installHint
    }
}

$present = @($Rows | Where-Object { $_.Status -eq 'PRESENT' })
$missing = @($Rows | Where-Object { $_.Status -eq 'MISSING' })

# ─────────────── 生成 Markdown ───────────────

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("<!-- BEGIN GENERATED -->")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("> 本段由 `scripts/refresh-tool-index.ps1` 自动生成，**请勿手工编辑**。")
[void]$sb.AppendLine("> 生成时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')")
[void]$sb.AppendLine("> 探测主机：$env:COMPUTERNAME ｜ Python：$(if ($PythonExe) { $PythonExe } else { '未找到' }) ｜ 包管理器：$(if ($PkgMgrs) { $PkgMgrs -join ', ' } else { '无' })")
[void]$sb.AppendLine("")
[void]$sb.AppendLine(("**统计：可用 {0} / 缺失 {1} / 共 {2}**" -f $present.Count, $missing.Count, $Rows.Count))
[void]$sb.AppendLine("")

# 按能力组分组输出
$groups = $Rows | Group-Object Group | Sort-Object Name
foreach ($g in $groups) {
    [void]$sb.AppendLine(("### {0}" -f $g.Name))
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("| 工具 | 类型 | 状态 | 实测路径 | 缺失时的安装方式 |")
    [void]$sb.AppendLine("|---|---|---|---|---|")
    foreach ($r in ($g.Group | Sort-Object Tool)) {
        $mark = if ($r.Status -eq 'PRESENT') { '✅ 可用' } else { '❌ 缺失' }
        $p = $r.Path -replace '\|', '\|'
        $ins = $r.Install -replace '\|', '\|'
        [void]$sb.AppendLine(("| {0} | {1} | {2} | `{3}` | {4} |" -f $r.Tool, $r.Kind, $mark, $p, $ins))
    }
    [void]$sb.AppendLine("")
}

[void]$sb.AppendLine("<!-- END GENERATED -->")

$generated = $sb.ToString()

if ($Json) {
    [pscustomobject]@{
        skillsRoot = $SkillsRoot
        indexPath  = $IndexPath
        python     = $PythonExe
        packageManagers = $PkgMgrs
        present    = $present.Count
        missing    = $missing.Count
        rows       = $Rows
    } | ConvertTo-Json -Depth 5
    exit 0
}

# ─────────────── 写入（保留标记之外的正文） ───────────────

$beginMark = '<!-- BEGIN GENERATED -->'
$endMark   = '<!-- END GENERATED -->'

$template = @'
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
<!-- END GENERATED -->

## 维护

- 工具清单的**唯一数据源**是 `scripts/tool-catalog.json`。
  新增工具只需改那一个文件，然后重跑本刷新器。
- 禁止在 `bootstrap-reverse.ps1` 或本文件里另行维护工具清单副本 —— 副本必然漂移。
'@

$newContent = $null

if (Test-Path -LiteralPath $IndexPath) {
    $existing = [System.IO.File]::ReadAllText($IndexPath)
    $bi = $existing.IndexOf($beginMark)
    $ei = $existing.IndexOf($endMark)
    if ($bi -ge 0 -and $ei -gt $bi) {
        $newContent = $existing.Substring(0, $bi) + $generated.TrimEnd() + $existing.Substring($ei + $endMark.Length)
    } else {
        # 已有文件但没有标记：整篇替换，并备份原文件
        $bak = "$IndexPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item -LiteralPath $IndexPath -Destination $bak -Force
        if (-not $Quiet) { Write-Host ("[WARN] 原文件无生成标记，已备份到 {0}，整篇重写" -f $bak) -ForegroundColor Yellow }
        $newContent = $template.TrimEnd() + [Environment]::NewLine
        $bi = $newContent.IndexOf($beginMark)
        $ei = $newContent.IndexOf($endMark)
        $newContent = $newContent.Substring(0, $bi) + $generated.TrimEnd() + $newContent.Substring($ei + $endMark.Length)
    }
} else {
    $newContent = $template.TrimEnd() + [Environment]::NewLine
    $bi = $newContent.IndexOf($beginMark)
    $ei = $newContent.IndexOf($endMark)
    $newContent = $newContent.Substring(0, $bi) + $generated.TrimEnd() + $newContent.Substring($ei + $endMark.Length)
}

# 统一为 LF，并写 UTF-8（无 BOM —— .md 不需要 BOM）
$newContent = $newContent.Replace("`r`n", "`n").Replace("`r", "`n")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($IndexPath, $newContent, $utf8NoBom)

if (-not $Quiet) {
    Write-Host ''
    Write-Host ("已写入 : {0}" -f $IndexPath) -ForegroundColor Green
    Write-Host ("可用   : {0}" -f $present.Count) -ForegroundColor Green
    Write-Host ("缺失   : {0}" -f $missing.Count) -ForegroundColor Yellow
    if ($missing.Count) {
        Write-Host ''
        Write-Host '缺失工具：' -ForegroundColor Yellow
        foreach ($m in ($missing | Sort-Object Group, Tool)) {
            Write-Host ("  - [{0}] {1}" -f $m.Group, $m.Tool) -ForegroundColor Yellow
        }
    }
}

exit 0
