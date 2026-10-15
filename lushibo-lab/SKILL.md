---
name: lushibo-lab
description: Create reproducible technical research workspaces for reverse engineering, penetration testing, memory analysis, fuzzing, malware analysis, protocol research, and CTF cases. Use when Codex needs to organize artifacts, hash evidence, create case directories, track commands and observations, build local test harnesses, collect logs/PCAP/dumps, preserve originals, generate manifests, or package a reproducible technical report.
triggers:
  - 建案
  - case
  - 工作空间
  - workspace
  - CTF案例
  - 取证
  - evidence
  - 案例管理
---

# Lushibo Lab

## 触发条件

- **加载时机**：复杂分析开工前需要干净可复现的 case 目录，或需要组织产物、哈希证据、记录命令与观察、搭本地测试环境、打包可复现报告时。
- **中文关键词**：建案、工作空间、案例管理、取证、证据、案件目录、可复现。
- **英文关键词**：case、workspace、evidence、manifest、hash、reproducible、harness、CTF case。
- **组合**：与 `$lushibo-reverse`、`$lushibo-pentest`、`$lushibo-memory`、`$lushibo-malware` 同用，为它们提供统一落盘结构。

Create a clean, repeatable case before complex analysis.

## Start

1. Run `scripts/new_case.py <name> --root <directory>` to create a case workspace.
2. Put untouched inputs under `artifacts/original/`.
3. Run `scripts/hash_artifact.py <path> --manifest <case>/manifest.json` for each input.
4. Keep derived files under `work/`, scripts under `scripts/`, evidence under `evidence/`, and final outputs under `output/`.

## Select references

- Case lifecycle, commands, snapshots, local services: read `references/case-workflow.md`.
- Evidence, hashes, timestamps, logs, PCAP, dumps, and reporting: read `references/evidence.md`.
- Full-speed CTF intake, category triage, solve engineering, flag verification, and Writeup packaging: read `references/ctf-operations.md`.

## Execute

- Record tool versions, exact commands, environment, timestamps, and output paths.
- Prefer deterministic scripts and configuration over manual-only steps.
- Track assumptions and failed hypotheses in notes.md — **运行期产物**：由建案/分析过程在 case 目录内生成（运行后生成 notes.md），不随包分发，无需预置模板。
- Keep service ports/processes and cleanup commands in the case manifest.

## Deliver

Package the manifest, scripts, evidence index, key artifacts, results, verification commands, and cleanup instructions.

---

## 执行步骤

1. 跑 `scripts/new_case.py <name> --root <directory>` 建 case 工作区。
2. 未改动输入放 `artifacts/original/`；每个输入跑 `scripts/hash_artifact.py <path> --manifest <case>/manifest.json` 入清单。
3. 目录分工：派生文件 `work/`、脚本 `scripts/`、证据 `evidence/`、最终输出 `output/`。
4. 记录工具版本、精确命令、环境、时间戳与输出路径；优先确定性脚本而非纯手工步骤。
5. 假设与失败路径写入 notes.md（运行期产物，见上文 Execute）。
6. 服务端口/进程与清理命令写进 case manifest。

## 交付物

- case 目录树与 manifest（含服务端口、进程与清理命令）。
- 哈希清单、证据索引、关键产物与结果。
- 复现命令、验证命令与清理说明。

## 验证方式

- 按 manifest 中的命令重新执行可复现同一结果。
- 哈希与原始件一致，原始件未被修改（只读或时间戳不变）。
- 清理命令能回收所有启动的服务与端口。
- 结论可回溯到具体证据文件与命令输出。
