---
name: lushibo-github
description: "GitHub 工程化与开源运营（GitHub engineering & OSS operations）。能力：仓库工程化改造（目录结构、README/文档体系、LICENSE、模板、CODEOWNERS）、CI/CD 流水线设计（GitHub Actions 多语言构建矩阵、缓存、制品、多环境发布）、issue 与 PR 自动化（标签、自动回复、超时关闭、分类、依赖更新）、发布工程（语义化版本、CHANGELOG、Release 制品、标签规范）、开源推广与贡献者运营（文档可发现性、good first issue、贡献指南、社区响应 SLA）。Use when 用户提到 GitHub、开源运营、仓库工程化、CI/CD、GitHub Actions、issue自动化、PR自动化、开源推广、分支保护、发布流水线、贡献者运营、语义化版本、CODEOWNERS，或给出仓库、workflow 报错、issue/PR 列表要求改造与自动化。交付物：仓库工程化审计报告（评分 + 修复清单）、Actions 工作流文件、issue/PR 自动化配置、发布流程文档、开源推广清单。"
triggers:
  - GitHub
  - 开源运营
  - 仓库工程化
  - CI/CD
  - GitHub Actions
  - issue自动化
  - PR自动化
  - 开源推广
  - 分支保护
  - 发布流水线
  - 贡献者运营
  - 语义化版本
  - CODEOWNERS
---

# Lushibo GitHub · 工程化与开源运营

仓库的成熟度由**可复现性**决定：陌生人 clone 下来能不能在 10 分钟内跑起来、CI 能不能拦住回归、发布能不能一条命令完成。做不到就是没做完。

## 触发条件

- **加载时机**：用户给出仓库、workflow 文件、issue/PR 列表、发布需求，要求做工程化改造、写 CI、做自动化、做开源推广。
- **中文关键词**：GitHub、开源运营、仓库工程化、CI/CD、Actions、工作流、issue 自动化、PR 自动化、开源推广、分支保护、发布流水线、贡献者运营、语义化版本、贡献指南、模板、标签。
- **英文关键词**：GitHub Actions、workflow、matrix、cache、artifact、release、semver、CHANGELOG、CODEOWNERS、branch protection、dependabot、CODE_OF_CONDUCT、good first issue、SLA。
- **不加载的情况**：只问"项目代码怎么写/怎么重构/怎么测"走 `$lushibo-code`；只问"环境怎么装、工具链怎么配"走 `$lushibo-sysenv`。
- **边界**：本 skill 管**仓库与流水线**，代码内部实现归 code，运行环境归 sysenv。

## 执行步骤

### 第 1 步：仓库工程化审计

先用 `scripts/repo_audit.py` 打分，再动手：

```bash
D:\Python\python.exe scripts\repo_audit.py . --out repo-audit.md
```

十项检查（G-01 至 G-10）：README、LICENSE、.gitignore、CI、测试、依赖锁定、提交规范、issue/PR 模板、文档面、元数据。低于 60 分先补齐基础项，不要先做推广——推广一个跑不起来的仓库只会消耗信誉。

### 第 2 步：目录与文档体系

标准结构（按语言微调）：

```
repo/
  README.md            入口：是什么、解决什么、怎么装、怎么用、怎么贡献
  LICENSE
  CHANGELOG.md         按 Keep a Changelog 格式
  CONTRIBUTING.md      环境要求、提交规范、PR 流程、评审标准
  SECURITY.md          漏洞上报渠道与响应时限
  CODE_OF_CONDUCT.md
  .github/
    workflows/         流水线
    ISSUE_TEMPLATE/    问题模板（bug/feature/question）
    PULL_REQUEST_TEMPLATE.md
    CODEOWNERS
    dependabot.yml
  docs/                深入文档
  tests/ 或 test/
  src/ 或 <包名>/
```

README 结构（顺序固定）：一句话定位 → 徽章 → 30 秒快速开始（可复制命令）→ 核心特性 3-6 条 → 用法示例 → 配置说明 → 贡献指引 → 许可证。README 里**必须有可复制粘贴就能跑的命令**，这是仓库的第一转化点。

### 第 3 步：CI 流水线设计

原则：**快反馈在前，慢验证在后；失败必须能定位到具体步骤**。

| 阶段 | 内容 | 目标时长 |
|---|---|---|
| lint | 格式 + 静态检查 | ≤1 分钟 |
| test | 单元测试 + 覆盖率门槛 | ≤5 分钟 |
| build | 打包/编译 | ≤5 分钟 |
| integration | 集成/端到端（可选，按需触发） | ≤15 分钟 |
| release | 打标签触发，产出制品并发布 | ≤10 分钟 |

关键配置要点：

- 多版本矩阵：Python 3.10-3.13、Node 18/20/22、Go 1.21/1.22。
- 缓存：Python 缓存 pip、Node 缓存 pnpm/npm、Go 缓存 module 与 build、Rust 缓存 target。
- 并发取消：同一分支新提交取消旧的进行中任务（concurrency + cancel-in-progress）。
- 权限最小化：默认 permissions 设为 contents: read，需要发布的任务单独提权。
- 触发条件：push 到主分支 + PR 到主分支；路径过滤避免文档改动触发全量测试。
- 失败可见：关键步骤加 continue-on-error: false（默认），不要吞错误。

工作流骨架（矩阵 + 缓存 + 并发取消）：

```yaml
name: ci
on:
  push: {branches: [main]}
  pull_request: {branches: [main]}
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
        with: {python-version: "${{ matrix.python-version }}", cache: pip}
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest -q --cov=./ --cov-report=term-missing
```

注意：workflow 里的 `${{ }}` 表达式不要被当成 shell 变量处理；在 SKILL 或文档里引用时要放在 fenced code block 中，避免被解析器误判为路径引用。

### 第 4 步：发布工程

- 版本规范：语义化版本 MAJOR.MINOR.PATCH；破坏性变更升 MAJOR，功能升 MINOR，修复升 PATCH。
- 标签规范：v1.2.3，与包元数据版本严格一致（CI 里加一步校验，不一致直接失败）。
- CHANGELOG：按 Added/Changed/Fixed/Removed/Deprecated/Security 分类，每条附 PR 编号。
- 发布流程：合并到主分支 → 打标签 → CI 构建制品 → 生成 Release Notes（从 PR 标题按 conventional commits 分类）→ 上传制品 → 更新包仓库。
- 回滚：发布前记录上一个可用版本；出问题回滚 = 重新发布上一版本 + 撤回包仓库版本，不要在原版本上改。

### 第 5 步：issue 与 PR 自动化

| 场景 | 自动化 | 实现 |
|---|---|---|
| 新 issue 分类 | 按模板字段自动打标签 | Actions + labeler 或脚本 |
| 缺少复现步骤 | 自动回复模板 + 打 needs-info | Actions 监听 issue 内容 |
| 长期无响应 | 14 天无活动打 stale，30 天关闭 | stale 类工作流 |
| PR 检查 | 必须通过 CI + 至少 1 个 review | 分支保护规则 |
| 依赖更新 | 每周自动提 PR，分组小版本 | dependabot 配置 |
| PR 自动标签 | 按改动路径打标签 | 路径匹配规则 |
| 欢迎新贡献者 | 首次 PR 自动评论 | Actions + 评论脚本 |

分支保护（主分支）：要求 PR、要求 1-2 个 review、要求状态检查通过、要求分支最新、禁止强推、禁止直接推送。

### 第 6 步：开源推广

推广的前提是仓库能被理解。按顺序做：

1. **可发现性**：仓库描述 + topics（5-10 个精准词）+ README 首屏一句话说清用途。
2. **可试用性**：提供一行安装命令、在线演示或示例项目、截图/GIF（README 里至少 1 张）。
3. **可参与性**：标注 good first issue（附背景、涉及文件、验收标准），CONTRIBUTING 写清本地跑测试的完整命令。
4. **传播渠道**：相关社区/论坛/周报投稿、关联项目的 README 互链、技术文章（讲问题与设计取舍，不讲"我写了个库"）。
5. **响应 SLA**：issue 24 小时内首次响应，PR 72 小时内给评审意见。响应速度对贡献者留存的影响大于功能数量。

推广禁忌：刷 star、在无关 issue 下贴链接、README 堆砌徽章而不给用法。

### 第 7 步：贡献者运营

- 贡献者分层：一次性修复 → 常规贡献者 → 维护者。给稳定贡献者写权限与 CODEOWNERS 条目。
- 评审纪律：评审只针对代码与设计，说明"为什么"，给出可执行的修改建议，不要求风格偏好。
- 新人友好：每个 good first issue 标注预计工作量（S/M/L）与涉及文件。
- 记录致谢：Release Notes 与 CHANGELOG 里列出贡献者。

### 第 8 步：安全与合规

- SECURITY.md 写清上报渠道与响应时限（建议 48 小时首次响应）。
- 开启依赖告警与自动安全更新；CI 里加依赖漏洞扫描步骤。
- 制品签名/校验和：Release 附 SHA-256，敏感项目加签名。
- Actions 供应链：第三方 action 固定到 commit SHA，不使用浮动 tag（避免上游被投毒）。

## 交付物

| 文件名 | 格式 | 内容要求 |
|---|---|---|
| 仓库审计报告.md | Markdown | 十项评分、证据、Top 5 修复动作（由审计脚本产出） |
| 工作流文件 | YAML | 放 .github/workflows/，含矩阵、缓存、并发取消、权限 |
| issue-PR自动化.md | Markdown | 场景/触发条件/动作/模板/所需权限 |
| 发布流程.md | Markdown | 版本规范、标签规范、CHANGELOG 格式、回滚步骤 |
| 开源推广清单.md | Markdown | 可发现性/可试用性/可参与性/渠道/响应 SLA 五节 |
| README改版稿.md | Markdown | 按固定顺序重写，含可复制命令与截图占位 |

文件默认落在工作目录的 `github-<仓库名>/` 下；工作流文件同时给出可直接放入仓库的路径。

## 验证方式

1. **审计可复现**：重跑 `scripts/repo_audit.py` 得到相同总分与逐项结论（同一 commit）。
2. **CI 真跑通**：工作流在真实仓库上跑一次，全绿；故意提交一个测试失败，CI 必须变红（证明不是空跑）。
3. **矩阵生效**：CI 日志里能看到所有声明的版本组合都被执行，无跳过。
4. **缓存命中**：第二次运行的缓存步骤显示命中，且总时长比首次下降 ≥30%。
5. **权限最小化**：工作流顶部 permissions 为 read；有写权限的 job 单独声明且能说明必要性。
6. **版本一致性**：包元数据版本与 git tag 一致；构造一次不一致的提交，发布流水线必须失败。
7. **自动化可观测**：issue/PR 自动化的每条规则都给出触发示例（issue 编号或模拟结果），未验证的规则不计入交付。
8. **README 可执行**：按 README 从零跑一遍，10 分钟内完成安装与最小示例，无缺失步骤。

## 参考文档

- `references/github-engineering.md` — 仓库结构模板、Actions 片段库（缓存/矩阵/发布/权限）、分支保护配置、issue/PR 自动化规则、开源推广指标。改造仓库前读。
