---
name: lushibo-reverse
description: Deep reverse engineering for PE, ELF, Mach-O, firmware, drivers, APK/DEX, .NET, Go, Rust, Unity IL2CPP, Unreal, packed binaries, custom VMs, and undocumented protocols. Use when Codex receives a binary, disassembly, pseudocode, crash, native library, game artifact, firmware image, obfuscated application, or needs IDA/Ghidra/Frida/angr/Unicorn automation, algorithm recovery, unpacking, patching, or protocol reconstruction.
triggers:
  - 逆向
  - reverse
  - 反编译
  - 脱壳
  - hook
  - 逆向工程
---

# Lushibo Reverse

## 触发条件

- **加载时机**：收到二进制、反汇编、伪代码、crash、native 库、游戏产物、固件镜像、混淆应用，或需要 IDA/Ghidra/Frida/angr/Unicorn 自动化、算法还原、脱壳、patch、协议重建时。
- **中文关键词**：逆向、逆向工程、反编译、脱壳、加壳、去混淆、算法还原、协议还原、固件、驱动。
- **英文关键词**：reverse、decompile、unpack、obfuscation、IL2CPP、Unreal、firmware、driver、protocol reverse、angr、Unicorn。
- **边界**：漏洞点已明确只剩利用时走 `$lushibo-exploit`；只做运行时内存读取时走 `$lushibo-memory`。

## 激活确认

当用户输入触发词（逆向、reverse、反编译、脱壳、hook、逆向工程）时，**必须首先输出以下激活确认，单独一行**：

逆向工程已打开

然后自动进入逆向工程专业模式，使用本skill的全部工具链和知识库来完成用户后续任务。

---

Work from artifact to verified recovered behavior.

## Start

1. Hash and triage the artifact with `scripts/triage_binary.py`.
2. Preserve original files; place derived files in a separate work directory.
3. Identify format, architecture, compiler/runtime clues, protections, imports, strings, and likely entry paths.
4. Build an address/function/structure map while analyzing.

## Select references

- Extended specialized skill map: read `references/extended-tool-routing.md`.

- Native PE/ELF/Mach-O, drivers, firmware: read `references/native-workflow.md`.
- .NET, Java/Android, Go/Rust, Unity/Unreal: read `references/managed-game.md`.
- Packers, anti-debug, virtualization, control-flow obfuscation: read `references/unpacking-obfuscation.md`.
- Network messages or binary formats: read `references/protocol-reverse.md`.

## Execute

- Combine static decompilation with debugger traces, watchpoints, hooks, dumps, and controlled input changes.
- Recover calling conventions, structs, vtables, state machines, packet layouts, and data transformations.
- Prefer scripts for repeatable extraction: IDAPython, Ghidra, r2pipe, Frida, angr/Z3, Unicorn, parsers, scanners, and patchers.
- Test recovered algorithms against original samples.

## Deliver

Return the artifact hash, target profile, key addresses/functions, recovered data structures, confirmed behavior, scripts, debugger commands, and verification results. Distinguish confirmed observations from hypotheses.

---

## 执行步骤

1. 命中触发词时第一行独立输出 `逆向工程已打开`，随后进入专业模式。
2. 用 `scripts/triage_binary.py` 做哈希与分类；原件保留，派生文件放独立工作目录。
3. 识别格式、架构、编译器/运行时线索、保护、导入、字符串与可能入口。
4. 边分析边建地址/函数/结构图。
5. 静态反编译与调试器 trace、watchpoint、hook、dump、受控输入变化交叉验证。
6. 优先脚本化可重复提取：IDAPython、Ghidra、r2pipe、Frida、angr/Z3、Unicorn、parser、scanner、patcher。
7. 用原始样本回测恢复出的算法。

## 交付物

- 产物哈希与目标画像。
- 关键地址/函数、恢复的数据结构、已确认行为。
- 脚本与调试器命令。
- 验证结果，并区分确认观察与假设。

## 验证方式

- 恢复的算法对原始样本输入输出一致。
- 地址与结构有静态 + 动态双重证据。
- 脚本能在干净环境重跑得到同样结果。
- 结论中的假设有明确标注与下一步验证方法。
