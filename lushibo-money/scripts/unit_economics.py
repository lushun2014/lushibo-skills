#!/usr/bin/env python3
"""变现项目单位经济模型计算器（unit economics calculator）。

纯标准库实现。用于把"客单价 / 成本 / 获客成本 / 转化率"换算成
毛利率、LTV、LTV/CAC、回本周期、盈亏平衡销量与每千次曝光收入，
并给出红黄绿判定与敏感性分析。

示例：
    python unit_economics.py --price 1999 --cost 300 --cac 150 --conv 3% --repeat 1.2 --fixed 2000 --sens
"""

from __future__ import annotations

import argparse
import json
import sys

EXIT_OK = 0
EXIT_BAD_INPUT = 2

# 判定阈值：(绿下限, 黄下限)
MARGIN_GREEN, MARGIN_YELLOW = 0.60, 0.30
LTVCAC_GREEN, LTVCAC_YELLOW = 3.0, 1.0
PAYBACK_GREEN = 3.0


def parse_ratio(raw: str) -> float:
    """把 '3%' / '0.03' / '3' 统一解析成小数。"""
    text = str(raw).strip()
    if not text:
        raise argparse.ArgumentTypeError("空值")
    if text.endswith("%"):
        text = text[:-1].strip()
        try:
            value = float(text) / 100.0
        except ValueError:
            raise argparse.ArgumentTypeError(f"无法解析百分比：{raw}") from None
    else:
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"无法解析数值：{raw}") from None
    # 大于 1 的裸数值按百分数处理（3 → 0.03）
    if value > 1.0:
        value = value / 100.0
    return value


def grade(value: float, green: float, yellow: float, higher_is_better: bool = True) -> str:
    """返回 绿 / 黄 / 红 判定。"""
    if higher_is_better:
        if value >= green:
            return "绿"
        if value >= yellow:
            return "黄"
        return "红"
    if value <= green:
        return "绿"
    if value <= yellow:
        return "黄"
    return "红"


def fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def compute(args: argparse.Namespace) -> dict:
    """核心计算，返回结构化结果。"""
    price = args.price
    cost = args.cost
    cac = args.cac
    conv = args.conv
    repeat = args.repeat
    fixed = args.fixed
    churn = args.churn

    gross = price - cost
    margin = gross / price if price else 0.0

    # 生命周期总毛利
    if args.model == "subscription":
        if churn <= 0:
            ltv = float("inf")
            life_months = float("inf")
        else:
            life_months = 1.0 / churn
            ltv = gross * life_months
        monthly_contribution = gross
    else:
        ltv = gross * repeat
        life_months = 12.0 if repeat > 0 else 0.0
        monthly_contribution = (gross * repeat) / 12.0 if repeat > 0 else 0.0

    ltv_cac = (ltv / cac) if cac > 0 else float("inf")
    payback_months = (cac / monthly_contribution) if monthly_contribution > 0 else float("inf")
    breakeven_units = (fixed / gross) if gross > 0 else float("inf")
    revenue_per_1k = 1000 * conv * price
    gross_per_1k = 1000 * conv * gross
    # 每 1000 次曝光要卖出多少单才能覆盖固定成本
    units_per_1k_needed = (fixed / gross_per_1k) if gross_per_1k > 0 else float("inf")

    return {
        "price": price,
        "cost": cost,
        "cac": cac,
        "conv": conv,
        "repeat": repeat,
        "fixed": fixed,
        "churn": churn,
        "model": args.model,
        "gross_per_unit": gross,
        "margin": margin,
        "ltv": ltv,
        "life_months": life_months,
        "monthly_contribution": monthly_contribution,
        "ltv_cac": ltv_cac,
        "payback_months": payback_months,
        "breakeven_units": breakeven_units,
        "revenue_per_1k_impressions": revenue_per_1k,
        "gross_per_1k_impressions": gross_per_1k,
        "impressions_per_1k_needed_for_fixed": units_per_1k_needed,
    }


def verdicts(res: dict) -> list[tuple[str, str, str]]:
    """返回 (指标, 数值展示, 判定) 列表。"""
    rows = [
        ("毛利率", fmt_pct(res["margin"]), grade(res["margin"], MARGIN_GREEN, MARGIN_YELLOW)),
    ]
    if res["ltv_cac"] == float("inf"):
        rows.append(("LTV/CAC", "∞（无获客成本）", "绿"))
    else:
        rows.append(("LTV/CAC", f"{res['ltv_cac']:.2f}", grade(res["ltv_cac"], LTVCAC_GREEN, LTVCAC_YELLOW)))
    if res["payback_months"] == float("inf"):
        rows.append(("CAC 回本周期", "不可回收（单件毛利 ≤ 0）", "红"))
    else:
        rows.append(("CAC 回本周期", f"{res['payback_months']:.2f} 个月", grade(res["payback_months"], PAYBACK_GREEN, 6.0, higher_is_better=False)))
    return rows


def render_markdown(res: dict, args: argparse.Namespace) -> str:
    lines: list[str] = []
    lines.append("# 单位经济模型测算")
    lines.append("")
    lines.append("## 输入")
    lines.append("")
    lines.append("| 参数 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 模式 | {res['model']} |")
    lines.append(f"| 客单价 | {fmt_money(res['price'])} |")
    lines.append(f"| 单件可变成本 | {fmt_money(res['cost'])} |")
    lines.append(f"| 获客成本 CAC | {fmt_money(res['cac'])} |")
    lines.append(f"| 转化率（曝光→成交） | {fmt_pct(res['conv'])} |")
    lines.append(f"| 平均购买次数 | {res['repeat']:.2f} |")
    lines.append(f"| 月固定成本 | {fmt_money(res['fixed'])} |")
    if res["model"] == "subscription":
        lines.append(f"| 月流失率 | {fmt_pct(res['churn'])} |")
    lines.append("")
    lines.append("## 结果")
    lines.append("")
    lines.append("| 指标 | 数值 | 公式 |")
    lines.append("|---|---|---|")
    lines.append(f"| 单件毛利 | {fmt_money(res['gross_per_unit'])} | 客单价 − 单件可变成本 |")
    lines.append(f"| 毛利率 | {fmt_pct(res['margin'])} | 单件毛利 ÷ 客单价 |")
    ltv_text = "∞" if res["ltv"] == float("inf") else fmt_money(res["ltv"])
    ltv_formula = "单件毛利 ÷ 月流失率" if res["model"] == "subscription" else "单件毛利 × 平均购买次数"
    lines.append(f"| LTV | {ltv_text} | {ltv_formula} |")
    ltv_cac_text = "∞" if res["ltv_cac"] == float("inf") else f"{res['ltv_cac']:.2f}"
    lines.append(f"| LTV/CAC | {ltv_cac_text} | LTV ÷ CAC |")
    payback_text = "不可回收" if res["payback_months"] == float("inf") else f"{res['payback_months']:.2f} 个月"
    lines.append(f"| CAC 回本周期 | {payback_text} | CAC ÷ 月均毛利贡献 |")
    be_text = "不可达（毛利 ≤ 0）" if res["breakeven_units"] == float("inf") else f"{res['breakeven_units']:.0f} 单"
    lines.append(f"| 盈亏平衡销量（月） | {be_text} | 月固定成本 ÷ 单件毛利 |")
    lines.append(f"| 每千次曝光收入 | {fmt_money(res['revenue_per_1k_impressions'])} | 1000 × 转化率 × 客单价 |")
    lines.append(f"| 每千次曝光毛利 | {fmt_money(res['gross_per_1k_impressions'])} | 1000 × 转化率 × 单件毛利 |")
    lines.append("")
    lines.append("## 判定")
    lines.append("")
    lines.append("| 指标 | 数值 | 判定 |")
    lines.append("|---|---|---|")
    for name, value, mark in verdicts(res):
        lines.append(f"| {name} | {value} | {mark} |")
    lines.append("")
    lines.append("判定基准：毛利率 ≥60% 绿 / 30%-60% 黄 / <30% 红；LTV/CAC ≥3 绿 / 1-3 黄 / <1 红；回本周期 ≤3 个月 绿 / 3-6 个月 黄 / >6 个月 红。")
    lines.append("")

    if args.sens:
        lines.append("## 敏感性分析：每千次曝光毛利（行=客单价，列=转化率）")
        lines.append("")
        price_factors = [0.8, 1.0, 1.2]
        conv_factors = [0.5, 1.0, 1.5]
        header = "| 客单价 \\ 转化率 | " + " | ".join(fmt_pct(res["conv"] * f) for f in conv_factors) + " |"
        lines.append(header)
        lines.append("|---" * (len(conv_factors) + 1) + "|")
        for pf in price_factors:
            price = res["price"] * pf
            gross = price - res["cost"]
            cells = [fmt_money(1000 * res["conv"] * f * gross) for f in conv_factors]
            lines.append(f"| {fmt_money(price)} | " + " | ".join(cells) + " |")
        lines.append("")
        lines.append("说明：单元格为每千次曝光可获得的毛利；负值表示该价格低于可变成本。")
        lines.append("")
    return "\n".join(lines)


def render_json(res: dict) -> str:
    def clean(value):
        if isinstance(value, float) and value == float("inf"):
            return None
        return round(value, 4) if isinstance(value, float) else value

    payload = {k: clean(v) for k, v in res.items()}
    payload["verdicts"] = {name: mark for name, _v, mark in verdicts(res)}
    payload["infinite_fields"] = [k for k, v in res.items() if v == float("inf")]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unit_economics.py",
        description="变现项目单位经济模型计算器：毛利率 / LTV / CAC / 回本周期 / 盈亏平衡 / 敏感性分析。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python unit_economics.py --price 1999 --cost 300 --cac 150 --conv 3% --repeat 1.2 --fixed 2000 --sens",
    )
    p.add_argument("--price", type=float, required=True, help="客单价（必须 > 0）")
    p.add_argument("--cost", type=float, default=0.0, help="单件可变成本，默认 0")
    p.add_argument("--cac", type=float, default=0.0, help="获客成本 CAC，默认 0")
    p.add_argument("--conv", type=parse_ratio, default=0.03, help="转化率，支持 3%% 或 0.03，默认 3%%")
    p.add_argument("--repeat", type=float, default=1.0, help="平均购买次数，默认 1.0")
    p.add_argument("--fixed", type=float, default=0.0, help="月固定成本，默认 0")
    p.add_argument("--churn", type=parse_ratio, default=0.0, help="月流失率（订阅模式使用），默认 0")
    p.add_argument("--model", choices=["one-shot", "subscription"], default="one-shot", help="收入模式")
    p.add_argument("--sens", action="store_true", help="输出客单价 × 转化率 敏感性分析表")
    p.add_argument("--json", action="store_true", help="输出 JSON 而不是 Markdown")
    p.add_argument("--out", metavar="文件路径", help="把结果写入文件（默认打印到 stdout）")
    return p


def validate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    errors: list[str] = []
    if args.price <= 0:
        errors.append("--price 必须大于 0")
    if args.cost < 0:
        errors.append("--cost 不能为负")
    if args.cac < 0:
        errors.append("--cac 不能为负")
    if args.fixed < 0:
        errors.append("--fixed 不能为负")
    if not (0 < args.conv <= 1):
        errors.append("--conv 必须在 (0, 1] 区间（即 0% < 转化率 ≤ 100%）")
    if args.repeat <= 0:
        errors.append("--repeat 必须大于 0")
    if not (0 <= args.churn < 1):
        errors.append("--churn 必须在 [0, 1) 区间")
    if args.model == "subscription" and args.churn <= 0:
        errors.append("订阅模式必须给出 --churn（月流失率）> 0，否则生命周期为无穷")
    if args.cost >= args.price:
        print(f"警告：单件成本 {args.cost} ≥ 客单价 {args.price}，单件毛利为负。", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"参数错误：{e}", file=sys.stderr)
        parser.print_usage(sys.stderr)
        raise SystemExit(EXIT_BAD_INPUT)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate(args, parser)

    res = compute(args)
    text = render_json(res) if args.json else render_markdown(res, args)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            print(f"写入失败：{exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        print(f"已写入：{args.out}")
    else:
        print(text)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
