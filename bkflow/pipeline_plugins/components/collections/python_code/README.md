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

可以通过Django设置配置以下参数：

```python
# 执行超时时间（秒）
PYTHON_CODE_PLUGIN_TIMEOUT = 30

# 最大代码长度（字符）
PYTHON_CODE_PLUGIN_MAX_LENGTH = 10240
```

## 注意事项

1. **代码长度限制**：代码不能超过配置的最大长度（默认10KB）
2. **执行超时**：代码执行时间不能超过配置的超时时间（默认30秒）
3. **变量映射**：输入变量映射必须是有效的JSON格式
4. **返回值**：建议使用`result`或`output`变量来返回结果
5. **错误处理**：代码执行错误会在`bk_execution_output`中显示

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










