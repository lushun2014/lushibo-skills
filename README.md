# lushibo-skills

> 路世博 codeX 版技能包 —— 51 个可加载 skill，覆盖逆向工程、渗透红队、漏洞利用、恶意代码、蓝队防御、游戏安全、工程环境、商业变现、内容创作与生活成长。

- **版本**：1.0.0（2026-10-15）
- **skill 数**：51 个顶层 skill ＋ 1 个嵌套 skill（`pentest-tools/src-hunter`）
- **共享资产**：`scripts/`、`routing.md`、`tool-index.md`、`PACKAGE.json`

---

## 这是什么

一套面向 CLI Agent（codex / Claude Code / Hermes 等支持 `skills/` 目录的运行时）的**程序化知识包**。
每个 skill 是一个独立目录，目录内 `SKILL.md` 带 YAML frontmatter（`name` + `description`），
按「触发条件 / 执行步骤 / 交付物 / 验证方式」四段组织；重活再挂 `references/`（参考资料）与 `scripts/`（可执行脚本）。

## 怎么用

把整个仓库放进运行时的 skills 目录即可（以 codex 为例）：

```bash
git clone https://github.com/lushun2014/lushibo-skills.git ~/.codex/skills
```

已有目录时用增量拉取：

```bash
cd ~/.codex/skills && git pull --ff-only
```

进入任务前先读 `SKILL.md`（总控路由索引），再按 `routing.md` 定位目标 skill；
工具路径一律查 `tool-index.md`，缺失工具用 `scripts/bootstrap-reverse.ps1`（Windows）或 `scripts/bootstrap-reverse.sh`（POSIX）自举。

---

## Skill 总览

| 分类 | 数量 | 定位 |
| :--- | :--- | :--- |
| 开局与路由 | 2 | 入口、开局覆盖、全域模式 |
| 逆向工程 | 10 | 二进制 / 移动 / 前端 / 固件逆向 |
| 渗透与红队 | 7 | Web / API / 内网 / 供应链 / LLM 安全 |
| 漏洞利用与内存 | 4 | pwn 链、内存分析、研究工作区 |
| 恶意代码与免杀 | 4 | 样本分析、检测面、C2 架构 |
| 蓝队防御 | 1 | 检测规则、应急响应、日志 |
| 游戏安全 | 5 | 运行时分析、绘制、反作弊面 |
| 社工与情报 | 1 | OSINT、被动侦察、攻击面测绘 |
| 授权与卡密 | 1 | 授权校验流恢复与实现 |
| 工程与环境 | 4 | 代码、GitHub、系统环境、代理网络 |
| 变现与商业 | 3 | 赚钱、电商、直播运营 |
| 内容与创作 | 4 | 写作、成人向创作、文档、图表 |
| 生活与成长 | 5 | 健康、学习、生活运维、心理、演讲 |

### 开局与路由

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-auto-ops` | lushibo-auto-ops | 路世博开局全域与连续交付工作流。 |
| `lushibo-unlimited` | lushibo-unlimited | 路世博全域专家模式 - 激活完整技术栈，覆盖逆向、渗透、内存、漏洞利用、样本分析、免杀研究、游戏辅助、社工情报与工程交付。 |

### 逆向工程

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `reverse-engineering` | reverse-engineering | Provides reverse engineering techniques. |
| `lushibo-reverse` | lushibo-reverse | Deep reverse engineering for PE, ELF, Mach-O, firmware, drivers, APK/DEX, . |
| `radare2` | radare2 | 使用 radare2 / r2 命令行做二进制分析（CLI binary analysis）。 |
| `ida-reverse` | ida-reverse | IDA Pro 逆向分析辅助技能（binary reverse engineering）。 |
| `binary-diff` | binary-diff | 跨版本符号迁移与二进制差分（symbol migration / binary diff）。 |
| `patch-diff-exploit` | patch-diff-exploit | N-day 补丁差分到可用利用（patch diff exploit）。 |
| `apk-reverse` | apk-reverse | 在 CLI 环境下做 Android APK 逆向时使用。 |
| `mobile-reverse` | mobile-reverse | Android/iOS reverse engineering: APK/IPA analysis, Frida/Objection workflow… |
| `js-reverse` | js-reverse | JavaScript reverse engineering: obfuscation recovery, signature/HMAC locati… |
| `firmware-pentest` | firmware-pentest | 固件与 IoT 渗透链（firmware pentest）。 |

### 渗透与红队

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-pentest` | lushibo-pentest | Evidence-driven penetration and attack-surface engineering for web applicat… |
| `pentest-tools` | pentest-tools | 主动渗透测试工具链（pentest toolchain over MCP）。 |
| `api-security` | api-security | API security testing for REST/GraphQL/WebSocket/SOAP: discovery, authz, BOL… |
| `attack-chain` | attack-chain | Multi-stage attack-path orchestration for CTF/red-team lab chains: recon to… |
| `edr-bypass-re` | edr-bypass-re | 逆向防御方实现到红队针对性绕过（EDR / Defender / AV evasion）。 |
| `llm-security` | llm-security | LLM/agent security testing: prompt injection, tool abuse, data exfil paths,… |
| `supply-chain-security` | supply-chain-security | Software supply-chain security: dependency risk, SBOM, package integrity, C… |

### 漏洞利用与内存

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-exploit` | lushibo-exploit | CTF Pwn and vulnerability research — crash triage, primitive analysis, and … |
| `pwn-chain` | pwn-chain | 从漏洞点到可用利用的全链路工程化方法（working exploit / pwn chain）。 |
| `lushibo-memory` | lushibo-memory | Cross-platform process memory, dump, runtime, heap, pointer-chain, signatur… |
| `lushibo-lab` | lushibo-lab | Create reproducible technical research workspaces for reverse engineering, … |

### 恶意代码与免杀

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-malware` | lushibo-malware | Malware analysis and threat intelligence — unpacking, configuration extract… |
| `malware-analysis` | malware-analysis | Malware triage and analysis: unpacking, config extraction, C2 reconstructio… |
| `lushibo-evasion` | lushibo-evasion | Detection engineering research — analyze AV/EDR detection logic, profile si… |
| `lushibo-botnet` | lushibo-botnet | 远控与 C2 运维工程（C2 operations engineering）。 |

### 蓝队防御

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-bluesec` | lushibo-bluesec | 蓝队防御与应急响应工程（blue team & incident response）。 |

### 游戏安全

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-game-hack` | lushibo-game-hack | Game runtime analysis and interactive overlay research — process memory str… |
| `lushibo-game-redteam` | lushibo-game-redteam | Red-team game-security force-start for ESP/overlay, external/kernel memory … |
| `lushibo-game-security` | lushibo-game-security | Defensive game security and cheat research covering external and internal c… |
| `lushibo-anticheat` | lushibo-anticheat | Game anti-cheat surface mapping and bypass-research force-start for ACE/miH… |
| `mobile-competitive-game-security` | mobile-competitive-game-security | Mobile competitive-game security research for 和平精英、王者荣耀、PUBG Mobile、Honor o… |

### 社工与情报

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-social-eng` | lushibo-social-eng | Open-source intelligence (OSINT) collection, passive reconnaissance, attack… |

### 授权与卡密

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-license-security` | lushibo-license-security | License/卡密/activation verification-flow recovery and implementation. |

### 工程与环境

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-code` | lushibo-code | 代码工程与自动化（software engineering & automation）。 |
| `lushibo-github` | lushibo-github | GitHub 工程化与开源运营（GitHub engineering & OSS operations）。 |
| `lushibo-sysenv` | lushibo-sysenv | 跨平台环境工程（Windows / Linux / Kali 环境搭建与运维）。 |
| `lushibo-proxy` | lushibo-proxy | 代理与跨境网络架构工程（proxy & cross-border network engineering）。 |

### 变现与商业

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-money` | lushibo-money | 变现与赚钱工程（monetization engineering）。 |
| `lushibo-ecom` | lushibo-ecom | 电商运营工程（e-commerce operations）。 |
| `lushibo-live` | lushibo-live | 直播运营工程（live-streaming operations）。 |

### 内容与创作

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-writer` | lushibo-writer | 写作工程（writing engineering）。 |
| `lushibo-mature-content` | lushibo-mature-content | 路世博成人向露骨创作 Skill（仅 M5）。 |
| `docs-generator` | docs-generator | Generate technical docs, writeups, reports, and structured Markdown from en… |
| `diagram-generator` | diagram-generator | generate, refine, validate, and render diagrams from natural language, note… |

### 生活与成长

| 目录 | skill | 说明 |
| :--- | :--- | :--- |
| `lushibo-health` | lushibo-health | 健康与体能工程（health & fitness engineering）。 |
| `lushibo-learn` | lushibo-learn | 学习工程（learning engineering）。 |
| `lushibo-lifeops` | lushibo-lifeops | 生活运维工程（life operations engineering）。 |
| `lushibo-mind` | lushibo-mind | 心理与关系工程（mind & relationship engineering）。 |
| `lushibo-speech` | lushibo-speech | 演讲与口才工程（speech & communication engineering）。 |

### 嵌套 skill

| 路径 | skill | 说明 |
| :--- | :--- | :--- |
| `pentest-tools/src-hunter` | src-hunter | 实战 SRC / 众测 / Bug bounty 漏洞挖掘工作流，5 阶段方法论 + 19 个攻击类 playbook。 |

---

## 目录结构

```text
lushibo-skills/
├── SKILL.md                  # 总控路由索引（skill 名：lushibo-router）
├── routing.md                # 全局路由表：目标类型 → skill 映射、冲突消解优先级
├── tool-index.md             # 工具索引：探测命令 / 实测路径 / 安装方式 / 降级路径
├── PACKAGE.json              # 包清单：全部 skill 的 name / path / category
├── scripts/                  # 跨 skill 共享脚本（工具链自举、工具索引刷新）
├── <skill-name>/
│   ├── SKILL.md              # 技能主体（YAML frontmatter + 四段式正文）
│   ├── references/           # 参考资料（按需加载）
│   ├── scripts/              # 可执行脚本
│   └── assets/               # 模板 / 图片 / 密钥库等静态资产
└── README.md
```

## 共享脚本

| 脚本 | 作用 |
| :--- | :--- |
| `scripts/bootstrap-reverse.ps1` | Windows 工具链自举安装（按能力组批量装） |
| `scripts/bootstrap-reverse.sh` | POSIX 工具链自举安装 |
| `scripts/tool-detect.ps1` | 本机工具探测 |
| `scripts/refresh-tool-index.ps1` | 重新探测并重写 `tool-index.md` |
| `scripts/tool-catalog.json` | 工具目录：能力组 → 工具 → 安装源 |

## 第三方来源与许可

| 组件 | 说明 |
| :--- | :--- |
| `pentest-tools/src-hunter` | 自带 `LICENSE`，保留原许可条款 |
| `apk-reverse/debug.keystore` | Android 标准调试签名密钥库（非私密凭据，仅供本地重打包签名） |

其余内容为作者自建技能文档。仓库未附加统一开源许可，默认保留全部权利；
如需二次分发或商用，请先联系作者。

## 免责声明

本仓库内容用于**已获授权的安全测试、CTF 竞赛、实验室研究与防御建设**。
使用者须自行确保对目标系统拥有合法授权，并自行承担因使用不当产生的一切后果。
