# lushibo-skills

> 路世博 codeX 版技能包 —— 51 个可加载 skill，覆盖逆向工程、渗透红队、漏洞利用、恶意代码、蓝队防御、游戏安全、工程环境、商业变现、内容创作与生活成长。

- **版本**：1.1.0（2026-10-15）
- **skill 数**：51 个顶层 skill ＋ 1 个嵌套 skill（`pentest-tools/src-hunter`）
- **共享资产**：`scripts/`、`routing.md`、`tool-index.md`、`PACKAGE.json`
- **已适配运行时**：Codex CLI · dsh（DeepSeek CLI） · Hermes Agent · 其他 Agent Skills 运行时

---

## 这是什么

一套面向 CLI Agent（Codex / dsh / Hermes / Claude Code 等支持 `skills/` 目录的运行时）的**程序化知识包**。
每个 skill 是一个独立目录，目录内 `SKILL.md` 带 YAML frontmatter（`name` + `description`），
按「触发条件 / 执行步骤 / 交付物 / 验证方式」四段组织；重活再挂 `references/`（参考资料）与 `scripts/`（可执行脚本）。

## 安装与使用（多运行时）

每个 skill 都是「一个目录 + 一个 `SKILL.md`」的通用结构，凡按此约定读取技能的运行时都能直接用。
差别只在**技能目录在哪**和**是否分层**：

| 运行时 | 技能目录 | 目录结构 | 发现方式 |
| :--- | :--- | :--- | :--- |
| Codex CLI | `~/.codex/skills/` | 平铺 `skills/<skill>/SKILL.md` | `~/.codex/AGENTS.md`（人格与路由层）按 `skills/…` 相对路径引用 |
| dsh（DeepSeek CLI） | `~/.dsh/skills/` | 平铺 `skills/<skill>/SKILL.md` | `@deepseek-ai/dsh-skill-filesystem` 插件扫描，默认根 `user-dsh` = `<dshHome>/skills` |
| Hermes Agent | `$HERMES_HOME/skills/` | 可分层 `skills/<分类>/<skill>/SKILL.md` | 递归查找 `SKILL.md`，`.git` 等目录自动跳过 |
| Claude Code 及其他 Agent Skills 运行时 | `~/.claude/skills/` 等 | 平铺 | 读取 `SKILL.md` 的 frontmatter |

Windows 上 `~` 即 `C:\Users\<你>`：Codex 用 `C:\Users\<你>\.codex\skills\`，
dsh 用 `C:\Users\<你>\.dsh\skills\`，Hermes 用 `%LOCALAPPDATA%\hermes\skills\`。

### 通用装法（推荐：克隆一份，再往各运行时同步）

```bash
# 1) 先克隆到 home 下，不占用任何运行时的技能目录
git clone https://github.com/lushun2014/lushibo-skills.git ~/.lushibo-skills

# 2) 以后只拉增量
cd ~/.lushibo-skills && git pull --ff-only
```

再用下面任一运行时的命令同步。同步只复制 skill 目录、不带 `.git`，各运行时的技能目录始终干净。

### Codex CLI

```bash
# 技能目录为空时，直接克隆进去
git clone https://github.com/lushun2014/lushibo-skills.git ~/.codex/skills

# 已有内容时，从本地克隆同步（幂等覆盖）
mkdir -p ~/.codex/skills
cp -r ~/.lushibo-skills/*/ ~/.codex/skills/
cp ~/.lushibo-skills/SKILL.md ~/.lushibo-skills/routing.md ~/.lushibo-skills/tool-index.md ~/.codex/skills/
```

Codex 的人格与触发层是 `~/.codex/AGENTS.md`，它按 `skills/lushibo-xxx/SKILL.md`
这样的相对路径引用技能，所以三份根文件（`SKILL.md` / `routing.md` / `tool-index.md`）要一起放进去。

### dsh（DeepSeek CLI）

```bash
mkdir -p ~/.dsh/skills
cp -r ~/.lushibo-skills/*/ ~/.dsh/skills/
```

dsh 通过 `@deepseek-ai/dsh-skill-filesystem` 插件发现技能，默认根之一是
`user-dsh`（rank 400）= `<dshHome>/skills`，所以 `~/.dsh/skills` 默认就会被扫描。
要把技能放到别处，在 `~/.dsh/profiles/<profile>/cordis.patch.yml` 里追加：

```yaml
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    includeDefaultRoots: true
    customSkillDirs:
      - 'C:\Users\<你>\.dsh\skills'
    watch: true
```

> id-targeted patch **不做深合并**，会整体替换被匹配插件的 config，
> 所以 `includeDefaultRoots` 与 `watch` 要一并写全。

两个坑：

- `~/.dsh/skills` 里若已有另一套同源技能（例如 `seagull-*` 命名的那份），
  两套会同时被扫描、触发词重叠，建议只留一套。
- `description` 里含未加引号的 `": "` 会让 YAML 解析失败，dsh 会**静默丢弃**该 skill。
  本仓库全部 `description` 均已加引号包裹，可直接用。

### Hermes Agent

```bash
# POSIX / git-bash：作为一个分类目录克隆进去
git clone https://github.com/lushun2014/lushibo-skills.git \
  ~/.hermes/skills/lushibo
```

```powershell
# Windows PowerShell（默认 HERMES_HOME = %LOCALAPPDATA%\hermes）
git clone https://github.com/lushun2014/lushibo-skills.git `
  "$env:LOCALAPPDATA\hermes\skills\lushibo"
```

Hermes 是递归扫描 `SKILL.md` 的，技能落在 `skills/lushibo/<skill>/SKILL.md` 即可被识别，
仓库自带的 `.git` 会被自动跳过，不会污染技能列表。装完重启会话生效，无需额外配置。
嵌套 skill 也会被一并识别（`pentest-tools/src-hunter` 会单独出现在技能列表里）。

### 装完怎么用

进入任务前先读 `SKILL.md`（总控路由索引），再按 `routing.md` 定位目标 skill；
工具路径一律查 `tool-index.md`，缺失工具用 `scripts/bootstrap-reverse.ps1`（Windows）
或 `scripts/bootstrap-reverse.sh`（POSIX）自举。

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
