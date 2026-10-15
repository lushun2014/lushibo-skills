#!/usr/bin/env python3
"""跨平台环境审计与工具链自举检查（Windows / Linux / Kali / macOS）。

采集：系统与身份、工具链版本、持久化配置（rc / PATH / 代理变量）、可选网络探测；
并按 --profile 给的期望清单给出缺失项与按平台的安装命令建议。

纯标准库实现。

示例：
    python env_audit.py --check-persist --out env-report.md
    python env_audit.py --profile expected.json --json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys

EXIT_OK = 0
EXIT_MISSING_REQUIRED = 1
EXIT_BAD_INPUT = 2

# 工具清单：名称 -> 用于取版本的参数
TOOLS: dict[str, list[str]] = {
    "python3": ["--version"], "python": ["--version"], "pip": ["--version"], "pip3": ["--version"],
    "git": ["--version"], "node": ["--version"], "npm": ["--version"], "pnpm": ["--version"],
    "yarn": ["--version"], "go": ["version"], "rustc": ["--version"], "cargo": ["--version"],
    "gcc": ["--version"], "clang": ["--version"], "make": ["--version"], "cmake": ["--version"],
    "docker": ["--version"], "docker-compose": ["--version"], "kubectl": ["version", "--client"],
    "nmap": ["--version"], "curl": ["--version"], "wget": ["--version"], "jq": ["--version"],
    "rg": ["--version"], "7z": [], "sqlite3": ["--version"], "java": ["-version"],
    "code": ["--version"], "pwsh": ["--version"], "powershell": ["-Command", "$PSVersionTable.PSVersion.ToString()"],
    "bash": ["--version"], "zsh": ["--version"], "vim": ["--version"], "nano": ["--version"],
    "tmux": ["-V"], "ssh": ["-V"], "openssl": ["version"], "gdb": ["--version"],
    "strace": ["-V"], "tcpdump": ["--version"], "winget": ["--version"], "choco": ["--version"],
    "scoop": ["--version"], "apt": ["--version"], "dnf": ["--version"], "pacman": ["--version"],
    "brew": ["--version"], "idapyswitch": ["--help"], "gh": ["--version"],
}

# 缺失时的安装命令建议：工具 -> {包管理器: 包名}
INSTALL_HINTS: dict[str, dict[str, str]] = {
    "git": {"winget": "Git.Git", "apt": "git", "pacman": "git", "brew": "git"},
    "python3": {"apt": "python3", "pacman": "python", "brew": "python@3.12", "winget": "Python.Python.3.12"},
    "node": {"winget": "OpenJS.NodeJS.LTS", "apt": "nodejs", "pacman": "nodejs", "brew": "node"},
    "pnpm": {"winget": "pnpm.pnpm", "brew": "pnpm"},
    "go": {"winget": "GoLang.Go", "apt": "golang-go", "pacman": "go", "brew": "go"},
    "rustc": {"winget": "Rustlang.Rustup", "apt": "rustc", "pacman": "rust", "brew": "rustup"},
    "docker": {"winget": "Docker.DockerDesktop", "apt": "docker.io", "pacman": "docker", "brew": "docker"},
    "nmap": {"winget": "Insecure.Nmap", "apt": "nmap", "pacman": "nmap", "brew": "nmap"},
    "jq": {"winget": "jqlang.jq", "apt": "jq", "pacman": "jq", "brew": "jq"},
    "rg": {"winget": "BurntSushi.ripgrep.MSVC", "apt": "ripgrep", "pacman": "ripgrep", "brew": "ripgrep"},
    "sqlite3": {"winget": "SQLite.SQLite", "apt": "sqlite3", "pacman": "sqlite", "brew": "sqlite"},
    "cmake": {"winget": "Kitware.CMake", "apt": "cmake", "pacman": "cmake", "brew": "cmake"},
    "pwsh": {"winget": "Microsoft.PowerShell", "apt": "powershell", "brew": "powershell"},
    "tmux": {"apt": "tmux", "pacman": "tmux", "brew": "tmux"},
    "tcpdump": {"apt": "tcpdump", "pacman": "tcpdump", "brew": "tcpdump"},
    "gdb": {"apt": "gdb", "pacman": "gdb", "brew": "gdb"},
    "openssl": {"apt": "openssl", "pacman": "openssl", "brew": "openssl"},
}


def run_cmd(args: list[str], timeout: int = 3) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, errors="replace")
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    out = (proc.stdout or "") + (proc.stderr or "")
    return out.strip().splitlines()[0][:80] if out.strip() else ""


def system_info() -> dict:
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "python_exe": sys.executable,
        "shell": os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown")),
        "is_admin": False,
        "is_wsl": False,
        "is_container": False,
        "hostname": platform.node(),
    }
    # 管理员 / root
    if os.name == "nt":
        try:
            import ctypes
            info["is_admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:
            info["is_admin"] = False
    else:
        info["is_admin"] = (os.geteuid() == 0) if hasattr(os, "geteuid") else False
    # WSL / 容器
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="replace") as fh:
            if "microsoft" in fh.read().lower():
                info["is_wsl"] = True
    except OSError:
        pass
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
            if "docker" in text or "kubepods" in text or "containerd" in text:
                info["is_container"] = True
    except OSError:
        pass
    if os.path.exists("/.dockerenv"):
        info["is_container"] = True
    return info


def probe_tools(names: list[str]) -> list[dict]:
    results: list[dict] = []
    for name in names:
        path = shutil.which(name)
        record = {"name": name, "present": bool(path), "path": path or "", "version": ""}
        if path:
            args = TOOLS.get(name)
            if args is None:
                args = ["--version"]
            if args:
                record["version"] = run_cmd([path, *args])
            if not record["version"]:
                record["version"] = "(无版本输出)"
        results.append(record)
    return results


def package_manager(info: dict) -> str:
    if info["os"] == "Windows":
        for pm in ("winget", "scoop", "choco"):
            if shutil.which(pm):
                return pm
        return "winget"
    if shutil.which("apt"):
        return "apt"
    if shutil.which("dnf"):
        return "dnf"
    if shutil.which("pacman"):
        return "pacman"
    if shutil.which("brew"):
        return "brew"
    return "unknown"


def install_command(tool: str, pm: str) -> str:
    hints = INSTALL_HINTS.get(tool, {})
    pkg = hints.get(pm) or hints.get("apt") or tool
    if pm == "winget":
        return f"winget install --id {pkg} -e"
    if pm == "scoop":
        return f"scoop install {pkg}"
    if pm == "choco":
        return f"choco install {pkg} -y"
    if pm in ("apt",):
        return f"sudo apt update && sudo apt install -y {pkg}"
    if pm == "dnf":
        return f"sudo dnf install -y {pkg}"
    if pm == "pacman":
        return f"sudo pacman -S --noconfirm {pkg}"
    if pm == "brew":
        return f"brew install {pkg}"
    return f"# 请手动安装 {tool}"


def persist_info() -> dict:
    """检查 shell 持久化配置与环境变量来源。"""
    result: dict = {"rc_files": [], "proxy_vars": {}, "path_entries": []}
    home = os.path.expanduser("~")
    candidates = [".bashrc", ".bash_profile", ".profile", ".zshrc", ".zprofile", ".config/fish/config.fish"]
    if os.name == "nt":
        candidates += ["Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1",
                       "Documents/PowerShell/Microsoft.PowerShell_profile.ps1"]
    for rel in candidates:
        path = os.path.join(home, *rel.split("/"))
        entry = {"file": rel, "exists": os.path.exists(path), "bytes": 0, "path_lines": 0, "alias_lines": 0}
        if entry["exists"]:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                text = ""
            entry["bytes"] = len(text.encode("utf-8"))
            entry["path_lines"] = len(re.findall(r"(?im)^\s*(export\s+PATH=|PATH\s*=|\$env:PATH)", text))
            entry["alias_lines"] = len(re.findall(r"(?im)^\s*(alias\s|function\s|Set-Alias)", text))
        result["rc_files"].append(entry)

    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY", "ALL_PROXY"):
        value = os.environ.get(var)
        if value:
            result["proxy_vars"][var] = value

    path_value = os.environ.get("PATH", "")
    sep = ";" if os.name == "nt" else ":"
    entries = [p for p in path_value.split(sep) if p]
    seen: dict[str, int] = {}
    for p in entries:
        seen[p.lower() if os.name == "nt" else p] = seen.get(p.lower() if os.name == "nt" else p, 0) + 1
    result["path_entries"] = entries
    result["path_duplicates"] = sorted([k for k, v in seen.items() if v > 1])
    result["path_missing_dirs"] = [p for p in entries if not os.path.isdir(p)][:10]
    return result


def net_probe(target: str) -> dict:
    host, _, port_text = target.partition(":")
    try:
        port = int(port_text) if port_text else 443
    except ValueError:
        return {"target": target, "ok": False, "error": "端口不是数字"}
    import time
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=2):
            elapsed = (time.perf_counter() - start) * 1000
        return {"target": target, "ok": True, "ms": round(elapsed, 1), "error": ""}
    except OSError as exc:
        return {"target": target, "ok": False, "ms": None, "error": str(exc)}


def render_markdown(report: dict, profile_result: dict | None) -> str:
    info = report["system"]
    lines = ["# 环境审计报告", "",
             "## 系统与身份", "",
             "| 项 | 值 |", "|---|---|",
             f"| 操作系统 | {info['os']} {info['os_release']} |",
             f"| 架构 | {info['arch']} |",
             f"| 主机名 | {info['hostname']} |",
             f"| Python | {info['python']}（{info['python_exe']}） |",
             f"| Shell | {info['shell']} |",
             f"| 管理员/root | {'是' if info['is_admin'] else '否'} |",
             f"| WSL | {'是' if info['is_wsl'] else '否'} |",
             f"| 容器 | {'是' if info['is_container'] else '否'} |",
             f"| 包管理器 | {report['package_manager']} |", "",
             "## 工具链", "",
             "| 工具 | 状态 | 版本 | 路径 |", "|---|---|---|---|"]
    present = [t for t in report["tools"] if t["present"]]
    for t in report["tools"]:
        lines.append(f"| {t['name']} | {'✅' if t['present'] else '❌'} | {t['version'] or '-'} | {t['path'] or '-'} |")
    lines.append("")
    lines.append(f"存在 {len(present)} / {len(report['tools'])} 项。")
    lines.append("")

    persist = report.get("persist")
    if persist:
        lines += ["## 持久化配置", "", "| 文件 | 存在 | 字节 | PATH 行 | 别名/函数行 |", "|---|---|---|---|---|"]
        for rc in persist["rc_files"]:
            lines.append(f"| {rc['file']} | {'✅' if rc['exists'] else '❌'} | {rc['bytes']} | "
                         f"{rc['path_lines']} | {rc['alias_lines']} |")
        lines.append("")
        lines.append(f"- PATH 条目数：{len(persist['path_entries'])}")
        if persist["path_duplicates"]:
            lines.append(f"- PATH 重复项：{', '.join(persist['path_duplicates'])}")
        if persist["path_missing_dirs"]:
            lines.append(f"- PATH 中不存在的目录：{', '.join(persist['path_missing_dirs'])}")
        if persist["proxy_vars"]:
            lines.append("- 代理变量：" + "，".join(f"{k}={v}" for k, v in persist["proxy_vars"].items()))
        else:
            lines.append("- 代理变量：未设置")
        lines.append("")

    net = report.get("net")
    if net:
        lines += ["## 网络探测", "",
                  f"- 目标 {net['target']}：{'可达 %.1f ms' % net['ms'] if net['ok'] else '不可达（' + net['error'] + '）'}", ""]

    if profile_result is not None:
        lines += ["## 期望清单比对", "",
                  f"- 必装缺失：{', '.join(profile_result['missing_required']) or '无'}",
                  f"- 选装缺失：{', '.join(profile_result['missing_optional']) or '无'}", ""]
        if profile_result["install_commands"]:
            lines += ["安装建议：", "", "```bash"]
            lines += profile_result["install_commands"]
            lines += ["```", ""]

    lines += ["## 结论", "",
              f"- 缺失 P0 工具（阻断工作流）：{', '.join(profile_result['missing_required']) if profile_result else '未提供期望清单'}",
              "- 建议动作：先补 P0 工具，再处理 PATH 重复项与失效目录。", ""]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="env_audit.py",
        description="跨平台环境审计：系统信息 / 工具链 / 持久化配置 / 网络探测 / 期望清单比对。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python env_audit.py --check-persist --profile expected.json --out env-report.md",
    )
    p.add_argument("--json", action="store_true", help="输出 JSON 而不是 Markdown")
    p.add_argument("--out", metavar="文件路径", help="把报告写入文件（默认打印到 stdout）")
    p.add_argument("--profile", metavar="JSON路径", help="期望工具清单 JSON，形如 {\"required\": [\"git\"], \"optional\": [\"docker\"]}")
    p.add_argument("--check-persist", action="store_true", help="检查 shell 持久化配置与 PATH 健康度")
    p.add_argument("--check-net", action="store_true", help="做一次 TCP 连通性探测")
    p.add_argument("--net-target", default="github.com:443", help="探测目标 host:port，默认 github.com:443")
    p.add_argument("--quiet", action="store_true", help="不打印摘要（配合 --out 使用）")
    return p


def load_profile(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("profile 根节点必须是对象")
    required = data.get("required", [])
    optional = data.get("optional", [])
    if not isinstance(required, list) or not isinstance(optional, list):
        raise ValueError("required / optional 必须是数组")
    return {"required": [str(x) for x in required], "optional": [str(x) for x in optional]}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report: dict = {
        "system": system_info(),
        "tools": [],
        "package_manager": "",
    }
    report["package_manager"] = package_manager(report["system"])
    report["tools"] = probe_tools(sorted(TOOLS.keys()))

    if args.check_persist:
        report["persist"] = persist_info()
    if args.check_net:
        report["net"] = net_probe(args.net_target)

    profile_result = None
    if args.profile:
        if not os.path.isfile(args.profile):
            print(f"参数错误：profile 文件不存在 {args.profile}", file=sys.stderr)
            return EXIT_BAD_INPUT
        try:
            profile = load_profile(args.profile)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"参数错误：无法解析 profile（{exc}）", file=sys.stderr)
            return EXIT_BAD_INPUT
        present = {t["name"] for t in report["tools"] if t["present"]}
        missing_required = [t for t in profile["required"] if t not in present]
        missing_optional = [t for t in profile["optional"] if t not in present]
        pm = report["package_manager"]
        profile_result = {
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "install_commands": [install_command(t, pm) for t in missing_required + missing_optional],
        }

    report["profile"] = profile_result
    text = json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_markdown(report, profile_result)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            print(f"写入失败：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        if not args.quiet:
            present = sum(1 for t in report["tools"] if t["present"])
            print(f"工具链 {present}/{len(report['tools'])} 项存在，报告已写入：{args.out}")
    else:
        print(text)

    if profile_result and profile_result["missing_required"]:
        return EXIT_MISSING_REQUIRED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
