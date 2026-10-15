#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""person_osint.py — 人员 / 账号 OSINT 离线查询清单与请求模板生成器。

所属 skill : lushibo-social-eng（路世博 codeX 版）
依赖       : 仅 Python 3 标准库（argparse / hashlib / json / re / sys / time / urllib / datetime）

用途
----
给定姓名、邮箱、用户名或域名，生成一份**可直接执行**的 OSINT 采集清单：
  * 每个查询项给出可复制的查询 URL
  * 对应的 curl 命令（含超时与 UA，便于留证）
  * 结果解析提示（该从返回内容里看什么、怎么判定命中）
  * 证据记录模板（来源 URL + 检索时间 + 检索方式，满足 lushibo-lab 留证要求）

默认**完全离线**：只打印清单，不向任何第三方站点发起请求。
只有在显式传入 --verify-urls 时，才会对清单里的 URL 做一次 HEAD 探测
（用于确认端点是否可达），并受 --timeout 与 --rate-limit 约束。

合规边界
--------
* 仅用于**授权范围内**的资产自查、红队/蓝队演练、自有品牌暴露面审计与应急响应支撑。
* 只使用公开可访问的信息源与官方公开 API；不绕过认证、不抓取需登录内容、不购买/使用泄露库原文。
* 查询第三方站点前，确认其 ToS 与当地法律（GDPR / 个保法等）允许；带 API key 的端点请自备凭据。
* 不得用于跟踪、骚扰、人肉或任何未经授权的目标画像。使用者对查询行为负全部责任。
* 所有输出必须脱敏后才能进入报告：真实邮箱/手机号/凭证一律替换为占位符。

用法示例
--------
    python person_osint.py --help
    python person_osint.py target@example.com
    python person_osint.py "Zhang San" --type name --json
    python person_osint.py johndoe --type username --only username,email
    python person_osint.py example.com --type domain --out plan.json
    python person_osint.py target@example.com --verify-urls --timeout 8
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "1.0.0"
UA = "Lushibo-OSINT/1.0 (+authorized-assessment; offline-planner)"

# ---------------------------------------------------------------- 输入校验

RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63}$")
RE_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")
RE_DOMAIN = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)
RE_NAME = re.compile(r"^[\w\u4e00-\u9fff][\w\u4e00-\u9fff .'\-]{0,63}$", re.UNICODE)

VALID_TYPES = ("auto", "name", "email", "username", "domain")
CATEGORIES = ("username", "email", "identity", "correlation", "media")


class InputError(ValueError):
    """输入不满足校验规则时抛出。"""


def detect_type(raw: str) -> str:
    """按字面特征推断输入类型；无法判定时抛 InputError。

    判定顺序刻意把 username 放在 name 之前：单个 ASCII 词（johndoe、john.doe）
    既是合法用户名也是合法姓名，用户名侧的查询清单更可执行；需要按姓名查时
    用 --type name 显式覆盖。
    """
    s = raw.strip()
    if not s:
        raise InputError("输入为空")
    if len(s) > 128:
        raise InputError("输入过长（>128 字符），请拆分为单个目标")
    if RE_EMAIL.match(s):
        return "email"
    if s.startswith("@") and RE_USERNAME.match(s[1:]):
        return "username"
    if RE_DOMAIN.match(s):
        return "domain"
    if " " not in s and RE_USERNAME.match(s):
        return "username"
    if RE_NAME.match(s):
        return "name"
    raise InputError("无法识别输入类型，请用 --type 显式指定（name/email/username/domain）")


def validate(raw: str, kind: str) -> str:
    """按显式类型做严格校验，返回归一化后的值。"""
    s = raw.strip()
    if kind == "email":
        if not RE_EMAIL.match(s):
            raise InputError("邮箱格式非法：%s" % s)
        return s.lower()
    if kind == "domain":
        s = s.lower().rstrip(".")
        if not RE_DOMAIN.match(s):
            raise InputError("域名格式非法：%s" % s)
        return s
    if kind == "username":
        s = s.lstrip("@")
        if not RE_USERNAME.match(s):
            raise InputError("用户名格式非法（允许字母数字 . _ -，最长 64）：%s" % s)
        return s
    if kind == "name":
        if not RE_NAME.match(s):
            raise InputError("姓名格式非法（含可疑字符或过长）：%s" % s)
        return s
    raise InputError("未知类型：%s" % kind)


# ---------------------------------------------------------------- 查询项构造

def _curl(url: str, headers=None, method: str = "GET") -> str:
    parts = ["curl", "-sS", "-m", "15", "-A", "'%s'" % UA]
    if method != "GET":
        parts += ["-X", method]
    for h in headers or []:
        parts += ["-H", "'%s'" % h]
    parts.append("'%s'" % url)
    return " ".join(parts)


def _item(cat, key, purpose, url, parse_hint, headers=None, needs_key=False, offline=False):
    return {
        "category": cat,
        "id": key,
        "purpose": purpose,
        "url": url,
        "curl": _curl(url, headers),
        "parse_hint": parse_hint,
        "requires_api_key": bool(needs_key),
        "offline_only": bool(offline),
    }


def _quote(s: str) -> str:
    return urllib.parse.quote_plus(s)


def build_plan(value: str, kind: str, only=None) -> list:
    """按输入类型生成查询清单。value 已通过 validate()。"""
    items = []
    email = value if kind == "email" else None
    username = value if kind == "username" else None
    domain = value if kind == "domain" else None
    name = value if kind == "name" else None

    # ---- 用户名枚举（username） ----
    if username:
        for site, tmpl, hint in (
            ("github", "https://github.com/{u}", "HTTP 404 = 不存在；200 且 profile 页有 activity = 命中"),
            ("gitlab", "https://gitlab.com/{u}", "同上；注意同名不同人，需比对头像/简介/提交邮箱"),
            ("reddit", "https://www.reddit.com/user/{u}/about.json", "JSON 里 data.name 与创建时间（created_utc）"),
            ("hackernews", "https://hacker-news.firebaseio.com/v0/user/{u}.json", "返回 null = 不存在；否则看 karma/created"),
            ("keybase", "https://keybase.io/_/api/1.0/user/lookup.json?username={u}", "可拿到绑定社交账号与 PGP key 指纹"),
            ("telegram", "https://t.me/{u}", "页面存在且非「If you have Telegram」占位 = 命中"),
            ("steam", "https://steamcommunity.com/id/{u}", "看 vanity URL 是否 302 到具体 profile"),
            ("medium", "https://medium.com/@{u}", "看是否 200 且有文章列表"),
            ("devto", "https://dev.to/{u}", "看 200 与文章/简介"),
            ("mastodon", "https://infosec.exchange/@{u}", "联邦宇宙实例；换实例重试可提高命中率"),
            ("twitch", "https://www.twitch.tv/{u}", "看 200 与频道页"),
            ("pinterest", "https://www.pinterest.com/{u}/", "看 200 与 pin 列表"),
            ("tiktok", "https://www.tiktok.com/@{u}", "看 200 与 bio"),
            ("instagram", "https://www.instagram.com/{u}/", "未登录常返回登录墙，判定需谨慎"),
            ("x", "https://x.com/{u}", "未登录常被限流，需人工浏览器复核"),
            ("linkedin", "https://www.linkedin.com/in/{u}", "未登录多为 999/登录墙，仅作线索"),
        ):
            items.append(_item(
                "username", "username:%s" % site,
                "账号存在性枚举：%s" % site,
                tmpl.format(u=urllib.parse.quote(username)),
                hint,
            ))
        items.append(_item(
            "username", "username:aggregator",
            "聚合枚举（sherlock / maigret）— 本地跑，不经过本脚本联网",
            "local://sherlock %s" % username,
            "对照 sherlock/maigret 输出，逐条人工复核误报；命中率高的平台优先人工确认",
            offline=True,
        ))
        items.append(_item(
            "username", "username:google-dork",
            "搜索引擎 dork：跨站点关联同一用户名",
            "https://www.google.com/search?q=%s" % _quote('"%s" -site:github.com' % username),
            "看结果里的论坛/博客/简历；记录域名与快照时间",
        ))

    # ---- 邮箱暴露面（email） ----
    if email:
        items.append(_item(
            "email", "email:hibp-account",
            "已知数据泄露事件中是否出现该邮箱",
            "https://haveibeenpwned.com/api/v3/breachedaccount/%s?truncateResponse=false" % _quote(email),
            "JSON 数组；每项含 Name/BreachDate/DataClasses。空数组=未命中",
            headers=["hibp-api-key: $HIBP_API_KEY", "user-agent: Lushibo-OSINT"],
            needs_key=True,
        ))
        items.append(_item(
            "email", "email:hibp-pastes",
            "粘贴站泄露（Pastebin 类）中出现情况",
            "https://haveibeenpwned.com/api/v3/pasteaccount/%s" % _quote(email),
            "JSON 数组；看 Source/Id/Date。仅作线索，不下载原文",
            headers=["hibp-api-key: $HIBP_API_KEY", "user-agent: Lushibo-OSINT"],
            needs_key=True,
        ))
        items.append(_item(
            "email", "email:gravatar",
            "Gravatar 头像与公开 profile（由邮箱哈希反查）",
            "https://gravatar.com/%s.json" % hashlib.md5(email.encode("utf-8")).hexdigest(),
            "404=无 Gravatar；200 时看 entry[].profileUrl / accounts[] 可直连其他平台",
        ))
        items.append(_item(
            "email", "email:emailrep",
            "邮箱信誉与画像（是否一次性、是否出现在可疑源）",
            "https://emailrep.io/%s" % _quote(email),
            "看 reputation / suspicious / details.profiles（关联社交账号）",
        ))
        items.append(_item(
            "email", "email:google-dork",
            "公开页面中直接出现该邮箱",
            "https://www.google.com/search?q=%s" % _quote('"%s"' % email),
            "看 PDF/文档/提交记录；记录 URL 与抓取时间，正文中的邮箱需脱敏",
        ))
        items.append(_item(
            "email", "email:hunter",
            "企业邮箱命名规律与同域其他联系人",
            "https://hunter.io/email-verifier/%s" % _quote(email),
            "看 pattern 字段推断同域命名规则，再据此枚举同事邮箱",
        ))
        items.append(_item(
            "email", "email:pgp",
            "PGP 公钥服务器查询（可拿到姓名与多个邮箱）",
            "https://keys.openpgp.org/vks/v1/by-email/%s" % _quote(email),
            "返回 ASCII armored key = 命中；解析 UID 行取姓名与其他邮箱",
        ))

    # ---- 姓名 / 身份关联（identity） ----
    if name:
        items.append(_item(
            "identity", "identity:linkedin-dork",
            "按姓名 + 公司/职位定位职业档案",
            "https://www.google.com/search?q=%s" % _quote('site:linkedin.com/in "%s"' % name),
            "看 title 摘要里的职位与城市；不要登录抓取",
        ))
        items.append(_item(
            "identity", "identity:scholar",
            "学术产出（论文/机构/合作者网络）",
            "https://scholar.google.com/scholar?q=%s" % _quote('"%s"' % name),
            "同名严重，必须用机构/领域交叉过滤",
        ))
        items.append(_item(
            "identity", "identity:orcid",
            "ORCID 研究者档案（含曾用名与机构历史）",
            "https://pub.orcid.org/v3.0/expanded-search/?q=%s" % _quote(name),
            "看 num-found；命中后用 orcid id 取完整档案",
        ))
        items.append(_item(
            "identity", "identity:patents",
            "专利/发明人档案（常含城市与雇主）",
            "https://patents.google.com/?inventor=%s" % _quote(name),
            "看发明人地址与受让人（雇主）",
        ))
        items.append(_item(
            "identity", "identity:public-records",
            "公开记录类站点（各国差异大，仅作线索）",
            "https://www.google.com/search?q=%s" % _quote('"%s" (简历 OR 履历 OR 判决 OR 登记)' % name),
            "只采信官方/一手来源；聚合站信息必须二次核实",
        ))

    # ---- 关联与基础设施（correlation） ----
    if domain:
        items.append(_item(
            "correlation", "corr:whois",
            "域名注册信息与注册人线索",
            "https://rdap.org/domain/%s" % urllib.parse.quote(domain),
            "RDAP JSON：看 entities[].vcardArray 里的姓名/邮箱/电话；隐私保护时为空",
        ))
        items.append(_item(
            "correlation", "corr:crtsh",
            "证书透明度日志 → 子域与关联域名",
            "https://crt.sh/?q=%s&output=json" % _quote("%." + domain),
            "看 name_value 与 issuer；同一 issuer/证书序列可聚类关联资产",
        ))
        items.append(_item(
            "correlation", "corr:mx",
            "邮件服务商与外包情况（影响钓鱼演练可行性评估）",
            "local://nslookup -type=MX %s" % domain,
            "MX 指向 M365/Google/自建，决定后续邮件侧评估方式",
            offline=True,
        ))
        items.append(_item(
            "correlation", "corr:github-code",
            "代码/配置里泄露的该域信息（密钥、内部主机名）",
            "https://github.com/search?q=%s&type=code" % _quote('"%s"' % domain),
            "看 commit 与文件路径；命中密钥立即按负责任披露流程上报",
        ))

    if email:
        local = email.split("@", 1)[0]
        items.append(_item(
            "correlation", "corr:localpart-as-username",
            "把邮箱本地部分当作用户名回灌到用户名枚举",
            "https://github.com/search?q=%s&type=users" % _quote(local),
            "命中后回到 username 类目逐平台核对",
        ))
        items.append(_item(
            "correlation", "corr:email-domain",
            "邮箱域名 → 组织资产面（转 domain 类目）",
            "https://rdap.org/domain/%s" % urllib.parse.quote(email.split("@", 1)[1]),
            "看注册组织与注册时间，判断是个人域还是企业域",
        ))

    # ---- 图片与元数据（media） ----
    items.append(_item(
        "media", "media:reverse-image",
        "反向图片检索（Yandex 对人脸最有效）",
        "https://yandex.com/images/search?rpt=imageview&url=%s" % _quote("<PUBLIC_IMAGE_URL>"),
        "先把目标公开头像 URL 填入占位符；比对命中页面的账号与时间线",
    ))
    items.append(_item(
        "media", "media:exiftool",
        "本地图片元数据提取（GPS/作者/软件）",
        "local://exiftool -a -G1 <IMAGE> | grep -iE 'gps|author|creator|software'",
        "GPS 坐标与设备型号是强关联证据；先哈希原图再分析",
        offline=True,
    ))

    if only:
        items = [i for i in items if i["category"] in only]
    return items


# ---------------------------------------------------------------- 可达性探测

def verify_urls(items, timeout: float, rate_limit: float):
    """对清单中的 http(s) URL 做 HEAD 探测。只报告状态，不解析内容。"""
    results = []
    for it in items:
        url = it["url"]
        if not url.startswith("http") or "<" in url:
            results.append({"id": it["id"], "url": url, "status": "skipped",
                            "detail": "非 http(s) 或含占位符，跳过"})
            continue
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                results.append({"id": it["id"], "url": url, "status": "ok",
                                "detail": "HTTP %s" % resp.status})
        except urllib.error.HTTPError as exc:
            # 401/403/404 都能说明端点存在；404 在枚举类查询里本身就是结论。
            results.append({"id": it["id"], "url": url, "status": "http_error",
                            "detail": "HTTP %s" % exc.code})
        except urllib.error.URLError as exc:
            results.append({"id": it["id"], "url": url, "status": "unreachable",
                            "detail": str(exc.reason)})
        except Exception as exc:  # noqa: BLE001 - 探测失败不应中断整份清单
            results.append({"id": it["id"], "url": url, "status": "error",
                            "detail": "%s: %s" % (type(exc).__name__, exc)})
        if rate_limit > 0:
            time.sleep(rate_limit)
    return results


# ---------------------------------------------------------------- 输出

EVIDENCE_TEMPLATE = {
    "source_url": "<完整 URL，含查询参数>",
    "retrieved_at": "<ISO8601 含时区，例 2026-10-15T04:10:00+08:00>",
    "method": "<curl / 浏览器 / API>",
    "http_status": "<状态码>",
    "artifact_path": "<落盘文件相对路径，如 evidence/osint/github-johndoe.html>",
    "artifact_sha256": "<对落盘文件取 SHA-256>",
    "confidence": "<confirmed | inferred | unverified>",
    "notes": "<同名误报、需要二次核实点>",
}


def render_text(doc) -> str:
    out = []
    out.append("=" * 78)
    out.append("人员/账号 OSINT 查询清单（离线生成，未联网）")
    out.append("=" * 78)
    out.append("目标     : %s" % doc["input"]["raw"])
    out.append("类型     : %s" % doc["input"]["type"])
    out.append("归一化   : %s" % doc["input"]["normalized"])
    out.append("生成时间 : %s" % doc["generated_at"])
    if doc["derived"]:
        for k, v in doc["derived"].items():
            out.append("  %s = %s" % (k, v))
    out.append("合规边界 : %s" % doc["compliance"])
    out.append("")
    cur = None
    for idx, it in enumerate(doc["plan"], 1):
        if it["category"] != cur:
            cur = it["category"]
            out.append("-" * 78)
            out.append("## %s" % cur)
            out.append("-" * 78)
        flag = []
        if it["requires_api_key"]:
            flag.append("需 API key")
        if it["offline_only"]:
            flag.append("本地执行")
        suffix = ("  [%s]" % " / ".join(flag)) if flag else ""
        out.append("%2d. [%s] %s%s" % (idx, it["id"], it["purpose"], suffix))
        out.append("    URL  : %s" % it["url"])
        out.append("    CURL : %s" % it["curl"])
        out.append("    解析 : %s" % it["parse_hint"])
    out.append("")
    out.append("-" * 78)
    out.append("证据记录模板（每条命中都要填，交给 lushibo-lab 入 manifest）")
    out.append("-" * 78)
    for k, v in EVIDENCE_TEMPLATE.items():
        out.append("  %-18s %s" % (k, v))
    out.append("")
    out.append("下一步：")
    out.append("  1. 按上面顺序执行，每条命中立即填证据模板并落盘哈希。")
    out.append("  2. 同名/同头像的疑似命中必须做二次交叉验证，标注 confidence。")
    out.append("  3. 需要真机可达性探测时再跑 --verify-urls（HEAD 探测，受 --timeout 约束）。")
    out.append("  4. 报告输出前脱敏：真实邮箱/手机号/凭证替换为占位符。")
    if doc.get("verify"):
        out.append("")
        out.append("-" * 78)
        out.append("URL 可达性探测结果（--verify-urls）")
        out.append("-" * 78)
        for r in doc["verify"]:
            out.append("  [%-11s] %s  (%s)" % (r["status"], r["id"], r["detail"]))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="person_osint.py",
        description="人员/账号 OSINT 离线查询清单生成器（仅生成清单与 curl 模板，默认不联网）",
        epilog="仅用于授权范围内的资产自查与演练；输出必须脱敏。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("target", nargs="?", help="姓名 / 邮箱 / 用户名 / 域名")
    ap.add_argument("--type", choices=VALID_TYPES, default="auto",
                    help="显式指定输入类型（默认 auto 自动识别）")
    ap.add_argument("--only", default="", help="只输出指定类目，逗号分隔：%s" % ",".join(CATEGORIES))
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（便于管道处理）")
    ap.add_argument("--out", metavar="FILE", help="把 JSON 写入文件")
    ap.add_argument("--verify-urls", action="store_true",
                    help="对清单中的 http(s) URL 做 HEAD 可达性探测（会联网，默认关闭）")
    ap.add_argument("--timeout", type=float, default=10.0, help="单次探测超时秒数（默认 10）")
    ap.add_argument("--rate-limit", type=float, default=0.5, help="探测间隔秒数（默认 0.5）")
    ap.add_argument("--list-categories", action="store_true", help="列出可用类目后退出")
    ap.add_argument("--version", action="version", version="person_osint.py %s" % __version__)
    args = ap.parse_args(argv)

    if args.list_categories:
        print("\n".join(CATEGORIES))
        return 0

    if not args.target:
        ap.error("缺少 target 参数（姓名 / 邮箱 / 用户名 / 域名）")
    if args.timeout <= 0:
        ap.error("--timeout 必须为正数")
    if args.rate_limit < 0:
        ap.error("--rate-limit 不能为负数")

    only = [c.strip() for c in args.only.split(",") if c.strip()]
    bad = [c for c in only if c not in CATEGORIES]
    if bad:
        ap.error("未知类目：%s（可用：%s）" % (", ".join(bad), ",".join(CATEGORIES)))

    try:
        kind = detect_type(args.target) if args.type == "auto" else args.type
        value = validate(args.target, kind)
    except InputError as exc:
        print("[!] 输入校验失败：%s" % exc, file=sys.stderr)
        return 2

    derived = {}
    if kind == "email":
        derived["邮箱 MD5（Gravatar 用）"] = hashlib.md5(value.encode("utf-8")).hexdigest()
        derived["邮箱 SHA-256"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
        derived["邮箱本地部分"] = value.split("@", 1)[0]
        derived["邮箱域名"] = value.split("@", 1)[1]
    if kind == "name":
        parts = [p for p in re.split(r"[\s.]+", value) if p]
        derived["姓名片段"] = ", ".join(parts)
        derived["候选用户名"] = ", ".join(
            sorted({p.lower() for p in parts} | {".".join(p.lower() for p in parts)})
        )
    if kind == "domain":
        derived["候选邮箱"] = ", ".join(
            "%s@%s" % (p, value) for p in ("admin", "info", "contact", "security", "hr")
        )

    plan = build_plan(value, kind, only=only)
    if not plan:
        print("[!] 识别类型=%s，--only=%s 组合下没有可用查询项；"
              "用 --type 指定类型（如 --type username）或放宽 --only"
              % (kind, ",".join(only) or "(未指定)"), file=sys.stderr)
        return 2

    doc = {
        "tool": "person_osint.py",
        "version": __version__,
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "compliance": "仅用于授权范围内的资产自查/演练；只用公开来源；输出必须脱敏；使用者自负合规责任。",
        "input": {"raw": args.target, "type": kind, "normalized": value},
        "derived": derived,
        "plan": plan,
        "evidence_template": EVIDENCE_TEMPLATE,
    }

    if args.verify_urls:
        try:
            doc["verify"] = verify_urls(plan, args.timeout, args.rate_limit)
        except KeyboardInterrupt:
            print("[!] 探测被中断", file=sys.stderr)
            doc["verify"] = []

    payload = json.dumps(doc, ensure_ascii=False, indent=2)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload + "\n")
        except OSError as exc:
            print("[!] 写入失败：%s" % exc, file=sys.stderr)
            return 2

    if args.json:
        print(payload)
    else:
        print(render_text(doc))
        if args.out:
            print("\n[i] JSON 已写入 %s" % args.out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
