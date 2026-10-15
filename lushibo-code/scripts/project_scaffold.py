#!/usr/bin/env python3
"""多语言工程骨架生成器 + 代码度量（project scaffold & metrics）。

子命令：
    scaffold  生成 Python / Node / Go / Rust 工程骨架（含测试与 CI）
    metrics   统计文件行数、函数长度、复杂度近似、重复文件、热点文件

纯标准库实现。模板内联，不依赖外部文件。

示例：
    python project_scaffold.py scaffold --lang python --name myproj --ci github --license mit
    python project_scaffold.py metrics ./src --json --out metrics.md
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

EXIT_OK = 0
EXIT_CONFLICT = 1
EXIT_BAD_INPUT = 2

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
HOT_FILE_LINES = 500
LONG_FUNC_LINES = 80
HIGH_COMPLEXITY = 15

LANG_EXTS = {
    "python": {".py"},
    "node": {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"},
    "go": {".go"},
    "rust": {".rs"},
    "other": {".c", ".h", ".cpp", ".hpp", ".java", ".rb", ".php", ".cs", ".sh", ".ps1", ".sql"},
}

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
BRANCH_RE = re.compile(r"\b(if|elif|else if|for|while|case|catch|except|&&|\|\||\?)\b")

MIT_LICENSE = """MIT License

Copyright (c) 2026 __NAME__ contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

APACHE_LICENSE = """                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   Copyright 2026 __NAME__ contributors
"""

GITIGNORE = {
    "python": "__pycache__/\n*.py[cod]\n.venv/\nvenv/\ndist/\nbuild/\n*.egg-info/\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n",
    "node": "node_modules/\ndist/\nbuild/\ncoverage/\n*.log\n.env\n",
    "go": "bin/\n*.test\n*.out\nvendor/\n",
    "rust": "target/\n**/*.rs.bk\n",
}

README = """# __NAME__

__NAME__ 的工程骨架：安装、运行、测试、发布。

## 安装

```bash
__INSTALL__
```

## 使用

```bash
__RUN__
```

## 测试

```bash
__TEST__
```

## 目录结构

```
__TREE__
```

## 许可证

__LICENSE__
"""

PY_CORE = '''"""__NAME__ 核心逻辑：纯函数，无 IO，便于测试。"""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """返回两数之和。"""
    return a + b


def parse_int(raw: str, default: int = 0) -> int:
    """把字符串解析成整数，失败时返回默认值。"""
    try:
        return int(str(raw).strip(), 0)
    except (TypeError, ValueError):
        return default
'''

PY_TEST = '''from __name_pkg__.core import add, parse_int


def test_add_positive():
    assert add(1, 2) == 3


def test_parse_int_hex():
    assert parse_int("0x10") == 16


def test_parse_int_invalid_returns_default():
    assert parse_int("nope", default=-1) == -1
'''

PY_PROJECT = '''[project]
name = "__NAME__"
version = "0.1.0"
description = "__NAME__ 项目"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "mypy"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
addopts = "-q --strict-markers"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.10"
warn_unused_ignores = true
'''

PY_MAKEFILE = """.PHONY: install lint fmt type test build all

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .

fmt:
	ruff format .

type:
	mypy src

test:
	pytest --cov=src --cov-report=term-missing --cov-branch

build:
	python -m build

all: lint type test build
"""

NODE_INDEX = '''export function add(a, b) {
  return a + b;
}

export function parseNumber(raw, fallback = 0) {
  const value = Number(String(raw).trim());
  return Number.isFinite(value) ? value : fallback;
}
'''

NODE_TEST = '''import { describe, expect, it } from "vitest";
import { add, parseNumber } from "../src/index.js";

describe("core", () => {
  it("adds numbers", () => {
    expect(add(1, 2)).toBe(3);
  });

  it("falls back on invalid input", () => {
    expect(parseNumber("nope", -1)).toBe(-1);
  });
});
'''

NODE_PKG = '''{
  "name": "__NAME__",
  "version": "0.1.0",
  "description": "__NAME__ 项目",
  "type": "module",
  "main": "src/index.js",
  "scripts": {
    "lint": "eslint .",
    "test": "vitest run",
    "build": "echo build-ok"
  },
  "devDependencies": {
    "eslint": "^9.0.0",
    "vitest": "^2.0.0"
  },
  "license": "MIT"
}
'''

GO_CORE = '''// Package __PKG__ 提供核心纯函数。
package __PKG__

import "strconv"

// Add 返回两数之和。
func Add(a, b int) int {
	return a + b
}

// ParseInt 解析整数，失败时返回默认值。
func ParseInt(raw string, def int) int {
	v, err := strconv.Atoi(raw)
	if err != nil {
		return def
	}
	return v
}
'''

GO_TEST = '''package __PKG__

import "testing"

func TestAdd(t *testing.T) {
	if got := Add(1, 2); got != 3 {
		t.Fatalf("Add(1,2)=%d, want 3", got)
	}
}

func TestParseIntFallback(t *testing.T) {
	if got := ParseInt("nope", -1); got != -1 {
		t.Fatalf("ParseInt fallback=%d, want -1", got)
	}
}
'''

GO_MAIN = '''package main

import (
	"fmt"

	"__MODULE__/internal/__PKG__"
)

func main() {
	fmt.Println(__PKG__.Add(1, 2))
}
'''

GO_MOD = '''module __MODULE__

go 1.22
'''

GO_MAKEFILE = """.PHONY: fmt lint test build all

fmt:
	gofmt -w .

lint:
	go vet ./...

test:
	go test -race ./...

build:
	go build -o bin/__NAME__ ./cmd/__NAME__

all: fmt lint test build
"""

RUST_LIB = '''//! __NAME__ 核心库。

/// 返回两数之和。
pub fn add(a: i64, b: i64) -> i64 {
    a + b
}

/// 解析整数，失败时返回默认值。
pub fn parse_int(raw: &str, default: i64) -> i64 {
    raw.trim().parse::<i64>().unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_works() {
        assert_eq!(add(1, 2), 3);
    }

    #[test]
    fn parse_int_falls_back() {
        assert_eq!(parse_int("nope", -1), -1);
    }
}
'''

RUST_MAIN = '''fn main() {
    println!("{}", __CRATE__::add(1, 2));
}
'''

RUST_CARGO = '''[package]
name = "__NAME__"
version = "0.1.0"
edition = "2021"
description = "__NAME__ 项目"
license = "MIT"

[dependencies]
'''

CI_PY = '''name: ci
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest -q
'''

CI_NODE = '''name: ci
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node-version: [18, 20, 22]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm install
      - run: npm run lint
      - run: npm test
'''

CI_GO = '''name: ci
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
          cache: true
      - run: gofmt -l .
      - run: go vet ./...
      - run: go test -race ./...
'''

CI_RUST = '''name: ci
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy
      - run: cargo fmt --check
      - run: cargo clippy -- -D warnings
      - run: cargo test
'''

CI_GITLAB = '''stages: [test]

test:
  stage: test
  image: __IMAGE__
  script:
    - __CMD__
'''


def render(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace(key, value)
    return out


def package_identifier(name: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if ident and ident[0].isdigit():
        ident = "_" + ident
    return ident


def build_tree(lang: str, name: str, test_framework: str, ci: str, license_id: str) -> dict[str, str]:
    """返回 {相对路径: 内容}。"""
    pkg = package_identifier(name)
    files: dict[str, str] = {}
    mapping = {"__NAME__": name, "__PKG__": pkg, "__MODULE__": name.lower().replace("-", "")}

    if lang == "python":
        files[f"src/{pkg}/__init__.py"] = f'"""{name} 包。"""\n\n__all__ = ["core"]\n'
        files[f"src/{pkg}/core.py"] = render(PY_CORE, mapping)
        test_body = PY_TEST.replace("__name_pkg__", pkg)
        if test_framework == "unittest":
            test_body = (
                "import unittest\n\n"
                f"from {pkg}.core import add, parse_int\n\n\n"
                "class CoreTest(unittest.TestCase):\n"
                "    def test_add(self):\n"
                "        self.assertEqual(add(1, 2), 3)\n\n"
                "    def test_parse_int_invalid(self):\n"
                "        self.assertEqual(parse_int('nope', default=-1), -1)\n\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )
        files["tests/test_core.py"] = test_body
        files["pyproject.toml"] = render(PY_PROJECT, mapping)
        files["Makefile"] = PY_MAKEFILE
        files["README.md"] = render(README, {
            **mapping,
            "__INSTALL__": "python -m venv .venv && . .venv/bin/activate && pip install -e \".[dev]\"",
            "__RUN__": f"python -c \"from {pkg}.core import add; print(add(1, 2))\"",
            "__TEST__": "pytest" if test_framework == "pytest" else "python -m unittest discover -s tests",
            "__TREE__": f"src/{pkg}/\ntests/\npyproject.toml\nMakefile",
            "__LICENSE__": license_id.upper() if license_id != "none" else "未指定",
        })
        ci_file, ci_image, ci_cmd = CI_PY, "", ""
        ci_path = ".github/workflows/ci.yml"

    elif lang == "node":
        files["src/index.js"] = NODE_INDEX
        test_body = NODE_TEST
        if test_framework == "jest":
            test_body = test_body.replace('from "vitest"', 'from "@jest/globals"')
        files["tests/index.test.js"] = test_body
        files["package.json"] = render(NODE_PKG, mapping)
        files["README.md"] = render(README, {
            **mapping,
            "__INSTALL__": "npm install",
            "__RUN__": "node -e \"import('./src/index.js').then(m => console.log(m.add(1,2)))\"",
            "__TEST__": "npm test",
            "__TREE__": "src/\ntests/\npackage.json",
            "__LICENSE__": license_id.upper() if license_id != "none" else "未指定",
        })
        ci_file, ci_image, ci_cmd = CI_NODE, "node:20", "npm install && npm test"
        ci_path = ".github/workflows/ci.yml"

    elif lang == "go":
        files["go.mod"] = render(GO_MOD, mapping)
        files[f"internal/{pkg}/core.go"] = render(GO_CORE, mapping)
        files[f"internal/{pkg}/core_test.go"] = render(GO_TEST, mapping)
        files[f"cmd/{name}/main.go"] = render(GO_MAIN, mapping)
        files["Makefile"] = render(GO_MAKEFILE, mapping)
        files["README.md"] = render(README, {
            **mapping,
            "__INSTALL__": "go mod download",
            "__RUN__": f"go run ./cmd/{name}",
            "__TEST__": "go test -race ./...",
            "__TREE__": f"cmd/{name}/\ninternal/{pkg}/\ngo.mod\nMakefile",
            "__LICENSE__": license_id.upper() if license_id != "none" else "未指定",
        })
        ci_file, ci_image, ci_cmd = CI_GO, "golang:1.22", "go test ./..."
        ci_path = ".github/workflows/ci.yml"

    elif lang == "rust":
        files["Cargo.toml"] = render(RUST_CARGO, mapping)
        files["src/lib.rs"] = RUST_LIB
        files["src/main.rs"] = RUST_MAIN.replace("__CRATE__", pkg)
        files["tests/integration.rs"] = (
            f"#[test]\nfn add_from_crate() {{\n    assert_eq!({pkg}::add(2, 3), 5);\n}}\n"
        )
        files["README.md"] = render(README, {
            **mapping,
            "__INSTALL__": "cargo fetch",
            "__RUN__": "cargo run",
            "__TEST__": "cargo test",
            "__TREE__": "src/\ntests/\nCargo.toml",
            "__LICENSE__": license_id.upper() if license_id != "none" else "未指定",
        })
        ci_file, ci_image, ci_cmd = CI_RUST, "rust:1.79", "cargo test"
        ci_path = ".github/workflows/ci.yml"
    else:
        raise ValueError(f"不支持的语言：{lang}")

    files[".gitignore"] = GITIGNORE[lang]

    if ci == "github":
        files[ci_path] = ci_file
    elif ci == "gitlab":
        files[".gitlab-ci.yml"] = render(CI_GITLAB, {"__IMAGE__": ci_image, "__CMD__": ci_cmd})

    if license_id == "mit":
        files["LICENSE"] = render(MIT_LICENSE, mapping)
    elif license_id == "apache-2.0":
        files["LICENSE"] = render(APACHE_LICENSE, mapping)

    return files


def cmd_scaffold(args: argparse.Namespace) -> int:
    if not NAME_RE.match(args.name):
        print("参数错误：--name 必须匹配 ^[A-Za-z][A-Za-z0-9_-]{1,63}$", file=sys.stderr)
        return EXIT_BAD_INPUT

    target = args.dir or os.path.join(os.getcwd(), args.name)
    files = build_tree(args.lang, args.name, args.test_framework, args.ci, args.license)

    if args.dry_run:
        print(f"[dry-run] 目标目录：{target}")
        for rel in sorted(files):
            print(f"  + {rel}  ({len(files[rel].encode('utf-8'))} 字节)")
        print(f"[dry-run] 共 {len(files)} 个文件，未写入磁盘。")
        return EXIT_OK

    if os.path.isdir(target) and os.listdir(target) and not args.force:
        print(f"目标目录非空：{target}（加 --force 覆盖，或换 --dir）", file=sys.stderr)
        return EXIT_CONFLICT

    created = 0
    for rel, content in sorted(files.items()):
        path = os.path.join(target, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
        except OSError as exc:
            print(f"写入失败 {rel}：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        created += 1

    print(f"已生成 {created} 个文件 → {target}")
    print("下一步：")
    if args.lang == "python":
        print("  python -m venv .venv && pip install -e \".[dev]\" && pytest")
    elif args.lang == "node":
        print("  npm install && npm test")
    elif args.lang == "go":
        print("  go test -race ./...")
    else:
        print("  cargo test")
    return EXIT_OK


def read_source(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def python_metrics(text: str) -> dict:
    """用 ast 统计函数/类与复杂度近似值。"""
    result = {"functions": 0, "classes": 0, "longest_function": 0, "longest_name": "",
              "max_complexity": 0, "complex_functions": []}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            result["classes"] += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"] += 1
            end = getattr(node, "end_lineno", node.lineno)
            length = end - node.lineno + 1
            if length > result["longest_function"]:
                result["longest_function"] = length
                result["longest_name"] = node.name
            complexity = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
                                      ast.With, ast.AsyncWith, ast.BoolOp, ast.IfExp)):
                    complexity += 1
                elif isinstance(child, ast.Match):
                    complexity += len(getattr(child, "cases", []))
            if complexity > result["max_complexity"]:
                result["max_complexity"] = complexity
            if complexity > HIGH_COMPLEXITY:
                result["complex_functions"].append({"name": node.name, "complexity": complexity,
                                                    "lines": length, "line": node.lineno})
    return result


def cmd_metrics(args: argparse.Namespace) -> int:
    root = args.path
    if not os.path.isdir(root):
        print(f"参数错误：目录不存在 {root}", file=sys.stderr)
        return EXIT_BAD_INPUT

    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "target", "dist", "build"}
    by_ext: dict[str, dict] = defaultdict(lambda: {"files": 0, "lines": 0, "nonempty": 0, "comment": 0})
    hot_files: list[dict] = []
    todos: list[dict] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    funcs_total = 0
    classes_total = 0
    longest = {"name": "", "lines": 0, "file": ""}
    complex_funcs: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            ext = os.path.splitext(fname)[1].lower() or "(noext)"
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size > 2_000_000:
                continue
            text = read_source(path)
            lines = text.splitlines()
            nonempty = [ln for ln in lines if ln.strip()]
            comments = [ln for ln in nonempty if ln.strip().startswith(("#", "//", "/*", "*", "<!--"))]
            entry = by_ext[ext]
            entry["files"] += 1
            entry["lines"] += len(lines)
            entry["nonempty"] += len(nonempty)
            entry["comment"] += len(comments)
            rel = os.path.relpath(path, root).replace(os.sep, "/")

            if len(lines) > HOT_FILE_LINES:
                hot_files.append({"file": rel, "lines": len(lines)})
            for idx, line in enumerate(lines, start=1):
                if TODO_RE.search(line):
                    todos.append({"file": rel, "line": idx, "text": line.strip()[:120]})
            try:
                with open(path, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
                hashes[digest].append(rel)
            except OSError:
                pass

            if ext == ".py":
                pm = python_metrics(text)
                funcs_total += pm["functions"]
                classes_total += pm["classes"]
                if pm["longest_function"] > longest["lines"]:
                    longest = {"name": pm["longest_name"], "lines": pm["longest_function"], "file": rel}
                for cf in pm["complex_functions"]:
                    complex_funcs.append({**cf, "file": rel})

    duplicates = [{"hash": h[:12], "files": fs} for h, fs in hashes.items() if len(fs) > 1]
    hot_files.sort(key=lambda x: x["lines"], reverse=True)
    complex_funcs.sort(key=lambda x: x["complexity"], reverse=True)

    report = {
        "root": os.path.abspath(root),
        "by_extension": {k: v for k, v in sorted(by_ext.items(), key=lambda kv: -kv[1]["lines"])},
        "totals": {
            "files": sum(v["files"] for v in by_ext.values()),
            "lines": sum(v["lines"] for v in by_ext.values()),
            "nonempty": sum(v["nonempty"] for v in by_ext.values()),
            "comment": sum(v["comment"] for v in by_ext.values()),
            "python_functions": funcs_total,
            "python_classes": classes_total,
        },
        "hot_files": hot_files[:20],
        "longest_function": longest,
        "complex_functions": complex_funcs[:20],
        "duplicate_files": duplicates[:20],
        "todo_count": len(todos),
        "todos": todos[:30],
    }

    if args.json:
        text = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        t = report["totals"]
        lines = ["# 代码度量报告", "",
                 f"- 根目录：{report['root']}",
                 f"- 文件数：{t['files']}，总行数：{t['lines']}，非空行：{t['nonempty']}，注释行：{t['comment']}",
                 f"- Python 函数数：{t['python_functions']}，类数：{t['python_classes']}",
                 f"- TODO/FIXME 数：{report['todo_count']}", "",
                 "## 按扩展名", "", "| 扩展名 | 文件 | 行数 | 非空行 | 注释行 |", "|---|---|---|---|---|"]
        for ext, v in report["by_extension"].items():
            lines.append(f"| {ext} | {v['files']} | {v['lines']} | {v['nonempty']} | {v['comment']} |")
        lines += ["", f"## 热点文件（>{HOT_FILE_LINES} 行）", ""]
        if hot_files:
            lines += ["| 文件 | 行数 |", "|---|---|"]
            lines += [f"| {h['file']} | {h['lines']} |" for h in hot_files[:10]]
        else:
            lines.append("无。")
        lines += ["", "## 最长函数与高复杂度函数", "",
                  f"- 最长函数：{longest['name'] or '无'}（{longest['lines']} 行，{longest['file'] or '-'}）"]
        if complex_funcs:
            lines += ["", "| 文件 | 函数 | 复杂度 | 行数 |", "|---|---|---|---|"]
            lines += [f"| {c['file']} | {c['name']} | {c['complexity']} | {c['lines']} |" for c in complex_funcs[:10]]
        else:
            lines.append(f"- 复杂度 >{HIGH_COMPLEXITY} 的函数：无")
        lines += ["", "## 重复文件（内容完全相同）", ""]
        if duplicates:
            for d in duplicates[:10]:
                lines.append(f"- {d['hash']}: {', '.join(d['files'])}")
        else:
            lines.append("无。")
        lines += ["", "## 结论与优先动作", ""]
        ranked = sorted(complex_funcs, key=lambda x: x["complexity"], reverse=True)[:3]
        if ranked:
            for c in ranked:
                lines.append(f"- 拆分 {c['file']}::{c['name']}（复杂度 {c['complexity']}，{c['lines']} 行）")
        for h in hot_files[:2]:
            lines.append(f"- 拆分热点文件 {h['file']}（{h['lines']} 行）")
        if not ranked and not hot_files:
            lines.append("- 未发现明显热点，按修改频率排序后再决定重构优先级。")
        lines.append("")
        text = "\n".join(lines)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            print(f"写入失败：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        print(f"度量报告已写入：{args.out}")
    else:
        print(text)

    if args.strict and (hot_files or complex_funcs):
        return EXIT_CONFLICT
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="project_scaffold.py",
        description="多语言工程骨架生成 + 代码度量。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python project_scaffold.py scaffold --lang go --name demo --dry-run",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scaffold", help="生成工程骨架")
    s.add_argument("--lang", required=True, choices=["python", "node", "go", "rust"], help="语言")
    s.add_argument("--name", required=True, help="项目名（^[A-Za-z][A-Za-z0-9_-]{1,63}$）")
    s.add_argument("--dir", help="输出目录，默认为当前目录下的同名目录")
    s.add_argument("--test-framework", default="pytest", choices=["pytest", "unittest", "vitest", "jest"],
                   help="测试框架，默认 pytest（node 默认 vitest）")
    s.add_argument("--ci", default="github", choices=["github", "gitlab", "none"], help="CI 类型")
    s.add_argument("--license", default="mit", choices=["mit", "apache-2.0", "none"], help="许可证")
    s.add_argument("--dry-run", action="store_true", help="只打印将要创建的文件树")
    s.add_argument("--force", action="store_true", help="目标目录非空时覆盖")
    s.set_defaults(func=cmd_scaffold)

    m = sub.add_parser("metrics", help="统计代码度量")
    m.add_argument("path", help="要统计的目录")
    m.add_argument("--json", action="store_true", help="输出 JSON")
    m.add_argument("--out", metavar="文件路径", help="写入文件")
    m.add_argument("--strict", action="store_true", help="存在热点文件或高复杂度函数时退出码为 1")
    m.set_defaults(func=cmd_metrics)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scaffold" and args.lang != "node" and args.test_framework in ("vitest", "jest"):
        print("参数错误：--test-framework vitest/jest 仅适用于 --lang node", file=sys.stderr)
        return EXIT_BAD_INPUT
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
