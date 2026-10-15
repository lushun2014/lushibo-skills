#!/usr/bin/env python3
"""GitHub 仓库工程化审计（repo audit）。

扫描本地仓库目录，对 10 项工程化指标打分（总分 100），输出逐项证据与修复清单。

检查项：
    G-01 README  G-02 LICENSE  G-03 .gitignore  G-04 CI  G-05 测试
    G-06 依赖锁定  G-07 提交规范  G-08 issue/PR 模板  G-09 文档面  G-10 元数据

纯标准库实现。

示例：
    python repo_audit.py . --out repo-audit.md
    python repo_audit.py . --json --min-score 60
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

EXIT_OK = 0
EXIT_BELOW_MIN = 1
EXIT_BAD_INPUT = 2

CONVENTIONAL = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")

LANG_IGNORES = {
    "python": ["__pycache__", "*.pyc", ".venv", "venv", "dist", "build", ".pytest_cache", ".mypy_cache"],
    "node": ["node_modules", "dist", "build", ".next", "coverage"],
    "go": ["bin", "vendor", "*.test"],
    "rust": ["target"],
}

TEST_PATTERNS = [
    re.compile(r"^tests?/"),
    re.compile(r"(^|/)test_.*\.py$"),
    re.compile(r"(^|/).*_test\.go$"),
    re.compile(r"(^|/).*\.(test|spec)\.(js|ts|jsx|tsx)$"),
    re.compile(r"(^|/)tests?\.rs$"),
    re.compile(r"^spec/"),
]

LOCK_FILES = ["requirements.txt", "poetry.lock", "uv.lock", "pyproject.toml", "package-lock.json",
              "pnpm-lock.yaml", "yarn.lock", "go.sum", "Cargo.lock", "Gemfile.lock"]

LICENSE_HINTS = {
    "MIT": ["MIT License", "Permission is hereby granted, free of charge"],
    "Apache-2.0": ["Apache License", "Version 2.0, January 2004"],
    "GPL-3.0": ["GNU GENERAL PUBLIC LICENSE", "Version 3"],
    "BSD-3-Clause": ["BSD 3-Clause", "Redistribution and use in source and binary forms"],
    "MPL-2.0": ["Mozilla Public License Version 2.0"],
}


def read_text(path: str, limit: int = 200_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def walk_files(root: str, max_files: int = 5000) -> list[str]:
    out: list[str] = []
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "target", "dist", "build", ".idea", ".vscode"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            out.append(rel)
            if len(out) >= max_files:
                return out
    return out


def detect_language(files: list[str]) -> str:
    exts = {".py": "python", ".js": "node", ".ts": "node", ".jsx": "node", ".tsx": "node",
            ".go": "go", ".rs": "rust"}
    counts: dict[str, int] = {}
    for f in files:
        lang = exts.get(os.path.splitext(f)[1])
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "unknown"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def run_git(root: str, args: list[str], timeout: int = 10) -> str:
    try:
        proc = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True,
                              timeout=timeout, errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout


def check_readme(root: str, files: list[str]) -> tuple[float, str, str]:
    name = next((f for f in files if f.lower() == "readme.md"), None) or \
           next((f for f in files if f.lower().startswith("readme")), None)
    if not name:
        return 0.0, "未找到 README", "创建 README.md：定位 + 安装 + 最小示例 + 许可证"
    text = read_text(os.path.join(root, name))
    size = len(text.encode("utf-8"))
    score = 0.4 if size > 200 else 0.1
    if size > 500:
        score = 0.7
    sections = sum(1 for kw in ("install", "usage", "quick start", "快速开始", "安装", "使用", "license", "许可")
                   if kw in text.lower())
    if sections >= 3:
        score = 1.0
    return score, f"{name}（{size} 字节，命中 {sections} 个关键小节）", "补齐「安装 / 使用 / 许可证」小节并给出可复制命令"


def check_license(root: str, files: list[str]) -> tuple[float, str, str]:
    name = next((f for f in files if f.lower().startswith("license") or f.lower().startswith("copying")), None)
    if not name:
        return 0.0, "未找到 LICENSE", "添加 LICENSE（MIT/Apache-2.0 等）并写入完整许可证正文"
    text = read_text(os.path.join(root, name))
    for lic, hints in LICENSE_HINTS.items():
        if any(h in text for h in hints):
            return 1.0, f"{name} → {lic}", "已具备"
    return 0.5, f"{name}（无法识别许可证类型）", "确认许可证正文完整且类型明确"


def check_gitignore(root: str, files: list[str], lang: str) -> tuple[float, str, str]:
    name = ".gitignore" if ".gitignore" in files else next((f for f in files if f.endswith(".gitignore")), None)
    if not name:
        return 0.0, "未找到 .gitignore", "创建 .gitignore 并覆盖语言常见产物"
    text = read_text(os.path.join(root, name))
    expected = LANG_IGNORES.get(lang, [])
    if not expected:
        return 0.7, f"{name}（语言未识别，未做覆盖度校验）", "按语言补充忽略规则"
    hit = [p for p in expected if p.replace("*", "") in text]
    score = min(1.0, 0.3 + 0.7 * (len(hit) / len(expected)))
    missing = [p for p in expected if p not in hit]
    fix = "补充忽略：" + ", ".join(missing) if missing else "已具备"
    return score, f"{name}（{lang} 覆盖 {len(hit)}/{len(expected)}）", fix


def check_ci(root: str, files: list[str]) -> tuple[float, str, str]:
    wf = [f for f in files if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))]
    if not wf:
        return 0.0, "未找到 .github/workflows/*.yml", "添加 CI 工作流：lint → test → build"
    text = "".join(read_text(os.path.join(root, f)) for f in wf)
    score = 0.5
    hits = []
    for kw in ("test", "lint", "build"):
        if kw in text.lower():
            hits.append(kw)
    if len(hits) >= 2:
        score = 0.8
    if "matrix" in text:
        score = 1.0
    return score, f"{len(wf)} 个工作流，命中步骤 {', '.join(hits) or '无'}", "补齐 lint/test/build 步骤并加版本矩阵"


def check_tests(files: list[str]) -> tuple[float, str, str]:
    hits = [f for f in files if any(p.search(f) for p in TEST_PATTERNS)]
    if not hits:
        return 0.0, "未找到测试文件", "创建 tests/ 目录并至少补 1 个真实可跑的用例"
    if len(hits) >= 3:
        return 1.0, f"{len(hits)} 个测试文件", "已具备"
    return 0.6, f"{len(hits)} 个测试文件", "补充边界与错误路径用例"


def check_lock(root: str, files: list[str]) -> tuple[float, str, str]:
    present = [f for f in LOCK_FILES if f in files]
    if not present:
        return 0.0, "未找到依赖锁定文件", "生成并提交锁定文件（requirements/lock/Cargo.lock/go.sum）"
    strict = [f for f in present if f not in ("pyproject.toml",)]
    return (1.0 if strict else 0.5), f"锁定文件：{', '.join(present)}", \
        "已具备" if strict else "补充真正的锁文件（如 requirements.txt 或 uv.lock）"


def check_commits(root: str) -> tuple[float, str, str]:
    log = run_git(root, ["log", "--pretty=%s", "-n", "200"])
    if not log.strip():
        return 0.5, "无法读取 git 历史（非仓库或 git 不可用）", "在 git 仓库内运行，或确认已初始化"
    subjects = [s for s in log.splitlines() if s.strip()]
    if not subjects:
        return 0.5, "提交历史为空", "至少完成一次规范提交"
    ok = sum(1 for s in subjects if any(s.startswith(p + ":") or s.startswith(p + "(") for p in CONVENTIONAL))
    ratio = ok / len(subjects)
    score = min(1.0, ratio * 1.25)
    return score, f"最近 {len(subjects)} 条提交中 {ok} 条符合 Conventional Commits（{ratio:.0%}）", \
        "统一提交前缀：feat/fix/docs/refactor/test/chore"


def check_templates(files: list[str]) -> tuple[float, str, str]:
    has_issue = any(f.startswith(".github/ISSUE_TEMPLATE/") for f in files) or \
                any(f.lower().startswith(".github/issue_template") for f in files)
    has_pr = any("pull_request_template" in f.lower() for f in files)
    score = (0.6 if has_issue else 0.0) + (0.4 if has_pr else 0.0)
    detail = f"issue 模板 {'有' if has_issue else '无'}，PR 模板 {'有' if has_pr else '无'}"
    return score, detail, "添加 .github/ISSUE_TEMPLATE/ 与 PULL_REQUEST_TEMPLATE.md"


def check_docs(files: list[str]) -> tuple[float, str, str]:
    checks = {
        "docs 目录": any(f.startswith("docs/") for f in files),
        "CHANGELOG": any(f.lower().startswith("changelog") for f in files),
        "CONTRIBUTING": any(f.lower().startswith("contributing") for f in files),
        "CODE_OF_CONDUCT": any("code_of_conduct" in f.lower() for f in files),
        "SECURITY": any(f.lower().startswith("security") for f in files),
    }
    hit = [k for k, v in checks.items() if v]
    return len(hit) / len(checks), f"命中 {len(hit)}/{len(checks)}：{', '.join(hit) or '无'}", \
        "补齐缺失文档：" + ", ".join(k for k, v in checks.items() if not v)


def check_metadata(root: str, files: list[str]) -> tuple[float, str, str]:
    score = 0.0
    detail: list[str] = []
    pkg_json = os.path.join(root, "package.json")
    pyproject = os.path.join(root, "pyproject.toml")
    cargo = os.path.join(root, "Cargo.toml")
    if os.path.isfile(pkg_json):
        try:
            data = json.loads(read_text(pkg_json))
        except json.JSONDecodeError:
            data = {}
        if data.get("description"):
            score += 0.4
            detail.append("package.json 有 description")
        if data.get("repository") or data.get("homepage"):
            score += 0.3
            detail.append("有 repository/homepage")
        if data.get("license"):
            score += 0.3
            detail.append("有 license 字段")
    elif os.path.isfile(pyproject):
        text = read_text(pyproject)
        if re.search(r"^description\s*=", text, re.M):
            score += 0.4
            detail.append("pyproject 有 description")
        if re.search(r"^license\s*=", text, re.M):
            score += 0.3
            detail.append("pyproject 有 license")
        if "classifiers" in text or "urls" in text:
            score += 0.3
            detail.append("有 classifiers/urls")
    elif os.path.isfile(cargo):
        text = read_text(cargo)
        if re.search(r"^description\s*=", text, re.M):
            score += 0.4
            detail.append("Cargo.toml 有 description")
        if re.search(r"^license\s*=", text, re.M):
            score += 0.3
            detail.append("Cargo.toml 有 license")
        if re.search(r"^repository\s*=", text, re.M):
            score += 0.3
            detail.append("有 repository")
    else:
        return 0.3, "未找到包元数据文件（package.json/pyproject.toml/Cargo.toml）", \
            "添加包元数据：description / license / repository"
    return min(1.0, score), "；".join(detail) or "元数据不完整", "补齐 description / license / repository 字段"


WEIGHTS = {
    "G-01 README": 12, "G-02 LICENSE": 10, "G-03 .gitignore": 8, "G-04 CI": 15, "G-05 测试": 15,
    "G-06 依赖锁定": 8, "G-07 提交规范": 10, "G-08 issue/PR 模板": 6, "G-09 文档面": 8, "G-10 元数据": 8,
}


def grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def audit(root: str) -> dict:
    files = walk_files(root)
    lang = detect_language(files)
    checks = [
        ("G-01 README", *check_readme(root, files)),
        ("G-02 LICENSE", *check_license(root, files)),
        ("G-03 .gitignore", *check_gitignore(root, files, lang)),
        ("G-04 CI", *check_ci(root, files)),
        ("G-05 测试", *check_tests(files)),
        ("G-06 依赖锁定", *check_lock(root, files)),
        ("G-07 提交规范", *check_commits(root)),
        ("G-08 issue/PR 模板", *check_templates(files)),
        ("G-09 文档面", *check_docs(files)),
        ("G-10 元数据", *check_metadata(root, files)),
    ]
    items = []
    total = 0.0
    for name, frac, evidence, fix in checks:
        weight = WEIGHTS[name]
        points = round(weight * frac, 2)
        total += points
        items.append({"item": name, "weight": weight, "ratio": round(frac, 3),
                      "points": points, "evidence": evidence, "fix": fix})
    total = round(total, 2)
    return {"root": os.path.abspath(root), "language": lang, "files_scanned": len(files),
            "score": total, "grade": grade(total), "items": items}


def render_markdown(report: dict, with_fix: bool) -> str:
    lines = ["# 仓库工程化审计报告", "",
             f"- 仓库：{report['root']}",
             f"- 主语言：{report['language']}",
             f"- 扫描文件数：{report['files_scanned']}",
             f"- 总分：{report['score']} / 100（等级 {report['grade']}）", "",
             "## 逐项结果", "",
             "| 检查项 | 权重 | 得分 | 状态 | 证据 | 修复建议 |",
             "|---|---|---|---|---|---|"]
    for it in report["items"]:
        status = "✅" if it["ratio"] >= 0.9 else ("🟡" if it["ratio"] >= 0.5 else "❌")
        lines.append(f"| {it['item']} | {it['weight']} | {it['points']} | {status} | {it['evidence']} | {it['fix']} |")
    lines.append("")
    lines.append("## Top 5 优先修复")
    lines.append("")
    ranked = sorted(report["items"], key=lambda x: x["weight"] * (1 - x["ratio"]), reverse=True)
    for idx, it in enumerate(ranked[:5], start=1):
        gap = round(it["weight"] * (1 - it["ratio"]), 2)
        lines.append(f"{idx}. {it['item']}（可提升 {gap} 分）— {it['fix']}")
    lines.append("")
    if with_fix:
        lines.append("## 可执行修复片段")
        lines.append("")
        lines.append("```bash")
        lines.append("# 补齐基础文件（按需修改许可证与项目名）")
        lines.append("printf '# 项目名\\n\\n一句话定位。\\n\\n## 安装\\n\\n```bash\\n<安装命令>\\n```\\n\\n## 使用\\n\\n```bash\\n<示例命令>\\n```\\n\\n## 许可证\\nMIT\\n' > README.md")
        lines.append("mkdir -p .github/workflows tests docs")
        lines.append("git commit -m 'chore: bootstrap repo scaffolding'")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="repo_audit.py",
        description="GitHub 仓库工程化审计：10 项指标打分 + 修复清单。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python repo_audit.py . --out repo-audit.md --fix",
    )
    p.add_argument("path", nargs="?", default=".", help="仓库路径，默认当前目录")
    p.add_argument("--json", action="store_true", help="输出 JSON 而不是 Markdown")
    p.add_argument("--out", metavar="文件路径", help="把报告写入文件（默认打印到 stdout）")
    p.add_argument("--min-score", type=float, default=0.0, help="低于该分数时退出码为 1，默认 0（不因分数失败）")
    p.add_argument("--fix", action="store_true", help="输出可执行修复命令片段（只打印，不执行）")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not os.path.isdir(args.path):
        print(f"参数错误：目录不存在 {args.path}", file=sys.stderr)
        return EXIT_BAD_INPUT
    if not (0.0 <= args.min_score <= 100.0):
        print("参数错误：--min-score 必须在 0-100 之间", file=sys.stderr)
        return EXIT_BAD_INPUT

    report = audit(args.path)
    text = json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_markdown(report, args.fix)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            print(f"写入失败：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        print(f"总分 {report['score']} / 100（等级 {report['grade']}），报告已写入：{args.out}")
    else:
        print(text)

    return EXIT_BELOW_MIN if report["score"] < args.min_score else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
