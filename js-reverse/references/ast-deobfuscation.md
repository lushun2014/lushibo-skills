# AST 去混淆

> 前提：页面取证和本地复现已经基本跑通。不要在未跑通前就把主要精力放在大规模 AST 清洗上。
> 目标：把混淆脚本还原成可读、可 diff、可长期复用的代码，而不是手工替换几个字符串。

---

## 什么时候用 AST，什么时候别用

| 场景 | 建议 |
|------|------|
| 需要反复重跑、要覆盖整份脚本 | 用 AST（本文） |
| 只要一次签名结果 | 直接 Hook 采样更快，不要上 AST |
| 只有几十行、混淆很浅 | 手工替换 + 格式化更快 |
| 自研 VM / 字节码解释器 | AST 收益低，改做解释器指令 hook |

原则：先 Observe → Capture 拿到运行时证据，再进入 AST 清洗。清洗的目标是"读懂链路"，不是"洗成教科书"。

---

## 常用工具

| 工具 | 定位 | 适用场景 |
|------|------|---------|
| @babel/parser + @babel/traverse + @babel/generator | 事实标准，支持最新语法（可选链、装饰器、TS/JSX） | 首选 |
| @babel/types | 构造、校验、替换节点 | 改写时配合 traverse |
| esprima | 老牌解析器，覆盖 ES2017 左右 | 老脚本、想少装依赖 |
| acorn | 极小、极快，Rollup/webpack 的解析底座 | 只要 AST、不做改写 |
| ast-types + recast | 按类型操作 + 保留原始排版（最小 diff） | 需要改一处但不想整份重排 |
| escodegen | 从 AST 回写代码 | 与 esprima/acorn 搭配 |

安装（任选其一，推荐 babel 全家桶）：

```bash
npm i @babel/parser @babel/traverse @babel/generator @babel/types
```

选择建议：要改写就用 babel；只要统计和定位用 acorn 就够；需要"只动一处、其他保持原样"用 recast。

---

## 典型混淆模式与对应还原手法

### 1. 字符串数组 + 索引取值

特征：

```javascript
var _0x1a2b = ['login', 'sign', 'aHR0cHM6Ly8='];
console[_0x1a2b[1]](_0x1a2b[0]);
```

手法：

1. 定位数组声明：VariableDeclarator，init 是 ArrayExpression 且元素全是 StringLiteral。
2. 遍历 MemberExpression：object 指向该数组标识符、property 是 NumericLiteral 或可静态求值的表达式。
3. 用字符串字面量替换取值表达式，最后删除数组声明（先确认无其它引用）。
4. 数组被 IIFE 旋转过（push/shift 打乱顺序）时，先模拟执行那段 IIFE 求出真实顺序，再做替换。

注意：删除声明前必须确认没有副作用（数组元素本身是函数调用就不要删）。

### 2. 字符串拼接与包装函数

特征：`_0x1('a') + _0x2('b')`、`(function (a) { return a; })('x')`。

手法：对纯函数做常量折叠，用 traverse 的 `path.evaluate()` 判断能否静态求值，能求值就替换成字面量；不能求值的保留（说明它依赖运行时状态，交给 Hook 采样解决）。

### 3. 控制流平坦化

特征：一个大 while/for + switch，配一个状态变量：

```javascript
var _s = '3|0|2|1'.split('|'), _i = 0;
while (true) {
  switch (_s[_i++]) {
    case '0': a(); continue;
    case '1': b(); continue;
  }
}
```

手法：

1. 识别分发变量与 case 序列（字符串 split 的结果或数组字面量）。
2. 按 case 顺序把每个分支的语句抽出来，去掉状态变量赋值，串成顺序语句。
3. 用顺序语句替换整个 while。
4. 反复运行直到 AST 不再变化（不动点迭代）。

要点：先处理干净 case 里的 break/continue 语义再拼接，否则会改变真实控制流。

### 4. 死代码注入

特征：`if (false) {...}`、`if (!![]) {...}`、永不抛出的 try/catch、无引用的空函数。

手法：用 `path.evaluate()` 求条件；恒 false 删除 consequent，恒 true 只保留 consequent；再清理无引用的函数声明与变量。注意保留可能有副作用的表达式语句（如赋值、调用）。

### 5. 成员表达式还原

特征：`window['document']['cookie']`、`_0x1['split'](...)`。

手法：computed MemberExpression 的 property 是 StringLiteral 且内容是合法标识符（`/^[A-Za-z_$][A-Za-z0-9_$]*$/`）时，改成 Identifier 并把 computed 置为 false；含 `-`、空格、关键字的保持原样，否则会生成非法代码。

### 6. 十六进制 / Unicode 转义还原

特征：`\x68\x65\x6c\x6c\x6f`、`\u0068\u0065\u006c\u006c\u006f`、`'\x61' === 'a'`。

手法：解析成 AST 后 StringLiteral 的 value 已经是解码后的真实值，直接使用 value 并用 generator 回写即可。**不要用正则替换源码文本**——正则很难正确处理转义边界、模板字符串和正则字面量。

### 7. 其它常见项

- 逗号表达式串联：拆成独立表达式语句，便于阅读与后续 pass。
- 数组/对象字面量拆包：单次使用的常量对象可以直接内联到使用点。
- 代理函数（只做转发）：内联掉，减少噪声。
- 大整数与位运算混淆：先做常量折叠，再人工判断是否是哈希/校验算法。

---

## 可运行示例（字符串数组 + 成员表达式）

```javascript
// 用法: node deob.js input.js > output.js
const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const generate = require('@babel/generator').default;
const t = require('@babel/types');

const src = fs.readFileSync(process.argv[2], 'utf8');
const ast = parser.parse(src, { sourceType: 'unambiguous', errorRecovery: true });

// 第 1 步：收集字符串数组（变量名 -> 字符串列表）
const arrays = new Map();
traverse(ast, {
  VariableDeclarator(path) {
    const { id, init } = path.node;
    if (!t.isIdentifier(id) || !t.isArrayExpression(init)) return;
    const items = init.elements.map((el) => (t.isStringLiteral(el) ? el.value : null));
    if (items.length && items.every((v) => typeof v === 'string')) arrays.set(id.name, items);
  },
});

// 第 2 步：把 arr[1] 这类取值替换成字符串字面量
traverse(ast, {
  MemberExpression(path) {
    const { object, property, computed } = path.node;
    if (!computed || !t.isIdentifier(object) || !arrays.has(object.name)) return;
    if (!t.isNumericLiteral(property)) return;
    const value = arrays.get(object.name)[property.value];
    if (typeof value !== 'string') return;
    path.replaceWith(t.stringLiteral(value));
  },
});

// 第 3 步：a['b'] -> a.b（只处理合法标识符）
traverse(ast, {
  MemberExpression(path) {
    const { property, computed } = path.node;
    if (!computed || !t.isStringLiteral(property)) return;
    if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(property.value)) return;
    path.node.property = t.identifier(property.value);
    path.node.computed = false;
  },
});

// 第 4 步：清理已无引用的数组声明
traverse(ast, {
  VariableDeclarator(path) {
    if (!t.isIdentifier(path.node.id) || !arrays.has(path.node.id.name)) return;
    const binding = path.scope.getBinding(path.node.id.name);
    if (binding && !binding.referenced) path.remove();
  },
});

process.stdout.write(generate(ast, { comments: true, compact: false }).code + '\n');
```

---

## 注意事项

- **不动点迭代**：每个 pass 跑完重新解析，直到输出不再变化（通常 3-5 轮，设上限 10 轮防死循环）。
- **不要用正则改源码**：字符串转义、模板字符串、正则字面量都会被打坏；AST 的 value 已经是解码结果。
- **一次只加一个 pass**：清洗后语义变了就回退上一轮快照，逐个 pass 定位问题。
- **保留注释与格式**：generate 时开 comments，方便和页面原始脚本逐行对照。
- **必须做 round-trip 校验**：清洗后的签名函数对同一输入要产出与页面采样完全一致的输出，不一致说明 pass 改错了语义。
- **证据留档**：原始脚本、采样记录、每轮清洗产物分开存放，保证任何一步可回溯。
- **自研 VM 及时止损**：遇到字节码解释器，AST 阶段收益很低，转去做解释器指令级 hook 更划算。

---

## 相关章节

- 运行时采样与插桩：`references/instrumentation.md`
- 本地复现：`references/local-rebuild.md`
- 补环境：`references/env-patching.md`
- 走不通时的回退路径：`references/fallbacks.md`
