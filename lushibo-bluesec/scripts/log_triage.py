#!/usr/bin/env python3
"""蓝队日志应急分诊（log triage）。

输入：一个或多个日志文件（.log/.txt/.json/.jsonl/.csv）
输出：findings.md、findings.json、iocs.txt，可选 rules.yml（Sigma 风格规则）

检出规则：
    BL-001 暴力破解（同源 IP 在时间窗内失败次数 ≥ 阈值）
    BL-002 爆破后成功登录（同源 IP 先失败后成功）
    BL-003 敏感账号成功登录 / 新账号创建
    BL-004 特权命令执行（sudo 或进程创建命中敏感命令）
    BL-005 非工作时段登录（本地时间 00:00-06:00 的成功登录）
    BL-006 日志缺口（同一文件内相邻事件时间跳变 > 30 分钟）

纯标准库实现。

示例：
    python log_triage.py auth.log security.jsonl --out-dir .\\triage --threshold 5 --window 60 --rules
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

EXIT_OK = 0
EXIT_ALERT = 1
EXIT_BAD_INPUT = 2

GAP_MINUTES = 30
SENSITIVE_USERS = {"root", "admin", "administrator", "test", "guest", "oracle", "postgres", "ubuntu", "sa"}
SENSITIVE_COMMANDS = [
    "curl ", "wget ", "chmod +x", "base64 -d", "/tmp/", "nc -e", "ncat",
    "powershell -enc", "powershell -e ", "mshta", "certutil -urlcache",
    "bash -i", "/dev/tcp/", "mimikatz", "vssadmin delete", "wevtutil cl",
]

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

RE_SYSLOG_TS = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})")
RE_ISO_TS = re.compile(r"(?P<iso>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})")
RE_IP = re.compile(r"\b(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
RE_FAIL = re.compile(r"Failed (?:password|publickey|none) for (?:invalid user )?(?P<user>\S+) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3})")
RE_ACCEPT = re.compile(r"Accepted (?:password|publickey) for (?P<user>\S+) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3})")
RE_INVALID = re.compile(r"Invalid user (?P<user>\S+) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3})")
RE_SUDO = re.compile(r"sudo:\s+(?P<user>\S+)\s*:.*?COMMAND=(?P<cmd>.+?)\s*$")
RE_SU = re.compile(r"su(?:do)?:.*session opened for user (?P<target>\S+) by (?P<user>\S+?)\(")

JSON_KEYS = {
    "eventid": ("eventid", "EventID", "event_id", "EventId", "event_code"),
    "ip": ("IpAddress", "SourceIp", "source_ip", "ip", "ClientIP", "RemoteIP", "SourceAddress"),
    "user": ("TargetUserName", "AccountName", "user", "UserName", "SubjectUserName", "Account"),
    "ts": ("TimeCreated", "timestamp", "time", "@timestamp", "UtcTime", "EventTime", "date"),
    "command": ("CommandLine", "command", "cmd", "ProcessCommandLine", "NewProcessName", "Image"),
    "logontype": ("LogonType", "logon_type", "LogonTypeId"),
}


@dataclass
class Event:
    source: str
    line_no: int
    raw: str
    ts: datetime | None = None
    src_ip: str = ""
    user: str = ""
    kind: str = "other"          # fail | success | sudo | proc | other
    command: str = ""
    eventid: str = ""


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str
    detail: str
    evidence: list[str] = field(default_factory=list)


def parse_timestamp(line: str, now: datetime) -> datetime | None:
    m = RE_ISO_TS.search(line)
    if m:
        text = m.group("iso").replace(" ", "T")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    m = RE_SYSLOG_TS.match(line.strip())
    if m:
        month = MONTHS.get(m.group("mon"))
        if month:
            try:
                hh, mm, ss = (int(x) for x in m.group("time").split(":"))
                return datetime(now.year, month, int(m.group("day")), hh, mm, ss)
            except ValueError:
                return None
    return None


def flatten_json(obj: dict) -> dict:
    """Windows evtx 导出的 JSON 常带一层 Event 包装，做一次浅合并。"""
    out = dict(obj)
    inner = obj.get("Event")
    if isinstance(inner, dict):
        for k, v in inner.items():
            out.setdefault(k, v)
        sys_block = inner.get("System")
        if isinstance(sys_block, dict):
            for k, v in sys_block.items():
                out.setdefault(k, v)
        for k in ("EventData", "UserData"):
            block = inner.get(k)
            if isinstance(block, dict):
                data = block.get("Data")
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "Name" in item:
                            out.setdefault(str(item["Name"]), item.get("#text", ""))
                for kk, vv in block.items():
                    if kk != "Data":
                        out.setdefault(kk, vv)
    return out


def pick(obj: dict, aliases: tuple[str, ...]) -> str:
    for key in aliases:
        if key in obj and obj[key] not in (None, ""):
            value = obj[key]
            if isinstance(value, dict):
                for sub in ("#text", "text", "SystemTime"):
                    if sub in value:
                        return str(value[sub])
                continue
            return str(value)
    return ""


def parse_json_event(obj: dict, source: str, line_no: int, raw: str, now: datetime) -> Event:
    flat = flatten_json(obj)
    ev = Event(source=source, line_no=line_no, raw=raw)
    ev.eventid = pick(flat, JSON_KEYS["eventid"])
    ev.src_ip = pick(flat, JSON_KEYS["ip"])
    ev.user = pick(flat, JSON_KEYS["user"])
    ev.command = pick(flat, JSON_KEYS["command"])
    ts_text = pick(flat, JSON_KEYS["ts"])
    ev.ts = parse_timestamp(ts_text, now) or parse_timestamp(raw, now)

    logon = pick(flat, JSON_KEYS["logontype"])
    if ev.eventid == "4625":
        ev.kind = "fail"
    elif ev.eventid == "4624":
        ev.kind = "success"
    elif ev.eventid in ("4688", "592", "1"):
        ev.kind = "proc"
    elif ev.eventid == "4672":
        ev.kind = "sudo"
    else:
        low = raw.lower()
        if "failed" in low:
            ev.kind = "fail"
        elif "accepted" in low:
            ev.kind = "success"
    if logon and logon not in ("3", "10") and ev.kind == "success":
        # 交互式登录（2/11）也纳入统计，但标注在证据里
        ev.command = f"LogonType={logon} {ev.command}".strip()
    return ev


def parse_text_event(line: str, source: str, line_no: int, now: datetime) -> Event:
    ev = Event(source=source, line_no=line_no, raw=line.rstrip("\n"))
    ev.ts = parse_timestamp(line, now)

    m = RE_FAIL.search(line)
    if m:
        ev.kind, ev.user, ev.src_ip = "fail", m.group("user"), m.group("ip")
        return ev
    m = RE_ACCEPT.search(line)
    if m:
        ev.kind, ev.user, ev.src_ip = "success", m.group("user"), m.group("ip")
        return ev
    m = RE_INVALID.search(line)
    if m:
        ev.kind, ev.user, ev.src_ip = "fail", m.group("user"), m.group("ip")
        return ev
    m = RE_SUDO.search(line)
    if m:
        ev.kind, ev.user, ev.command = "sudo", m.group("user"), m.group("cmd")
        ip = RE_IP.search(line)
        if ip:
            ev.src_ip = ip.group("ip")
        return ev
    m = RE_SU.search(line)
    if m:
        ev.kind, ev.user, ev.command = "sudo", m.group("user"), f"su -> {m.group('target')}"
        return ev
    ip = RE_IP.search(line)
    if ip:
        ev.src_ip = ip.group("ip")
    return ev


def read_events(paths: list[str], now: datetime) -> tuple[list[Event], list[str]]:
    events: list[Event] = []
    warnings: list[str] = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            warnings.append(f"无法读取 {path}：{exc}")
            continue
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped[0] == "{":
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    events.append(parse_text_event(line, path, idx, now))
                    continue
                if isinstance(obj, dict):
                    events.append(parse_json_event(obj, path, idx, line, now))
                continue
            events.append(parse_text_event(line, path, idx, now))
    return events, warnings


def detect_bruteforce(events: list[Event], window: int, threshold: int) -> tuple[list[Finding], set[str]]:
    by_ip: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        if ev.kind == "fail" and ev.src_ip:
            by_ip[ev.src_ip].append(ev)

    findings: list[Finding] = []
    flagged: set[str] = set()
    for ip, items in by_ip.items():
        timed = [e for e in items if e.ts]
        if len(items) >= threshold and not timed:
            findings.append(Finding(
                "BL-001", "暴力破解（无时间戳，按总量判定）", "P0",
                f"来源 {ip} 失败 {len(items)} 次（阈值 {threshold}），日志缺时间戳无法做窗口判定。",
                [e.raw.strip() for e in items[:5]],
            ))
            flagged.add(ip)
            continue
        timed.sort(key=lambda e: e.ts)
        start = 0
        best: tuple[int, int] | None = None
        for end in range(len(timed)):
            while timed[end].ts - timed[start].ts > timedelta(seconds=window):
                start += 1
            count = end - start + 1
            if count >= threshold and (best is None or count > best[1] - best[0] + 1):
                best = (start, end)
        if best:
            chunk = timed[best[0]:best[1] + 1]
            users = sorted({e.user for e in chunk if e.user})
            findings.append(Finding(
                "BL-001", "暴力破解", "P0",
                f"来源 {ip} 在 {window} 秒窗口内失败 {len(chunk)} 次（阈值 {threshold}），"
                f"目标账号 {', '.join(users[:6]) or '未知'}。",
                [e.raw.strip() for e in chunk[:5]],
            ))
            flagged.add(ip)
    return findings, flagged


def detect_success_after_fail(events: list[Event], flagged: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for ip in sorted(flagged):
        fails = [e for e in events if e.kind == "fail" and e.src_ip == ip and e.ts]
        succs = [e for e in events if e.kind == "success" and e.src_ip == ip and e.ts]
        if not fails or not succs:
            continue
        first_fail = min(e.ts for e in fails)
        after = [e for e in succs if e.ts >= first_fail]
        if not after:
            continue
        first = min(after, key=lambda e: e.ts)
        findings.append(Finding(
            "BL-002", "爆破后成功登录", "P0",
            f"来源 {ip} 先出现暴力破解，随后账号 {first.user or '未知'} 登录成功"
            f"（{first.ts:%Y-%m-%d %H:%M:%S}）。",
            [first.raw.strip()],
        ))
    return findings


def detect_sensitive_accounts(events: list[Event]) -> list[Finding]:
    findings: list[Finding] = []
    seen_users: set[str] = set()
    for ev in events:
        if ev.kind == "success" and ev.user:
            if ev.user.lower() in SENSITIVE_USERS and ev.user.lower() not in seen_users:
                findings.append(Finding(
                    "BL-003", "敏感账号成功登录", "P1",
                    f"账号 {ev.user} 成功登录（来源 {ev.src_ip or '未知'}）。",
                    [ev.raw.strip()],
                ))
            seen_users.add(ev.user.lower())
        if ev.eventid == "4720":
            findings.append(Finding(
                "BL-003", "新账号创建", "P1",
                f"检测到账号创建事件 4720，涉及账号 {ev.user or '未知'}。",
                [ev.raw.strip()],
            ))
    return findings


def detect_privileged_commands(events: list[Event]) -> list[Finding]:
    findings: list[Finding] = []
    for ev in events:
        if ev.kind not in ("sudo", "proc") or not ev.command:
            continue
        low = ev.command.lower()
        hit = [p for p in SENSITIVE_COMMANDS if p in low]
        if hit:
            findings.append(Finding(
                "BL-004", "特权命令执行", "P1",
                f"账号 {ev.user or '未知'} 执行命中敏感特征（{', '.join(hit)}）：{ev.command[:200]}",
                [ev.raw.strip()],
            ))
    return findings


def detect_offhours(events: list[Event]) -> list[Finding]:
    findings: list[Finding] = []
    for ev in events:
        if ev.kind == "success" and ev.ts and 0 <= ev.ts.hour < 6:
            findings.append(Finding(
                "BL-005", "非工作时段登录", "P2",
                f"{ev.ts:%Y-%m-%d %H:%M:%S} 账号 {ev.user or '未知'} 从 {ev.src_ip or '未知'} 登录成功。",
                [ev.raw.strip()],
            ))
    return findings


def detect_log_gaps(events: list[Event]) -> list[Finding]:
    findings: list[Finding] = []
    by_source: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        if ev.ts:
            by_source[ev.source].append(ev)
    for source, items in by_source.items():
        items.sort(key=lambda e: e.ts)
        for prev, cur in zip(items, items[1:]):
            delta = cur.ts - prev.ts
            if delta > timedelta(minutes=GAP_MINUTES):
                findings.append(Finding(
                    "BL-006", "日志缺口", "P2",
                    f"{source} 第 {prev.line_no} 行与第 {cur.line_no} 行之间时间跳变 "
                    f"{delta.total_seconds() / 60:.0f} 分钟（>{GAP_MINUTES} 分钟），可能存在日志清理或采集中断。",
                    [prev.raw.strip(), cur.raw.strip()],
                ))
    return findings


SIGMA_RULES = """title: 疑似凭据爆破
id: BL-001
status: experimental
logsource:
  product: linux
  service: sshd
detection:
  selection:
    message|contains: 'Failed password'
  timeframe: 60s
  condition: selection | count() by src_ip > 5
falsepositives:
  - 运维批量巡检脚本
level: medium
tags: [attack.credential_access, attack.t1110]
---
title: 爆破后成功登录
id: BL-002
status: experimental
logsource:
  product: windows
  service: security
detection:
  fail:
    EventID: 4625
  success:
    EventID: 4624
    LogonType: [3, 10]
  timeframe: 10m
  condition: fail | count() by IpAddress > 5 and success by IpAddress
falsepositives:
  - 用户先输错密码后成功登录
level: high
tags: [attack.credential_access, attack.t1078]
---
title: 特权命令下载或写入临时目录
id: BL-004
status: experimental
logsource:
  product: linux
  service: sudo
detection:
  selection:
    COMMAND|contains:
      - 'curl '
      - 'wget '
      - 'chmod +x'
      - 'base64 -d'
      - '/tmp/'
  condition: selection
falsepositives:
  - 自动化部署脚本
level: high
tags: [attack.execution, attack.t1059]
"""


def render_markdown(findings: list[Finding], events: list[Event], warnings: list[str], args: argparse.Namespace) -> str:
    lines: list[str] = []
    lines.append("# 日志应急分诊报告")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 解析事件数：{len(events)}")
    timed = [e.ts for e in events if e.ts]
    if timed:
        lines.append(f"- 时间范围：{min(timed):%Y-%m-%d %H:%M:%S} ~ {max(timed):%Y-%m-%d %H:%M:%S}")
    else:
        lines.append("- 时间范围：未识别到时间戳")
    lines.append(f"- 告警数：{len(findings)}")
    by_rule: dict[str, int] = defaultdict(int)
    for f in findings:
        by_rule[f.rule_id] += 1
    if by_rule:
        lines.append("- 按规则：" + "，".join(f"{k}×{v}" for k, v in sorted(by_rule.items())))
    lines.append("")
    if warnings:
        lines.append("## 读取警告")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
    lines.append("## 告警明细")
    lines.append("")
    if not findings:
        lines.append("未检出告警。")
        lines.append("")
    for f in findings:
        lines.append(f"### [{f.rule_id}] {f.title}（{f.severity}）")
        lines.append("")
        lines.append(f.detail)
        lines.append("")
        for ev in f.evidence:
            lines.append("```")
            lines.append(ev[:400])
            lines.append("```")
        lines.append("")
    lines.append("## 处置建议")
    lines.append("")
    lines.append("1. P0 告警：立即确认来源 IP 归属，必要时封禁并检查是否有其他主机被同一来源访问。")
    lines.append("2. BL-002 命中：按失陷流程处理，重置相关账号凭据，检查该主机的持久化点。")
    lines.append("3. 固定证据：原始日志只读保留并记录 SHA-256，分析副本另存。")
    lines.append("4. 收敛检测：把本报告中的规则部署到 SIEM，验证一次触发后上线。")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="log_triage.py",
        description="蓝队日志应急分诊：暴力破解 / 爆破后成功 / 敏感账号 / 特权命令 / 非工作时段 / 日志缺口。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python log_triage.py auth.log security.jsonl --out-dir .\\triage --threshold 5 --window 60 --rules",
    )
    p.add_argument("files", nargs="+", help="一个或多个日志文件（.log/.txt/.json/.jsonl/.csv）")
    p.add_argument("--out-dir", default="./triage-out", help="输出目录，默认 ./triage-out")
    p.add_argument("--window", type=int, default=60, help="爆破检测时间窗（秒），默认 60")
    p.add_argument("--threshold", type=int, default=5, help="同窗同源失败次数阈值，默认 5")
    p.add_argument("--json", action="store_true", help="只把 JSON 摘要打印到 stdout")
    p.add_argument("--rules", action="store_true", help="额外输出 Sigma 风格规则 rules.yml")
    p.add_argument("--quiet", action="store_true", help="不打印摘要")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.window <= 0:
        print("参数错误：--window 必须为正整数", file=sys.stderr)
        return EXIT_BAD_INPUT
    if args.threshold <= 0:
        print("参数错误：--threshold 必须为正整数", file=sys.stderr)
        return EXIT_BAD_INPUT
    missing = [f for f in args.files if not os.path.isfile(f)]
    if missing:
        for m in missing:
            print(f"参数错误：文件不存在 {m}", file=sys.stderr)
        return EXIT_BAD_INPUT

    now = datetime.now()
    events, warnings = read_events(args.files, now)

    findings: list[Finding] = []
    bf, flagged = detect_bruteforce(events, args.window, args.threshold)
    findings += bf
    findings += detect_success_after_fail(events, flagged)
    findings += detect_sensitive_accounts(events)
    findings += detect_privileged_commands(events)
    findings += detect_offhours(events)
    findings += detect_log_gaps(events)

    order = {"P0": 0, "P1": 1, "P2": 2}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.rule_id))

    try:
        os.makedirs(args.out_dir, exist_ok=True)
    except OSError as exc:
        print(f"无法创建输出目录：{exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    rule_counts: dict[str, int] = defaultdict(int)
    for f in findings:
        rule_counts[f.rule_id] += 1

    summary = {
        "events": len(events),
        "findings": len(findings),
        "by_rule": dict(sorted(rule_counts.items())),
        "by_severity": {sev: sum(1 for f in findings if f.severity == sev) for sev in ("P0", "P1", "P2")},
        "files": args.files,
        "warnings": warnings,
        "time_range": None,
    }
    timed = [e.ts for e in events if e.ts]
    if timed:
        summary["time_range"] = [f"{min(timed):%Y-%m-%d %H:%M:%S}", f"{max(timed):%Y-%m-%d %H:%M:%S}"]

    write_text(os.path.join(args.out_dir, "findings.md"), render_markdown(findings, events, warnings, args))
    write_text(os.path.join(args.out_dir, "findings.json"), json.dumps(
        {
            "summary": summary,
            "findings": [
                {"rule_id": f.rule_id, "title": f.title, "severity": f.severity,
                 "detail": f.detail, "evidence": f.evidence}
                for f in findings
            ],
        }, ensure_ascii=False, indent=2))

    iocs = sorted({e.src_ip for e in events if e.src_ip} | {e.user for e in events if e.user and e.kind in ("fail", "sudo")})
    write_text(os.path.join(args.out_dir, "iocs.txt"), "\n".join(iocs) + ("\n" if iocs else ""))

    if args.rules:
        write_text(os.path.join(args.out_dir, "rules.yml"), SIGMA_RULES)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print(f"解析事件 {summary['events']} 条，告警 {summary['findings']} 条")
        if summary["by_rule"]:
            print("按规则：" + "，".join(f"{k}×{v}" for k, v in summary["by_rule"].items()))
        print(f"输出目录：{os.path.abspath(args.out_dir)}")
        if warnings:
            for w in warnings:
                print(f"警告：{w}", file=sys.stderr)

    return EXIT_ALERT if any(f.rule_id in ("BL-001", "BL-002") for f in findings) else EXIT_OK


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") or text == "" else text + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
