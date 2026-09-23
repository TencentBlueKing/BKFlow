# Python代码插件节点使用说明

## 概述

Python代码插件节点允许在工作流中安全地执行Python代码。该插件使用RestrictedPython提供受限的执行环境，确保代码执行的安全性。

## 功能特性

- ✅ 安全的代码执行环境（基于RestrictedPython）
- ✅ 支持访问工作流变量
- ✅ 支持返回计算结果
- ✅ 执行超时保护（默认30秒）
- ✅ 代码长度限制（默认10KB）
- ✅ 禁止危险操作（文件系统、网络、系统命令等）

## 安全限制

### 禁止的操作

- ❌ 导入危险模块：`os`, `sys`, `subprocess`, `socket`, `urllib`, `requests`等
- ❌ 使用危险函数：`eval()`, `exec()`, `compile()`, `open()`等
- ❌ 文件系统操作
- ❌ 网络请求
- ❌ 系统命令执行
- ❌ 进程和线程操作

### 允许的操作

- ✅ 基本数据类型操作（int, str, list, dict等）
- ✅ 数学运算和逻辑运算
- ✅ 字符串处理
- ✅ 列表和字典操作
- ✅ JSON序列化/反序列化（通过json模块）
- ✅ 基本的内置函数（len, range, sorted, min, max等）

## 使用方法

### 1. 基本用法

在"Python代码"输入框中输入要执行的代码：

```python
# 简单计算
result = 10 + 20
```

### 2. 使用输入变量

在"输入变量映射"中配置变量映射（JSON格式）：

```json
{
  "num1": "${input_number1}",
  "num2": "${input_number2}"
}
```

然后在代码中使用这些变量：

```python
# 使用输入变量
result = num1 + num2
```

### 3. 返回结果

可以通过设置`result`或`output`变量来返回结果：

```python
# 方式1：使用result变量
result = num1 * num2

# 方式2：使用output变量（返回字典）
output = {
    "sum": num1 + num2,
    "product": num1 * num2,
    "message": "计算完成"
}
```

### 4. 数据处理示例

```python
# 处理列表数据
data_list = input_data
filtered = [x for x in data_list if x > 10]
result = {
    "count": len(filtered),
    "items": filtered,
    "average": sum(filtered) / len(filtered) if filtered else 0
}
```

### 5. 使用JSON模块

```python
import json

# 解析JSON字符串
data = json.loads(json_string)

# 序列化为JSON
result = json.dumps({"key": "value"})
```

## 输出说明

插件执行后会输出两个变量：

1. **bk_execution_result**：代码的执行结果（result或output变量的值）
2. **bk_execution_output**：标准输出和错误输出的文本

## 配置选项

可以通过同名部署环境变量配置以下参数（均为整数）：

```python
# 准备阶段和 main 执行阶段各自的超时时间（秒）
PYTHON_CODE_PLUGIN_TIMEOUT = 30

# 等待并发名额的超时时间（秒）；未配置时跟随 PYTHON_CODE_PLUGIN_TIMEOUT
PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT = 30

# 最大代码长度（字符）
PYTHON_CODE_PLUGIN_MAX_LENGTH = 10240

# 单个代码执行子进程的内存限制（MB）
PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB = 256

# 每个 Worker 同时运行的代码执行子进程数
PYTHON_CODE_PLUGIN_MAX_CONCURRENT_PROCESSES = 4

# 子进程返回给 Worker 的跨进程编码后最大响应大小（字节）；0 表示不额外限制
PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES = 0
```

## 注意事项

1. **代码长度限制**：代码不能超过配置的最大长度（默认10KB）
2. **执行超时**：排队使用独立的 `PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT`；获取名额后，输入编码、子进程启动和编译共用准备阶段预算；`main` 开始后获得独立执行预算（包含返回结果编码和传输）。准备和执行阶段各使用 `PYTHON_CODE_PLUGIN_TIMEOUT`（默认各30秒），因此节点总耗时可能超过30秒。父进程同时读写子进程管道，收到执行开始标记后切换期限；`main` 未开始时报告执行等待超时
3. **进程隔离**：代码在独立子进程内执行，超时后子进程会被终止
4. **并发限制**：每个 Worker 默认4个执行名额，从输入编码开始持有，直到子进程回收及父进程 JSON/协议解码完成后释放；超出额度的任务等待可用名额。这不等于修改 Celery Worker 的线程并发数
5. **变量映射**：输入变量映射必须是有效的JSON格式
6. **返回值**：支持 JSON 基础类型，以及 `complex`、`datetime`、`date`、`time`、`timedelta`、`Decimal`、`Fraction`、`UUID`、`set`、`frozenset`、`bytes`、`bytearray`、`tuple`、`range`、`deque`、`Counter`、`OrderedDict` 和 `defaultdict`。`defaultdict` 的默认工厂支持 `None`、`bool/int/float/complex/str/bytes/bytearray/list/dict/tuple/set/frozenset`，以及 `collections.Counter/OrderedDict/defaultdict/deque`、`decimal.Decimal`、`fractions.Fraction`、`datetime.timedelta`。未知工厂仅在整个选定输出可被旧引擎 JSON 保存时降级为普通字典；输入或需要 pickle 保型的输出仍明确报错，不传输任意 callable。其他容器子类仍按对应基础类型返回，不支持任意自定义对象
7. **输出筛选和响应大小**：配置 `bk_output_key` 时，先在子进程中取出选定字段，再编码和检查响应大小，未选中的字段不参与编码。默认不新增响应大小门槛，以兼容存量大结果；内存限制、执行超时和并发限制仍生效。如需设置10MB响应上限，配置 `PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES=10485760`，超限错误会显示完整响应编码后的实际大小与上限
8. **成功日志**：记录结果类型和可获取的长度；字符串/字节只预览前128个元素，容器不展开。节点实际输出保持完整
9. **错误处理**：代码执行错误会在`bk_execution_output`中显示

发布前需在实际 Engine Pod 中验证突发并发、队列等待时间和内存水位。默认4个执行名额仍可能使等待超过队列期限的节点失败；并发数和队列期限应结合存量流量调整。响应上限默认关闭时，大结果的编码、传输和父进程解析会增加内存消耗，启用上限前应先核查存量结果大小。被旧实现降低进程资源硬限制的 Worker 无法自行恢复，部署后需滚动重启现有 er-e Pod。

## 父子进程协议与引擎存储

上述类型支持说明的是父子进程边界。引擎持久化继续使用原来的“先 JSON、失败后 pickle”规则：例如字符串键的 `Counter/defaultdict` 通常存为 JSON，下游恢复为普通 `dict`；元组键等使 JSON 无法编码的场景才走 pickle，可能保留容器类型和工厂。本 PR 不承诺所有结果经引擎存储后仍保型。

日期/时间支持保留 `datetime.timezone` 的自定义名称、标准库 `ZoneInfo` 的时区标识和夏令时规则，以及 `pytz` 已定位的时差和时区类型；其他自定义时区明确报错。协议保留正常中文的 UTF-8 紧凑编码，对含代理字符的参数/返回值使用受控字符串标记保留原始码点，对诊断信息中的代理字符使用 JSON 转义，避免编码失败、字符合并或子进程响应异常退出。

## 常见问题

### Q: 为什么不能导入某些模块？

A: 为了安全考虑，插件禁止导入可能造成安全风险的模块。如果需要特定功能，请联系管理员评估是否可以添加。

### Q: 如何调试代码？

A: 可以使用`print()`函数输出调试信息，输出会显示在`bk_execution_output`中。

### Q: 代码执行超时怎么办？

A: 优化代码逻辑，减少计算量，或者联系管理员增加超时时间配置。

### Q: 可以访问数据库吗？

A: 不可以。为了安全考虑，插件不允许访问数据库或其他外部资源。

## 安全建议

1. 只执行可信的代码
2. 避免执行复杂的计算逻辑
3. 定期审查代码内容
4. 使用变量映射而不是硬编码值
5. 合理设置超时时间

## 技术支持

如有问题或建议，请联系开发团队。





