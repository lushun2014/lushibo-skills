---
name: lushibo-game-security
description: Defensive game security and cheat research covering external and internal cheat architecture, trainers, memory tampering, ESP/overlay, aim automation, injection and hooks, packet manipulation, asset/config modification, anti-cheat telemetry, integrity, server authority, Unity IL2CPP, Unreal, incident analysis, and detection validation. Use when Codex receives a game binary, cheat sample, anti-cheat design, suspicious telemetry, memory offsets, hooks, overlays, player reports, or needs to understand how game abuse works in order to detect, reproduce in a lab, harden, or investigate it.
triggers:
  - 游戏安全
  - 反外挂设计
  - anti-cheat
  - 作弊检测
  - cheat detection
  - 游戏防护
  - 完整性校验
  - 遥测分析
---

# Lushibo Game Security

## 触发条件

- **加载时机**：收到游戏二进制、作弊样本、反作弊设计、可疑遥测、内存偏移、hook、overlay、玩家举报，或操作员明确要求防御侧检测/加固/复盘时。
- **中文关键词**：游戏安全、反外挂设计、作弊检测、游戏防护、完整性校验、遥测分析、封号申诉复盘、举报核查。
- **英文关键词**：anti-cheat、cheat detection、telemetry、integrity check、server authority、IL2CPP、Unreal、incident analysis。
- **边界**：本 skill 做检测与加固；需要直接实现外挂链路时切到 `$lushibo-game-hack` / `$lushibo-game-redteam`。

Analyze the abuse path from trust boundary to observable behavior, then implement detection and hardening.

## Start

1. Identify engine, platform, architecture, network model, authoritative state, anti-cheat components, and available artifacts.
2. Classify the technique: external memory, injected/internal, input automation, overlay/ESP, runtime patch, packet/protocol, asset/config, kernel/driver, DMA/hardware, or account/economy abuse.
3. Map required access, modified state, data sources, persistence/lifecycle, and observable artifacts.
4. Reproduce only the minimum behavior needed to validate detection or a defensive hypothesis.

## Select references

- Cheat categories, data flows, and observables: read `references/cheat-architecture.md`.
- Anti-cheat architecture and control placement: read `references/anti-cheat-design.md`.
- Unity/IL2CPP and Unreal analysis: read `references/engine-security.md`.
- Investigation and evidence: read `references/incident-analysis.md`.

## Tools

- Use `scripts/integrity_manifest.py` to create or verify signed-off file hash manifests.
- Use `scripts/telemetry_analyze.py` to summarize player/input telemetry and flag explainable anomaly indicators.
- Combine with `$lushibo-reverse`, `$lushibo-memory`, and `$lushibo-lab` for binaries, runtime state, and evidence handling.

## Deliver

Return the technique classification, trust-boundary failure, required capabilities, observables, reproduction harness, integrity/telemetry checks, false-positive considerations, mitigations, and retest plan. Separate a detection hypothesis from a confirmed cheat artifact.

---

## 执行步骤

1. 识别引擎、平台、架构、网络模型、权威状态、AC 组件与可用产物。
2. 分类技术：外部内存 / 注入内部 / 输入自动化 / overlay-ESP / 运行时 patch / 封包协议 / 资产配置 / 内核驱动 / DMA 硬件 / 账号经济。
3. 映射所需访问、被修改状态、数据来源、持久化与生命周期、可观测产物。
4. 只复现验证检测或防御假设所需的最小行为。
5. 用 `scripts/integrity_manifest.py` 建/验文件哈希清单，用 `scripts/telemetry_analyze.py` 汇总玩家与输入遥测并标出可解释的异常指标。
6. 输出检测与加固方案，区分检测假设与已确认的作弊产物；需要还原样本本体时组合 `$lushibo-reverse`、`$lushibo-memory`、`$lushibo-lab`。

## 交付物

- 技术分类与信任边界失效点。
- 所需能力、可观测物、最小复现 harness。
- 完整性/遥测检查项、误报考量、缓解措施与复测计划。
- "检测假设 vs 已确认作弊产物"分列结论。

## 验证方式

- 完整性清单可复算，篡改后能被检出。
- 遥测分析对已知作弊样本命中、对正常样本不误报（给出误报率或误报样例）。
- 复现 harness 只做最小行为，可重复执行。
- 结论区分假设与确认；检测建议附具体遥测字段或校验点，而非泛泛而谈。
