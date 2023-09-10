<h1 align="center">● 开放解释器</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm"><img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"></a>
  <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"></a>
    <a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
  <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License">
<br>
    <b>让语言模型在您的计算机上运行代码。</b><br>
    OpenAI的代码解释器的开源、本地运行实现。<br>
    <br><a href="https://openinterpreter.com">获取桌面应用程序的早期访问权限。</a><br>
</p>

<br>

![poster](https://github.com/KillianLucas/open-interpreter/assets/63927363/08f0d493-956b-4d49-982e-67d4b20c4b56)

<br>

```shell
pip install open-interpreter
```

```shell
interpreter
```

<br>

**开放解释器** 允许LLMs在本地运行代码（Python、Javascript、Shell等）。安装后，通过在终端中运行 `$ interpreter`，您可以通过类似ChatGPT的界面与开放解释器聊天。

这为您的计算机的通用功能提供了自然语言界面：

- 创建和编辑照片、视频、PDF等。
- 控制Chrome浏览器进行研究
- 绘制、清理和分析大型数据集
- ...等等。

**⚠️ 注意：在代码运行之前，您会被要求批准。**

<br>

## 演示

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colab上也提供了交互式演示：

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

## 快速开始

```shell
pip install open-interpreter
```

### 终端

安装后，简单地运行 `interpreter`：

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices") # 执行单一命令
interpreter.chat() # 开始交互式聊天
```

## 与ChatGPT的代码解释器比较

OpenAI发布的 [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) 和 GPT-4 提供了一个与ChatGPT完成实际任务的绝佳机会。

但是，OpenAI的服务是托管的，闭源的，并且受到严格限制：
- 没有互联网访问。
- [预装包限制](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 最大上传100 MB，运行时间限制为120.0秒。
- 当环境死亡时，状态会被清除（以及任何生成的文件或链接）。

---

开放解释器通过在您的本地环境上运行来克服这些限制。它可以完全访问互联网，不受时间或文件大小的限制，并可以使用任何包或库。

这结合了GPT-4的代码解释器的功能和您的本地开发环境的灵活性。

## 命令

### 交互式聊天

要在终端中开始交互式聊天，从命令行运行 `interpreter`：

```shell
interpreter
```

或者从.py文件中运行 `interpreter.chat()`：

```python
interpreter.chat()
```

### 程序化聊天

为了更精确的控制，您可以直接传递消息给 `.chat(message)`：

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Streams output to your terminal, completes task ...

interpreter.chat("These look great but can you make the subtitles bigger?")

# ...
```

### 开始新的聊天

在Python中，开放解释器会记住对话历史。如果您想重新开始，您可以重置它：

```python
interpreter.reset()
```

### 保存和恢复聊天

`interpreter.chat()` 当 return_messages=True 时返回一系列消息，它可以被用来通过 `interpreter.load(messages)` 恢复对话：

```python
messages = interpreter.chat("My name is Killian.", return_messages=True) # 保存消息到 'messages'
interpreter.reset() # 重置解释器 ("Killian" 将被遗忘)

interpreter.load(messages) # 从 'messages' 恢复聊天 ("Killian" 将被记住)
```

### 自定义系统消息

您可以查看和配置 Open Interpreter 的系统消息以扩展其功能、修改权限或给它更多上下文。

```python
interpreter.system_message += """
使用 -y 运行 shell 命令，这样用户就不必确认它们。
"""
print(interpreter.system_message)
```

### 更改模型

ⓘ **在本地运行时遇到问题？** 阅读我们的新 [GPU设置指南](/docs/GPU.md) 和 [Windows设置指南](/docs/WINDOWS.md)。

您可以从命令行在本地模式下运行 `interpreter` 以使用 `Code Llama`：

```shell
interpreter --local
```

对于 `gpt-3.5-turbo`，使用快速模式：

```shell
interpreter --fast
```

在 Python 中，您需要手动设置模型：

```python
interpreter.model = "gpt-3.5-turbo"
```

### Azure 支持

要连接到 Azure 部署，`--use-azure` 标志将指导您完成此设置：

```
interpreter --use-azure
```

在 Python 中，设置以下变量：

```
interpreter.use_azure = True
interpreter.api_key = "your_openai_api_key"
interpreter.azure_api_base = "your_azure_api_base"
interpreter.azure_api_version = "your_azure_api_version"
interpreter.azure_deployment_name = "your_azure_deployment_name"
interpreter.azure_api_type = "azure"
```

### 调试模式

为了帮助贡献者查看 Open Interpreter，`--debug` 模式非常详细。

您可以通过使用它的标志激活调试模式（`interpreter --debug`），或在聊天中间：

```
$ interpreter
...
> %debug # <- 开启调试模式
```

### 使用 .env 配置

Open Interpreter 允许您使用 .env 文件设置默认行为。这提供了一种灵活的方式，无需每次更改命令行参数即可配置解释器。

这是一个 .env 配置的示例：

```
INTERPRETER_CLI_AUTO_RUN=False
INTERPRETER_CLI_FAST_MODE=False
INTERPRETER_CLI_LOCAL_RUN=False
INTERPRETER_CLI_DEBUG=False
INTERPRETER_CLI_USE_AZURE=False
```

您可以在 .env 文件中修改这些值，以更改 Open Interpreter 的默认行为。

## 安全通知

由于生成的代码在您的本地环境中执行，它可以与您的文件和系统设置互动，可能导致数据丢失或安全风险等意外结果。

**⚠️ 在执行代码之前，Open Interpreter 会要求用户确认。**

您可以运行 `interpreter -y` 或设置 `interpreter.auto_run = True` 来绕过此确认，此时：

- 在请求修改文件或系统设置的命令时要小心。
- 观察 Open Interpreter 就像观察自动驾驶汽车，并准备通过关闭终端来结束进程。
- 考虑在 Google Colab 或 Replit 这样的受限环境中运行 Open Interpreter。这些环境更加孤立，减少了执行任意代码的风险。

## 它是如何工作的？

Open Interpreter 配备了一个 [函数调用语言模型](https://platform.openai.com/docs/guides/gpt/function-calling) 和一个 `exec()` 函数，它接受一个 `language`（如 "python" 或 "javascript"）和要运行的 `code`。

我们然后将模型的消息、代码和您的系统输出流式传输到终端作为 Markdown。

# 贡献

感谢您对贡献的兴趣！我们欢迎社区的参与。

请查看我们的 [贡献指南](/docs/contributing.md) 以获取更多关于如何参与的详情。

## 许可

Open Interpreter 根据 MIT 许可证授权。您被允许使用、复制、修改、分发、再许可并出售软件副本。

**注意**：此软件与 OpenAI 无关。
> 有一个速度如指尖般快速工作的初级程序员的访问权限... 可以使新的工作流程变得轻而易举和高效，同时还可以为新的受众带来编程的好处。
>
> — _OpenAI的代码解释器发布_

<br>
<br>
<br>

**注意**：此翻译是由人工智能创建的。我们确信它包含了一些不准确之处。
请通过为我们提供您的纠正意见的拉取请求，帮助Open Interpreter走向世界各地！
