# 代码工程细则：骨架 / 重构 / 测试 / 性能

本文件是 `lushibo-code` 的模板与命令参考。

## 1. 多语言骨架结构

### Python

```
proj/
  pyproject.toml        构建 + ruff + pytest 配置
  src/<pkg>/__init__.py
  src/<pkg>/core.py     纯逻辑，无 IO
  tests/test_core.py
  README.md  Makefile  .gitignore
```

```toml
[project]
name = "<name>"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "mypy"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
addopts = "-q --strict-markers"
testpaths = ["tests"]
```

### Node / TypeScript

```
proj/
  package.json  tsconfig.json  eslint.config.js
  src/index.ts  src/core.ts
  tests/core.test.ts
```

package.json 关键脚本：`lint`、`typecheck`（tsc --noEmit）、`test`（vitest run）、`build`。

### Go

```
proj/
  go.mod  Makefile
  cmd/<name>/main.go
  internal/<pkg>/core.go  internal/<pkg>/core_test.go
```

### Rust

```
proj/
  Cargo.toml
  src/lib.rs  src/main.rs
  tests/integration.rs
```

## 2. 重构手法与代码对照

**提取函数**

```python
# 前：一个函数做三件事
def handle(req):
    data = json.loads(req.body)          # 解析
    if "id" not in data: raise ValueError # 校验
    return repo.save(data)                # 持久化

# 后：编排层 + 单一职责
def handle(req):
    data = parse_payload(req.body)
    validate_payload(data)
    return repo.save(data)
```

**用映射表替换条件分支**

```python
# 前
if kind == "a": return handle_a(x)
elif kind == "b": return handle_b(x)
elif kind == "c": return handle_c(x)

# 后
HANDLERS = {"a": handle_a, "b": handle_b, "c": handle_c}
return HANDLERS[kind](x)     # 注意补 KeyError 处理
```

**依赖倒置**

```python
class Clock(Protocol):
    def now(self) -> datetime: ...

class Service:
    def __init__(self, clock: Clock, repo: Repo) -> None:
        self._clock, self._repo = clock, repo
```

**渐进式替换遗留代码**

1. 抽出接口，旧实现与新实现都满足该接口。
2. 用特性开关或路由层按比例/按条件分流。
3. 双跑比对结果，不一致时记录差异样本。
4. 差异收敛后把流量切到新实现，保留旧实现一个版本周期。
5. 删除旧实现与开关。

## 3. 测试细则

**单元测试结构（Arrange-Act-Assert）**

```python
def test_parse_config_missing_key_returns_default():
    cfg = parse_config({"a": 1})            # Arrange + Act
    assert cfg.timeout == 30                # Assert
```

**必须覆盖的边界**：空输入、单元素、极值（0、负数、最大值）、超长输入、类型错误、编码异常、并发重入、超时与部分失败。

**参数化**

```python
@pytest.mark.parametrize("raw,expected", [
    ("1", 1), (" 2 ", 2), ("0x10", 16),
])
def test_parse_int(raw, expected):
    assert parse_int(raw) == expected
```

**时间与随机**：注入时钟、固定随机种子；禁止在断言里依赖当前时间。

**覆盖率命令**

```bash
pytest --cov=src --cov-report=term-missing --cov-branch
coverage report --fail-under=80
```

覆盖率的正确用法是**找没被测到的分支**，不是刷数字。

## 4. 性能剖析命令

| 语言 | 采样剖析 | 内存 | 基准 |
|---|---|---|---|
| Python | cProfile / py-spy top / py-spy record | tracemalloc / memray | timeit / pytest-benchmark |
| Node | --cpu-prof / clinic flame | --heap-prof | tinybench |
| Go | pprof（net/http/pprof 或 runtime/pprof） | pprof heap | testing.B |
| Rust | perf record / cargo flamegraph | valgrind massif | criterion |
| 通用 | perf top / perf record -g | /usr/bin/time -v | hyperfine |

Go 基准模板：

```go
func BenchmarkParse(b *testing.B) {
    data := loadFixture()
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _ = Parse(data)
    }
}
```

基准纪律：固定输入、固定 GOMAXPROCS、关闭无关后台任务、跑 ≥5 次取中位数、记录硬件与版本。

## 5. 优化手段对照

| 瓶颈类型 | 证据 | 首选手段 |
|---|---|---|
| CPU 热点 | 采样显示单函数占比 >30% | 算法优化、减少分配 |
| IO 等待 | 剖析显示阻塞在 read/write | 批处理、缓冲、异步 |
| 数据库 | 慢查询日志、N+1 模式 | 索引、批查询、缓存 |
| 锁竞争 | 剖析显示锁等待 | 减小临界区、分片锁 |
| 内存 | 峰值高、GC 频繁 | 复用对象、流式处理 |
| 启动 | 启动耗时剖析 | 延迟导入、懒加载 |

## 6. 代码审查清单

- 变更范围与声明的问题一致，没有夹带无关改动。
- 错误路径有处理：异常、超时、重试、部分失败、资源释放。
- 边界条件有测试，测试断言具体。
- 命名表达意图，无缩写歧义。
- 无循环内 IO、无 N+1 查询、无未关闭句柄。
- 无硬编码密钥、无敏感信息进日志。
- 公共接口变更已更新文档与类型注解。
- 并发安全：共享状态有保护，或明确标注不可并发使用。

## 7. 常用质量门限

| 指标 | 建议门限 |
|---|---|
| 单文件行数 | ≤500 |
| 单函数行数 | ≤80 |
| 圈复杂度近似值 | ≤15 |
| 函数参数个数 | ≤5 |
| 关键路径分支覆盖 | ≥80% |
| 静态检查告警 | 0（CI 里 -D warnings） |
| 依赖高危漏洞 | 0 |

## 8. 使用边界

性能数字与硬件、数据规模强相关，跨环境结论不可直接搬用；重构前务必确认测试覆盖。
