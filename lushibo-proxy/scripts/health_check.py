#!/usr/bin/env python3
"""代理节点健康检查与故障切换判定（health check）。

对一组节点做 TCP 握手 + 可选 TLS 握手探测，统计连通率与延迟分位，
输出健康状态表，并给出主/备用节点切换建议。

纯标准库实现（socket / ssl / statistics）。

示例：
    python health_check.py --nodes nodes.json --rounds 3 --timeout 3
    python health_check.py us-la-01=1.2.3.4:443 --tls --sni www.example.com
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import statistics
import sys
import time

EXIT_OK = 0
EXIT_UNHEALTHY = 1
EXIT_BAD_INPUT = 2

FAILS_BEFORE_DOWN = 3


def parse_node_spec(spec: str) -> dict:
    """解析 name=host:port 形式。"""
    name, _, target = spec.partition("=")
    if not target:
        name, target = spec, spec
    host, _, port_text = target.rpartition(":")
    if not host:
        host, port_text = target, "443"
    try:
        port = int(port_text)
    except ValueError:
        raise ValueError(f"端口不是数字：{spec}") from None
    if not (1 <= port <= 65535):
        raise ValueError(f"端口越界：{spec}")
    return {"name": name.strip(), "host": host.strip(), "port": port, "tls": False, "sni": ""}


def load_nodes(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("nodes", [])
    if not isinstance(data, list) or not data:
        raise ValueError("节点清单必须是非空数组")
    nodes: list[dict] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict) or "host" not in item:
            raise ValueError(f"第 {idx + 1} 项缺少 host 字段")
        port = int(item.get("port", 443))
        if not (1 <= port <= 65535):
            raise ValueError(f"第 {idx + 1} 项端口越界")
        nodes.append({
            "name": str(item.get("name", f"node-{idx + 1}")),
            "host": str(item["host"]),
            "port": port,
            "tls": bool(item.get("tls", False)),
            "sni": str(item.get("sni", "")),
        })
    return nodes


def probe(node: dict, timeout: float, use_tls: bool) -> dict:
    """做一次探测，返回耗时与错误信息。"""
    result = {"tcp_ms": None, "tls_ms": None, "error": ""}
    start = time.perf_counter()
    try:
        with socket.create_connection((node["host"], node["port"]), timeout=timeout) as sock:
            result["tcp_ms"] = round((time.perf_counter() - start) * 1000, 1)
            if use_tls:
                ctx = ssl.create_default_context()
                tls_start = time.perf_counter()
                with ctx.wrap_socket(sock, server_hostname=node["sni"] or node["host"]) as tls_sock:
                    tls_sock.do_handshake()
                    result["tls_ms"] = round((time.perf_counter() - tls_start) * 1000, 1)
    except (OSError, ssl.SSLError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def summarize(node: dict, samples: list[dict]) -> dict:
    tcp = [s["tcp_ms"] for s in samples if s["tcp_ms"] is not None]
    tls = [s["tls_ms"] for s in samples if s["tls_ms"] is not None]
    ok = sum(1 for s in samples if s["tcp_ms"] is not None and not s["error"])
    total = len(samples)
    rate = ok / total if total else 0.0
    return {
        "name": node["name"],
        "host": node["host"],
        "port": node["port"],
        "rounds": total,
        "ok": ok,
        "connect_rate": round(rate, 3),
        "tcp_p50": round(statistics.median(tcp), 1) if tcp else None,
        "tcp_min": round(min(tcp), 1) if tcp else None,
        "tcp_max": round(max(tcp), 1) if tcp else None,
        "tls_p50": round(statistics.median(tls), 1) if tls else None,
        "healthy": rate >= 0.99,
        "errors": [s["error"] for s in samples if s["error"]][:2],
    }


def render_markdown(results: list[dict], timeout: float, rounds: int) -> str:
    lines = ["# 代理节点健康检查", "",
             f"- 探测轮次：{rounds} 轮/节点，超时 {timeout}s",
             f"- 节点数：{len(results)}，健康：{sum(1 for r in results if r['healthy'])}", "",
             "| 节点 | 地址 | 连通率 | TCP P50(ms) | TLS P50(ms) | 状态 | 错误 |",
             "|---|---|---|---|---|---|---|"]
    for r in results:
        status = "✅ 健康" if r["healthy"] else "❌ 异常"
        lines.append(f"| {r['name']} | {r['host']}:{r['port']} | {r['connect_rate']:.0%} | "
                     f"{r['tcp_p50'] if r['tcp_p50'] is not None else '-'} | "
                     f"{r['tls_p50'] if r['tls_p50'] is not None else '-'} | {status} | "
                     f"{'; '.join(r['errors']) or '-'} |")
    lines.append("")
    healthy = [r for r in results if r["healthy"]]
    if healthy:
        primary = min(healthy, key=lambda r: r["tcp_p50"] if r["tcp_p50"] is not None else 1e9)
        lines.append(f"## 切换建议")
        lines.append("")
        lines.append(f"- 主用：{primary['name']}（{primary['host']}:{primary['port']}，TCP P50 "
                     f"{primary['tcp_p50']} ms）")
        backups = [r for r in healthy if r["name"] != primary["name"]]
        if backups:
            lines.append(f"- 备用：{', '.join(r['name'] for r in backups[:3])}")
        else:
            lines.append("- 备用：无（建议补一条独立路径，切换阈值：连续 3 次失败）")
    else:
        lines.append("## 切换建议")
        lines.append("")
        lines.append("- 无健康节点，检查本机网络、DNS 与节点服务状态；不要盲目重试。")
    lines.append("")
    lines.append(f"判定规则：连通率 ≥99% 视为健康；连续 {FAILS_BEFORE_DOWN} 次失败切换备用。")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="health_check.py",
        description="代理节点健康检查：TCP/TLS 握手探测、连通率与延迟分位、切换建议。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python health_check.py --nodes nodes.json --rounds 3 --timeout 3 --json",
    )
    p.add_argument("specs", nargs="*", help="节点，形如 name=host:port")
    p.add_argument("--nodes", metavar="JSON路径", help="节点清单 JSON：[{\"name\":..,\"host\":..,\"port\":..,\"tls\":true,\"sni\":..}]")
    p.add_argument("--rounds", type=int, default=3, help="每节点探测轮次，默认 3")
    p.add_argument("--timeout", type=float, default=3.0, help="单次连接超时秒数，默认 3.0")
    p.add_argument("--tls", action="store_true", help="对所有节点额外做 TLS 握手（清单里 tls=true 的节点始终做）")
    p.add_argument("--sni", default="", help="TLS SNI，默认使用 host")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--out", metavar="文件路径", help="写入文件")
    p.add_argument("--quiet", action="store_true", help="不打印到 stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.rounds <= 0:
        print("参数错误：--rounds 必须为正整数", file=sys.stderr)
        return EXIT_BAD_INPUT
    if args.timeout <= 0:
        print("参数错误：--timeout 必须大于 0", file=sys.stderr)
        return EXIT_BAD_INPUT

    nodes: list[dict] = []
    if args.nodes:
        if not os.path.isfile(args.nodes):
            print(f"参数错误：节点清单不存在 {args.nodes}", file=sys.stderr)
            return EXIT_BAD_INPUT
        try:
            nodes += load_nodes(args.nodes)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"参数错误：无法解析节点清单（{exc}）", file=sys.stderr)
            return EXIT_BAD_INPUT
    for spec in args.specs:
        try:
            nodes.append(parse_node_spec(spec))
        except ValueError as exc:
            print(f"参数错误：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT

    if not nodes:
        print("参数错误：至少提供一个节点（位置参数或 --nodes）", file=sys.stderr)
        return EXIT_BAD_INPUT

    for node in nodes:
        if args.sni:
            node["sni"] = args.sni
        if args.tls:
            node["tls"] = True

    results: list[dict] = []
    for node in nodes:
        samples = [probe(node, args.timeout, node["tls"]) for _ in range(args.rounds)]
        results.append(summarize(node, samples))

    text = json.dumps({"timeout": args.timeout, "rounds": args.rounds, "nodes": results},
                      ensure_ascii=False, indent=2) if args.json else render_markdown(results, args.timeout, args.rounds)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            print(f"写入失败：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        if not args.quiet:
            print(f"检查完成，报告已写入：{args.out}")
    elif not args.quiet:
        print(text)

    return EXIT_OK if all(r["healthy"] for r in results) else EXIT_UNHEALTHY


if __name__ == "__main__":
    raise SystemExit(main())
