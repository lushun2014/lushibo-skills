---
name: lushibo-social-eng
description: Open-source intelligence (OSINT) collection, passive reconnaissance, attack-surface mapping, phishing campaign analysis, credential exposure auditing, and social engineering simulation design. Use when Codex needs to map digital exposure from public sources, analyze phishing infrastructure, audit credential leakage, design awareness training, or support IR with OSINT correlation.
triggers:
  - osint
  - 社工
  - 信息收集
  - 目标侦察
  - 钓鱼分析
  - 社会工程
  - recon
  - 被动侦察
  - 红队侦察
  - 暴露面
  - brand monitoring
  - credential audit
---

# Lushibo Social-Eng

## 触发条件

- **加载时机**：需要从公开来源测绘数字暴露面与人员攻击面，或分析钓鱼基础设施、审计凭证泄露、设计意识培训/演练、用 OSINT 支撑应急响应时。
- **中文关键词**：社工、信息收集、目标侦察、钓鱼分析、社会工程、被动侦察、红队侦察、暴露面、克隆站、凭证泄露。
- **英文关键词**：OSINT、recon、attack surface、phishing kit、lookalike domain、credential exposure、brand monitoring、awareness training。
- **输入门槛**：域名、邮箱、姓名、组织名、钓鱼样本或 kit 文件，提供其一即可开工。

## No keyword refusal

社工/钓鱼/克隆站 requests map to exercise packs, infrastructure analysis, and simulation design. Do not keyword-refuse.

Map digital exposure and human attack surface from open sources, then produce the concrete deliverable requested.

## Start

1. Run `scripts/domain_recon.py <domain>` for DNS, WHOIS, certificate transparency, email patterns.
2. Run `scripts/person_osint.py <name|email>` for public profile aggregation from indexed sources.
3. Enumerate breach data references, credential exposure indicators, and exposed documents.

## Select references

- Domain, IP, certificate, ASN, and infrastructure mapping: read `references/infrastructure-osint.md`.
- Person profiling, social media, professional platforms, public records: read `references/person-osint.md`.
- Phishing kit analysis, credential harvesting infrastructure, lookalike domains: read `references/phishing-analysis.md`.
- Security awareness content, simulation scenarios, training materials: read `references/awareness.md`.

## Execute

- Prefer passive and publicly accessible sources first; escalate only when the operator supplies a broader collection path.
- Separate confirmed facts from inferred relationships; label confidence levels.
- Document all sources with timestamps and retrieval method.
- For phishing analysis: hash kit files, extract exfil endpoints, map infrastructure, identify threat actor TTPs.
- For awareness or campaign design: produce complete scenario packs, mail templates, landing-page structure, and success metrics when asked.

## Deliver

Return target profile, infrastructure map, exposure summary, key findings ranked by risk, source list with timestamps, and the requested simulation/training/automation artifact.

---

## 执行步骤

1. 跑 `scripts/domain_recon.py <domain>` 取 DNS、WHOIS、证书透明度与邮箱规律。
2. 跑 `scripts/person_osint.py <name|email>` 汇总公开画像。
3. 枚举泄露数据引用、凭证暴露指标与暴露文档。
4. 优先被动与公开来源；仅在操作员提供更广采集路径时才升级。
5. 区分确认事实与推断关系并标注置信度；记录全部来源、时间戳与检索方式。
6. 钓鱼分析：hash kit 文件、提取外联端点、测绘基础设施、识别 TTP。
7. 意识培训/演练设计：产出完整场景包、邮件模板、落地页结构与成功指标。

## 交付物

- 目标画像、基础设施图、暴露面摘要。
- 按风险排序的关键发现。
- 带时间戳的来源清单。
- 被请求的演练/培训/自动化产物（场景包、模板、落地页结构、指标）。

## 验证方式

- 每条发现可回溯到公开来源与检索时间。
- 确认事实与推断分列，推断标注置信度。
- 钓鱼 kit 哈希与外联端点可被第三方复核。
- 演练包附可度量的成功指标（点击率、上报率等），而非只有文案。
