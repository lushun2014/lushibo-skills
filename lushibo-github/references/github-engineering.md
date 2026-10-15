# GitHub 工程化细则：结构 / Actions / 自动化 / 推广

本文件是 `lushibo-github` 的模板与片段库。

## 1. 仓库必备文件矩阵

| 文件 | 必需性 | 作用 | 最小内容 |
|---|---|---|---|
| README.md | 必需 | 入口与转化 | 定位、安装、最小示例 |
| LICENSE | 必需 | 法律与采用门槛 | 完整许可证正文 |
| .gitignore | 必需 | 防误提交 | 按语言产物清单 |
| CHANGELOG.md | 强烈建议 | 版本变更可追溯 | Keep a Changelog 格式 |
| CONTRIBUTING.md | 强烈建议 | 降低参与门槛 | 环境、测试、PR 流程 |
| SECURITY.md | 建议 | 漏洞上报 | 渠道 + 48h 响应承诺 |
| CODE_OF_CONDUCT.md | 建议 | 社区基线 | Contributor Covenant |
| CODEOWNERS | 建议 | 评审路由 | 路径 → 团队/个人 |
| dependabot.yml | 建议 | 依赖更新 | 每周、分组小版本 |
| ISSUE_TEMPLATE/ | 建议 | 信息完整度 | bug/feature 两个模板 |

## 2. Actions 片段库

**缓存（Python）**

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: pip
    cache-dependency-path: pyproject.toml
```

**缓存（Node / pnpm）**

```yaml
- uses: pnpm/action-setup@v4
  with: {version: 9}
- uses: actions/setup-node@v4
  with:
    node-version: 20
    cache: pnpm
- run: pnpm install --frozen-lockfile
```

**并发取消**

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**权限最小化 + 发布提权**

```yaml
permissions:
  contents: read
jobs:
  release:
    permissions:
      contents: write
      id-token: write
```

**标签触发发布**

```yaml
on:
  push:
    tags: ["v*.*.*"]
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
        with: {fetch-depth: 0}
      - name: 校验版本一致性
        run: |
          TAG="${GITHUB_REF_NAME#v}"
          PKG=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
          test "$TAG" = "$PKG" || { echo "版本不一致: tag=$TAG pkg=$PKG"; exit 1; }
```

**制品上传**

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: dist-${{ matrix.python-version }}
    path: dist/
    retention-days: 14
```

**路径过滤（文档改动不跑测试）**

```yaml
on:
  pull_request:
    paths-ignore: ["docs/**", "**.md", "LICENSE"]
```

## 3. 分支保护配置要点

| 项 | 建议值 | 理由 |
|---|---|---|
| Require pull request | 开启 | 禁止直接推主分支 |
| Required approvals | 1（小项目）/ 2（关键项目） | 避免自审自合 |
| Dismiss stale approvals | 开启 | 新提交需重新评审 |
| Require status checks | 开启，选 CI 的 lint/test | 拦住回归 |
| Require branches up to date | 开启 | 避免合并后才发现冲突 |
| Require linear history | 可选 | 便于回滚与二分 |
| Allow force push | 关闭 | 保护历史 |
| Restrict who can push | 仅维护者 | 降低事故面 |

## 4. issue / PR 自动化规则

| 规则 | 触发 | 动作 | 实现方式 |
|---|---|---|---|
| 自动标签 | issue 打开 | 按模板字段/关键词打标签 | Actions + 脚本 |
| 缺信息提醒 | issue 正文 <50 字或缺复现步骤 | 评论模板 + needs-info 标签 | Actions 内容检查 |
| 陈旧清理 | 14 天无活动 | stale 标签 + 提醒 | stale 工作流 |
| 超时关闭 | 30 天无活动 | 关闭 + 说明 | stale 工作流 |
| PR 路径标签 | PR 打开 | 按改动目录打标签 | labeler 配置 |
| 首次贡献欢迎 | 作者首次提 PR | 自动评论欢迎 + 指引 | Actions |
| 依赖更新 | 每周一 | 分组提 PR（小版本合并） | dependabot |
| 大 PR 提醒 | 改动 >800 行 | 评论建议拆分 | Actions |

## 5. 提交与变更日志规范

Conventional Commits 前缀：feat、fix、docs、style、refactor、perf、test、build、ci、chore、revert。

CHANGELOG 分类：Added / Changed / Deprecated / Removed / Fixed / Security。每条格式：`- 描述 (#PR编号)`。

自动生成 Release Notes 的分组映射：

| 前缀 | CHANGELOG 分类 |
|---|---|
| feat | Added |
| fix | Fixed |
| perf / refactor | Changed |
| revert / remove | Removed |
| security | Security |

## 6. 开源推广指标

| 指标 | 健康信号 | 说明 |
|---|---|---|
| 首屏跳出 | README 前 20 行能看懂用途 | 决定是否继续读 |
| 安装成功率 | 从零到跑通 <10 分钟 | 决定是否留下 |
| 首次响应时长 | issue <24h、PR <72h | 决定贡献者是否回来 |
| good first issue 转化 | ≥30% 被认领 | 决定社区活力 |
| 贡献者留存 | 二次贡献比例 ≥20% | 比 star 数更能说明问题 |
| star 增长来源 | 有明确渠道归因 | 无法归因的增长通常是噪声 |

## 7. 供应链安全

- 第三方 action 固定到 commit SHA，例如 `uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`。
- 开启 Actions 的 "Require approval for first-time contributors"。
- 发布制品附 SHA-256；关键项目使用 Sigstore/签名。
- 依赖锁定文件必须入库；CI 使用冻结安装（--frozen-lockfile / --require-hashes）。
- 定期轮换发布令牌，使用 OIDC 短期凭据替代长期密钥。

## 8. 使用边界

平台功能与配额随 GitHub 政策调整，配置前以平台当前文档为准。
