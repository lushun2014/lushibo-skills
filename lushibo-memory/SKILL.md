---
name: lushibo-memory
description: Cross-platform process memory, dump, runtime, heap, pointer-chain, signature, structure, and memory-forensics analysis for Windows, Linux, Android, Unity IL2CPP, Unreal, native applications, crash dumps, and raw memory images. Use when Codex receives a PID, process name, memory dump, module offset, AOB pattern, pointer chain, runtime address, crash dump, Volatility artifact, Frida target, or needs ReadProcessMemory/process_vm_readv code, map/module discovery, structure reconstruction, memory diffing, hooks, watchpoints, dump analysis, or rollback-safe patch tooling.
triggers:
  - 内存分析
  - memory dump
  - AOB
  - 指针链
  - pointer chain
  - ReadProcessMemory
  - 内存取证
  - Volatility
  - 堆分析
  - 内存扫描
---

# Lushibo Memory

## 触发条件

- **加载时机**：收到 PID、进程名、内存 dump、模块偏移、AOB 通配模式、指针链、运行期地址、crash dump、Volatility 产物或 Frida 目标，需要读内存、还原结构或做内存取证时。
- **中文关键词**：内存分析、内存取证、指针链、堆分析、内存扫描、结构还原、偏移、读写进程。
- **英文关键词**：memory dump、AOB、pointer chain、ReadProcessMemory、process_vm_readv、Volatility、heap、watchpoint、IL2CPP、crash dump。
- **边界**：需要先搞清代码逻辑再读内存时，先走 `$lushibo-reverse`。

Resolve runtime addresses and structures from evidence, then produce repeatable tooling.

## Start

1. Establish architecture, pointer width, endianness, target OS/runtime, and artifact type.
2. Distinguish absolute addresses, module-relative offsets, signatures, pointer chains, handles, and generated references.
3. Record module mappings, page protections, thread/heap context, and address provenance.
4. Use `scripts/aob_scan.py` for wildcard byte-pattern scans and `scripts/dump_strings.py` for offset-aware ASCII/UTF-16 extraction.

## Select references

- Windows live process, dumps, WinDbg, RPM/WPM: read `references/windows.md`.
- Linux, Android, Frida, IL2CPP: read `references/linux-android.md`.
- Raw dumps, structures, pointer chains, memory forensics: read `references/dump-structures.md`.

## Execute

- Prefer module resolution, signatures, and validated pointer paths over hard-coded absolute addresses.
- Use controlled state changes, memory diffs, watchpoints, allocation hooks, and access-width patterns to recover structures.
- Verify readable/writable regions and bounds before access.
- For patches, capture original bytes, validate expected bytes, restore protections, and provide rollback.

## Deliver

Return the address derivation, mapping evidence, recovered structure, complete reader/scanner/hook/patch code, error handling, logs, and verification steps.

---

## 执行步骤

1. 确定架构、指针宽度、字节序、目标 OS/运行时与产物类型。
2. 区分绝对地址、模块相对偏移、签名、指针链、句柄与生成引用。
3. 记录模块映射、页保护、线程/堆上下文与地址来源。
4. 用 `scripts/aob_scan.py` 做通配字节模式扫描，用 `scripts/dump_strings.py` 做偏移感知的 ASCII/UTF-16 提取。
5. 用受控状态变化、内存 diff、watchpoint、分配钩子与访问宽度模式还原结构。
6. 访问前校验区域可读写与边界；patch 前保存原始字节、校验期望字节、恢复保护并提供回滚。

## 交付物

- 地址推导过程与映射证据。
- 恢复出的结构体与指针链定义。
- 完整 reader/scanner/hook/patch 代码（含错误处理与日志）。
- 验证步骤与回滚方式。

## 验证方式

- 地址推导可被同一命令复算；跨重启/重连后指针链仍成立，或写明失效条件。
- 结构字段用受控状态变化或 fixture 双向验证（改值 → 观测变化 → 改回）。
- patch 能回滚到原始字节，且期望字节校验能拦住错版本。
- 优先模块解析/签名/已验证指针路径；硬编码绝对地址必须标注来源与失效风险。
