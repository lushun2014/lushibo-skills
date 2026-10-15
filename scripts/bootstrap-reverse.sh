#!/usr/bin/env bash
#
# 路世博 codeX 版 · 工具链自举安装器（POSIX：Linux / macOS）
#
# 与 Windows 侧 bootstrap-reverse.ps1 是同一套机制的两平台实现：
#   - 工具清单与探测规则来自同一个数据源 scripts/tool-catalog.json（禁止各写一份）
#   - 平台专属的安装命令不同（apt / brew / pip3 / npm / go），因此安装命令表在本文件内
#   - 本机没有对应包管理器时，明确报 MANUAL 并给出上游获取方式，不假装成功
#
# 用法：
#   bash bootstrap-reverse.sh                          # 默认确保 core 可用
#   bash bootstrap-reverse.sh --capability reverse
#   bash bootstrap-reverse.sh --capability reverse,pentest
#   bash bootstrap-reverse.sh --capability pe-sieve --capability sysmon
#   bash bootstrap-reverse.sh --capability @('pe-sieve','sysmon')   # 兼容 PowerShell 文档写法
#   bash bootstrap-reverse.sh --dry-run --json
#   bash bootstrap-reverse.sh --capability reverse --start-services --refresh-index
#
# 退出码：0 = 无硬失败；1 = 有硬失败；2 = 用法/环境错误

set -uo pipefail

# ─────────────────────────── 路径 ───────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CATALOG="$SCRIPT_DIR/tool-catalog.json"
INDEX="$SKILLS_ROOT/tool-index.md"
LOG_FILE="${TMPDIR:-/tmp}/lushibo-bootstrap-$(date +%Y%m%d-%H%M%S).log"

# ─────────────────────────── 参数 ───────────────────────────

CAPS=()
DRY_RUN=0
START_SERVICES=0
REFRESH_INDEX=0
JSON_OUT=0

usage() {
    sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --capability|-c)
            shift
            [ $# -gt 0 ] || { echo "错误：--capability 缺少参数" >&2; exit 2; }
            # 兼容 @('a','b') / 'a','b' / a,b 三种写法
            cleaned="$(printf '%s' "$1" | tr -d "@()[]'\"")"
            IFS=',' read -r -a _parts <<< "$cleaned"
            for _p in "${_parts[@]}"; do
                _p="$(printf '%s' "$_p" | tr -d '[:space:]')"
                [ -n "$_p" ] && CAPS+=("$_p")
            done
            ;;
        --dry-run)        DRY_RUN=1 ;;
        --start-services) START_SERVICES=1 ;;
        --refresh-index)  REFRESH_INDEX=1 ;;
        --json)           JSON_OUT=1 ;;
        -h|--help)        usage ;;
        *) echo "未知参数: $1（用 --help 查看用法）" >&2; exit 2 ;;
    esac
    shift
done

[ ${#CAPS[@]} -eq 0 ] && CAPS=("core")

# ─────────────────────────── 日志 ───────────────────────────

log() {
    local level="$1"; shift
    local msg="[$(date +%H:%M:%S)] [$level] $*"
    printf '%s\n' "$msg" >> "$LOG_FILE"
    if [ "$JSON_OUT" -eq 0 ]; then
        case "$level" in
            ERROR) printf '\033[31m%s\033[0m\n' "$msg" ;;
            WARN)  printf '\033[33m%s\033[0m\n' "$msg" ;;
            OK)    printf '\033[32m%s\033[0m\n' "$msg" ;;
            SKIP)  printf '\033[90m%s\033[0m\n' "$msg" ;;
            *)     printf '%s\n' "$msg" ;;
        esac
    fi
}

# ─────────────────────────── JSON 读取 ───────────────────────────
# 优先 python3，其次 node。两者都没有就报错退出（不猜、不硬编码工具清单）。

JSON_ENGINE=""
if command -v python3 >/dev/null 2>&1; then JSON_ENGINE="python3"
elif command -v python >/dev/null 2>&1; then JSON_ENGINE="python"
elif command -v node >/dev/null 2>&1; then JSON_ENGINE="node"
fi

if [ ! -f "$CATALOG" ]; then
    echo "[FATAL] 缺少工具目录: $CATALOG" >&2
    exit 2
fi
if [ -z "$JSON_ENGINE" ]; then
    echo "[FATAL] 需要 python3 / python / node 之一来解析 $CATALOG" >&2
    exit 2
fi

# 输出制表符分隔的工具清单： name \t group \t kind \t detect \t candidates(分号分隔) \t manual
read_catalog() {
    if [ "$JSON_ENGINE" = "node" ]; then
        node -e '
          const fs=require("fs");
          const d=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));
          for (const t of d.Tools) {
            const cands=(t.Candidates||[]).join(";");
            const man=(t.Manual||"").replace(/[\t\n\r]/g," ");
            console.log([t.Name,t.Group,t.Kind,t.Detect,cands,man].join("\t"));
          }
        ' "$CATALOG" | tr -d '\r'
    else
        "$JSON_ENGINE" - "$CATALOG" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    d = json.load(fh)
for t in d["Tools"]:
    cands = ";".join(t.get("Candidates") or [])
    man = (t.get("Manual") or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    print("\t".join([t["Name"], t["Group"], t["Kind"], t["Detect"], cands, man]))
PY
    fi
}

# 输出制表符分隔的组别名： group \t 展开后的组（分号分隔）
read_aliases() {
    if [ "$JSON_ENGINE" = "node" ]; then
        node -e '
          const fs=require("fs");
          const d=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));
          for (const [k,v] of Object.entries(d.GroupAlias||{})) console.log(k+"\t"+[].concat(v).join(";"));
        ' "$CATALOG" | tr -d '\r'
    else
        "$JSON_ENGINE" - "$CATALOG" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    d = json.load(fh)
for k, v in (d.get("GroupAlias") or {}).items():
    if not isinstance(v, list):
        v = [v]
    print(k + "\t" + ";".join(v))
PY
    fi
}

# ─────────────────────────── POSIX 安装命令表 ───────────────────────────
# 平台专属数据：apt / brew / pip3 / npm / go。
# Windows 侧的 winget/choco/scoop 命令在 tool-catalog.json 里，两者不重叠、互不替代。

posix_install() {
    case "$1" in
        git)               echo "apt:git|brew:git" ;;
        7z)                echo "apt:p7zip-full|brew:p7zip" ;;
        ripgrep)           echo "apt:ripgrep|brew:ripgrep" ;;
        jq)                echo "apt:jq|brew:jq" ;;
        py-capstone)       echo "pip3:capstone" ;;
        py-lief)           echo "pip3:lief" ;;
        py-pefile)         echo "pip3:pefile" ;;
        py-pyelftools)     echo "pip3:pyelftools" ;;
        py-requests)       echo "pip3:requests" ;;
        py-yaml)           echo "pip3:pyyaml" ;;
        py-cryptography)   echo "pip3:cryptography" ;;
        radare2)           echo "apt:radare2|brew:radare2" ;;
        rabin2)            echo "apt:radare2|brew:radare2" ;;
        jadx)              echo "brew:jadx" ;;
        apktool)           echo "apt:apktool|brew:apktool" ;;
        frida)             echo "pip3:frida frida-tools" ;;
        adb)               echo "apt:android-tools-adb|brew:android-platform-tools" ;;
        ghidra)            echo "brew:ghidra" ;;
        objdump)           echo "apt:binutils|brew:binutils" ;;
        strings)           echo "apt:binutils|brew:binutils" ;;
        py-angr)           echo "pip3:angr" ;;
        py-unicorn)        echo "pip3:unicorn" ;;
        py-pwntools)       echo "pip3:pwntools" ;;
        ROPgadget)         echo "pip3:ROPgadget" ;;
        ropper)            echo "pip3:ropper" ;;
        gdb)               echo "apt:gdb|brew:gdb" ;;
        qemu-system)       echo "apt:qemu-system|brew:qemu" ;;
        nmap)              echo "apt:nmap|brew:nmap" ;;
        sqlmap)            echo "pip3:sqlmap|apt:sqlmap" ;;
        ffuf)              echo "go:github.com/ffuf/ffuf/v2@latest|brew:ffuf" ;;
        nuclei)            echo "go:github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest|brew:nuclei" ;;
        httpx)             echo "go:github.com/projectdiscovery/httpx/cmd/httpx@latest|brew:httpx" ;;
        hashcat)           echo "apt:hashcat|brew:hashcat" ;;
        tshark)            echo "apt:tshark|brew:wireshark" ;;
        py-volatility3)    echo "pip3:volatility3" ;;
        binwalk)           echo "apt:binwalk|pip3:binwalk" ;;
        exiftool)          echo "apt:libimage-exiftool-perl|brew:exiftool" ;;
        pandoc)            echo "apt:pandoc|brew:pandoc" ;;
        libreoffice)       echo "apt:libreoffice|brew:libreoffice" ;;
        *)                 echo "" ;;
    esac
}

run_install() {
    local spec="$1"
    local mgr="${spec%%:*}"
    local pkg="${spec#*:}"
    case "$mgr" in
        apt)
            if command -v apt-get >/dev/null 2>&1; then
                if [ "$(id -u)" -eq 0 ]; then
                    apt-get install -y "$pkg"
                elif command -v sudo >/dev/null 2>&1; then
                    sudo apt-get install -y "$pkg"
                else
                    log ERROR "需要 root 或 sudo 才能 apt-get install $pkg"
                    return 1
                fi
            else
                return 1
            fi
            ;;
        brew)
            command -v brew >/dev/null 2>&1 || return 1
            brew install "$pkg"
            ;;
        pip3)
            # shellcheck disable=SC2086
            ${PIP_CMD:-pip3} install --upgrade $pkg
            ;;
        go)
            command -v go >/dev/null 2>&1 || return 1
            go install "$pkg"
            ;;
        *) return 1 ;;
    esac
}

# ─────────────────────────── 探测 ───────────────────────────

detect_tool() {
    local kind="$1" detect="$2" cands="$3"
    case "$kind" in
        python)
            ${PIP_CMD:-pip3} show "$detect" >/dev/null 2>&1 && { echo "python:$detect"; return 0; }
            return 1
            ;;
        exe|npm|mcp|manual)
            if command -v "$detect" >/dev/null 2>&1; then
                command -v "$detect"; return 0
            fi
            if [ -n "$cands" ]; then
                local IFS=';'
                for c in $cands; do
                    [ -e "$c" ] && { echo "$c"; return 0; }
                done
            fi
            return 1
            ;;
        *) return 1 ;;
    esac
}

# ─────────────────────────── 主流程 ───────────────────────────

PIP_CMD="pip3"
command -v pip3 >/dev/null 2>&1 || PIP_CMD="pip"

# 能力组别名展开
declare -A ALIAS
while IFS=$'\t' read -r k v; do
    [ -n "$k" ] && ALIAS["$k"]="$v"
done < <(read_aliases | tr -d '\r')

declare -A WANT
for cap in "${CAPS[@]}"; do
    key="$(printf '%s' "$cap" | tr '[:upper:]' '[:lower:]')"
    if [ -n "${ALIAS[$key]:-}" ]; then
        IFS=';' read -r -a gs <<< "${ALIAS[$key]}"
        for g in "${gs[@]}"; do WANT["$g"]=1; done
    else
        WANT["$key"]=1
    fi
done

if [ "$JSON_OUT" -eq 0 ]; then
    echo
    echo "════════════════════════════════════════════════════════════"
    echo " 路世博 codeX 版 · 工具链自举（POSIX）"
    echo "════════════════════════════════════════════════════════════"
    echo " skills-root : $SKILLS_ROOT"
    echo " 能力组      : $(printf '%s\n' "${!WANT[@]}" | sort | tr '\n' ' ')"
    echo " JSON 引擎   : $JSON_ENGINE"
    echo " 模式        : $([ "$DRY_RUN" -eq 1 ] && echo 'DryRun（只探测）' || echo '安装')"
    echo
fi

log INFO "skills-root = $SKILLS_ROOT"
log INFO "JSON 引擎 = $JSON_ENGINE"

PRESENT=0; INSTALLED=0; MANUAL=0; FAILED=0; WOULD=0
JSON_ROWS=""

while IFS=$'\t' read -r name group kind detect cands manual; do
    [ -z "$name" ] && continue
    gl="$(printf '%s' "$group" | tr '[:upper:]' '[:lower:]')"
    nl="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"
    [ -n "${WANT[$gl]:-}" ] || [ -n "${WANT[$nl]:-}" ] || continue

    if found="$(detect_tool "$kind" "$detect" "$cands")"; then
        log SKIP "[已有] $(printf '%-22s' "$name") $found"
        PRESENT=$((PRESENT+1))
        JSON_ROWS="${JSON_ROWS}${name}|PRESENT|${found}
"
        continue
    fi

    spec="$(posix_install "$name")"
    if [ -z "$spec" ]; then
        log WARN "[手工] $(printf '%-22s' "$name") ${manual:-无自动安装方式}"
        MANUAL=$((MANUAL+1))
        JSON_ROWS="${JSON_ROWS}${name}|MANUAL|${manual:-无自动安装方式}
"
        continue
    fi

    # 选第一个可用包管理器对应的命令
    chosen=""; IFS='|' read -r -a specs <<< "$spec"
    for s in "${specs[@]}"; do
        m="${s%%:*}"
        case "$m" in
            apt)  command -v apt-get >/dev/null 2>&1 && { chosen="$s"; break; } ;;
            brew) command -v brew >/dev/null 2>&1 && { chosen="$s"; break; } ;;
            pip3) command -v "$PIP_CMD" >/dev/null 2>&1 && { chosen="$s"; break; } ;;
            go)   command -v go >/dev/null 2>&1 && { chosen="$s"; break; } ;;
        esac
    done

    if [ -z "$chosen" ]; then
        log WARN "[手工] $(printf '%-22s' "$name") 本机无可用包管理器（需要 apt / brew / pip3 / go 之一）"
        MANUAL=$((MANUAL+1))
        JSON_ROWS="${JSON_ROWS}${name}|MANUAL|缺少包管理器
"
        continue
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        log WARN "[待装] $(printf '%-22s' "$name") ($chosen)"
        WOULD=$((WOULD+1))
        JSON_ROWS="${JSON_ROWS}${name}|WOULD_INSTALL|${chosen}
"
        continue
    fi

    log INFO "[安装] $(printf '%-22s' "$name") ($chosen)"
    if run_install "$chosen" >> "$LOG_FILE" 2>&1; then
        if found="$(detect_tool "$kind" "$detect" "$cands")"; then
            log OK "[完成] $(printf '%-22s' "$name") $found"
            INSTALLED=$((INSTALLED+1))
            JSON_ROWS="${JSON_ROWS}${name}|INSTALLED|${found}
"
        else
            log ERROR "[失败] $(printf '%-22s' "$name") 安装命令成功但重新探测仍未找到"
            FAILED=$((FAILED+1))
            JSON_ROWS="${JSON_ROWS}${name}|FAILED|重新探测未找到
"
        fi
    else
        log ERROR "[失败] $(printf '%-22s' "$name") 安装命令返回非零"
        FAILED=$((FAILED+1))
        JSON_ROWS="${JSON_ROWS}${name}|FAILED|安装命令返回非零
"
    fi
done < <(read_catalog | tr -d '\r')

# ─────────────────────────── 服务 ───────────────────────────

if [ "$START_SERVICES" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    log INFO "尝试启动 MCP 常驻服务 ..."
    for svc in idalib-mcp jshookmcp anything-analyzer; do
        if command -v "$svc" >/dev/null 2>&1; then
            nohup "$svc" >/dev/null 2>&1 &
            log OK "[启动] $svc"
        else
            log SKIP "[跳过] $svc 未安装"
        fi
    done
fi

# ─────────────────────────── 汇总 ───────────────────────────

if [ "$JSON_OUT" -eq 0 ]; then
    echo
    echo "──────────────────── 汇总 ────────────────────"
    echo " 已有 : $PRESENT"
    echo " 已装 : $INSTALLED"
    [ "$WOULD" -gt 0 ]  && echo " 待装 : $WOULD"
    [ "$MANUAL" -gt 0 ] && echo " 手工 : $MANUAL"
    [ "$FAILED" -gt 0 ] && echo " 失败 : $FAILED"
    echo
    echo " 日志: $LOG_FILE"
fi

log INFO "汇总: 已有=$PRESENT 已装=$INSTALLED 手工=$MANUAL 失败=$FAILED"

if [ "$REFRESH_INDEX" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    log INFO "刷新 tool-index.md 请使用 PowerShell 版 refresh-tool-index.ps1（POSIX 版尚未提供）"
fi

if [ "$JSON_OUT" -eq 1 ]; then
    printf '{\n'
    printf '  "skillsRoot": %s,\n' "$(printf '%s' "$SKILLS_ROOT" | sed 's/\\/\\\\/g; s/"/\\"/g; s/^/"/; s/$/"/')"
    printf '  "dryRun": %s,\n' "$([ "$DRY_RUN" -eq 1 ] && echo true || echo false)"
    printf '  "logPath": "%s",\n' "$LOG_FILE"
    printf '  "summary": { "present": %d, "installed": %d, "manual": %d, "failed": %d, "wouldInstall": %d },\n' \
        "$PRESENT" "$INSTALLED" "$MANUAL" "$FAILED" "$WOULD"
    printf '  "results": [\n'
    first=1
    while IFS='|' read -r n s p; do
        [ -z "$n" ] && continue
        [ "$first" -eq 0 ] && printf ',\n'
        first=0
        printf '    { "tool": "%s", "status": "%s", "detail": "%s" }' \
            "$(printf '%s' "$n" | sed 's/"/\\"/g')" "$s" "$(printf '%s' "$p" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    done <<< "$JSON_ROWS"
    printf '\n  ]\n}\n'
fi

[ "$FAILED" -gt 0 ] && exit 1
exit 0
