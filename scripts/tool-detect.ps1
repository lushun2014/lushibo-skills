<#
.SYNOPSIS
    路世博 codeX 版 · 工具探测原语（共享库）

.DESCRIPTION
    bootstrap-reverse.ps1 与 refresh-tool-index.ps1 共用本文件。
    禁止任一方自带副本 —— 两份探测逻辑漂移会导致"装了的工具被报缺失"或反之。

    被 dot-source 使用：
        . (Join-Path $ScriptDir 'tool-detect.ps1')

    导出函数：
        Get-CommandPath       命令名 → 绝对路径（找不到返回 $null）
        Test-PathAny          一组路径 → 第一个存在的（都没有返回 $null）
        Get-PythonExe         找到可用的 python 解释器
        Test-PythonModule     探测 python 模块是否可导入
        Get-PackageManager    列出本机可用的包管理器
        Test-ToolPresent      目录项 → 状态（统一的探测语义）
#>

# 注意：本文件必须保存为 UTF-8 with BOM。
# Windows PowerShell 5.1 读取无 BOM 的 UTF-8 .ps1 会按 ANSI 解码，中文注释与字符串会乱码。

function Get-CommandPath {
    <# 返回命令的绝对路径；找不到返回 $null。 #>
    param([Parameter(Mandatory)][string]$Name)
    $c = Get-Command $Name -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}

function Test-PathAny {
    <# 返回 $Paths 中第一个存在的路径；都不存在返回 $null。 #>
    param([string[]]$Paths)
    if (-not $Paths) { return $null }
    foreach ($p in $Paths) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return $null
}

function Get-PythonExe {
    <# 依次尝试 python / python3 / py，返回第一个可用的解释器路径。 #>
    foreach ($n in @('python', 'python3', 'py')) {
        $p = Get-CommandPath $n
        if ($p) { return $p }
    }
    return $null
}

function Test-PythonModule {
    <# 探测 $Module 能否被 $PythonExe 导入。用 find_spec 避免真的执行模块。 #>
    param(
        [string]$PythonExe,
        [Parameter(Mandatory)][string]$Module
    )
    if (-not $PythonExe) { return $false }
    if ($Module -notmatch '^[A-Za-z_][A-Za-z0-9_.]*$') { return $false }   # 防注入
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $code = "import importlib.util as u, sys; sys.exit(0 if u.find_spec('$Module') else 1)"
        & $PythonExe -c $code 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Get-PackageManager {
    <# 列出本机可用的包管理器，按优先级排序。 #>
    $mgrs = @()
    if (Get-CommandPath 'winget') { $mgrs += 'winget' }
    if (Get-CommandPath 'choco')  { $mgrs += 'choco' }
    if (Get-CommandPath 'scoop')  { $mgrs += 'scoop' }
    if (Get-PythonExe)            { $mgrs += 'pip' }
    if (Get-CommandPath 'npm')    { $mgrs += 'npm' }
    if (Get-CommandPath 'git')    { $mgrs += 'git' }
    return $mgrs
}

function Test-ToolPresent {
    <#
    .SYNOPSIS
        统一探测语义：给定工具目录项，返回"已找到"的证据字符串，或 $null。
    .DESCRIPTION
        这是 bootstrap 与 refresh 唯一允许使用的探测入口。
        任何一处需要判断工具是否存在，都必须调本函数，不得自行拼装探测逻辑。
    .PARAMETER Tool
        tool-catalog.psd1 中的一项（含 Kind / Detect / Candidates）。
    .PARAMETER PythonExe
        可选的 python 解释器路径；未提供时自动探测。
    #>
    param(
        [Parameter(Mandatory)]$Tool,
        [string]$PythonExe
    )

    $kind = $Tool.Kind
    $detect = $Tool.Detect
    $cands = $Tool.Candidates

    switch ($kind) {
        'python' {
            if (-not $PythonExe) { $PythonExe = Get-PythonExe }
            if (Test-PythonModule -PythonExe $PythonExe -Module $detect) {
                return ("python:{0} ({1})" -f $detect, $PythonExe)
            }
            return $null
        }
        'exe' {
            $found = Get-CommandPath $detect
            if (-not $found) { $found = Test-PathAny $cands }
            return $found
        }
        'npm' {
            $found = Get-CommandPath $detect
            if (-not $found) { $found = Test-PathAny $cands }
            return $found
        }
        'mcp' {
            $found = Get-CommandPath $detect
            if (-not $found) { $found = Test-PathAny $cands }
            return $found
        }
        'manual' {
            $found = Get-CommandPath $detect
            if (-not $found) { $found = Test-PathAny $cands }
            return $found
        }
        default {
            $found = Get-CommandPath $detect
            if (-not $found) { $found = Test-PathAny $cands }
            return $found
        }
    }
}

function Import-ToolCatalog {
    <#
    .SYNOPSIS
        加载 tool-catalog.json（跨平台单一数据源），并展开 Candidates 里的 %VAR% 占位符。
    .DESCRIPTION
        选 JSON 而不是 .psd1 的原因：POSIX 侧的 bootstrap-reverse.sh 也要读同一份目录。
        .psd1 只有 PowerShell 能解析，会逼出第二份清单，进而漂移。

        本函数把 JSON 的嵌套对象**归一化成 hashtable**，这样调用方可以照常使用
        $t.Install.ContainsKey(...) / $t.Install[$pm] 这类写法。
    #>
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "缺少工具目录: $Path"
    }

    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $data = $raw | ConvertFrom-Json

    $tools = @(
        foreach ($t in $data.Tools) {
            # Candidates：展开 %VAR% 环境变量占位符
            $cands = @()
            if ($t.Candidates) {
                foreach ($c in $t.Candidates) {
                    $cands += [Environment]::ExpandEnvironmentVariables($c)
                }
            }

            # Install：PSCustomObject → hashtable，保持下游写法不变
            $install = @{}
            if ($t.Install) {
                foreach ($p in $t.Install.PSObject.Properties) {
                    $install[$p.Name] = $p.Value
                }
            }

            @{
                Name       = $t.Name
                Group      = $t.Group
                Kind       = $t.Kind
                Detect     = $t.Detect
                Candidates = $cands
                Install    = $install
                Manual     = $t.Manual
            }
        }
    )

    $alias = @{}
    if ($data.GroupAlias) {
        foreach ($p in $data.GroupAlias.PSObject.Properties) {
            $alias[$p.Name] = @($p.Value)
        }
    }

    return [pscustomobject]@{
        Tools      = $tools
        GroupAlias = $alias
    }
}
