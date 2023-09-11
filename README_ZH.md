<h1 align="center">● Open Interpreter（开放解释器）</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm"><img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"></a>
  <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"></a>
    <a href="README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
  <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License">
    <br>
    <br>
    <b>让语言模型在您的计算机上运行代码。</b><br>
    在本地实现开源的OpenAI的代码解释器。<br>
    <br><a href="https://openinterpreter.com">登记以提前获取Open Interpreter（开放解释器）桌面应用程序</a><br>
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

**Open Interpreter（开放解释器）** 可以让大语言模型（LLMs）在本地运行代码（比如 Python、JavaScript、Shell 等）。安装后，在终端上运行 `$ interpreter` 即可通过类似 ChatGPT 的界面与 Open Interpreter 聊天。

本软件为计算机的通用功能提供了一个自然语言界面，比如：

-   创建和编辑照片、视频、PDF 等
-   控制 Chrome 浏览器进行搜索
-   绘制、清理和分析大型数据集
-   ...

**⚠️ 注意：在代码运行前都会要求您批准执行代码。**

<br>

## 演示

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colab 上也提供了交互式演示：

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

## 与 ChatGPT 的代码解释器比较

OpenAI 发布的 [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) 和 GPT-4 提供了一个与 ChatGPT 完成实际任务的绝佳机会。

但是，OpenAI 的服务是托管的，闭源的，并且受到严格限制：

-   无法访问互联网。
-   [预装软件包数量有限](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
-   允许的最大上传为 100 MB，且最大运行时间限制为 120.0 秒
-   当运行环境中途结束时，之前的状态会被清除（包括任何生成的文件或链接）。

---

Open Interpreter（开放解释器）通过在本地环境中运行克服了这些限制。它可以完全访问互联网，不受运行时间或是文件大小的限制，也可以使用任何软件包或库。

它将 GPT-4 代码解释器的强大功能与本地开发环境的灵活性相结合。

## 命令

### 交互式聊天

要在终端中开始交互式聊天，从命令行运行 `interpreter`：

```shell
interpreter
```

或者从.py 文件中运行 `interpreter.chat()`：

```python
interpreter.chat()
```

### 程序化聊天

为了更精确的控制，您可以通过 `.chat(message)` 直接传递消息 ：

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Streams output to your terminal, completes task ...

interpreter.chat("These look great but can you make the subtitles bigger?")

# ...
```

### 开始新的聊天

在 Python 中，Open Interpreter 会记录历史对话。如果你想从头开始，可以进行重置：

```python
interpreter.reset()
```

### 保存和恢复聊天

当 `return_messages=True` 时，`interpreter.chat()` 会返回一个信息列表，可以用`interpreter.load(messages)` 来恢复之前的对话：

```python
messages = interpreter.chat("My name is Killian.", return_messages=True) # 保存消息到 'messages'
interpreter.reset() # 重置解释器 ("Killian" 将被遗忘)

interpreter.load(messages) # 从 'messages' 恢复聊天 ("Killian" 将被记住)
```

### 自定义系统消息

你可以检查和配置 Open Interpreter 的系统信息，以扩展其功能、修改权限或赋予其更多上下文。

```python
interpreter.system_message += """
使用 -y 运行 shell 命令，这样用户就不必确认它们。
"""
print(interpreter.system_message)
```

### 更改模型

在 `gpt-3.5-turbo` 下，使用快速模式：

```shell
interpreter --fast
```

在 Python 环境下，您需要手动设置模型：

```python
interpreter.model = "gpt-3.5-turbo"
```

### 在本地运行 Open Interpreter（开放解释器）

ⓘ **本地运行遇到问题？** 请阅读我们最新的 [GPU 设置指南](/docs/GPU.md)和 [Windows 设置指南](/docs/WINDOWS.md)。

你可以从命令行以本地模式运行 `interpreter` 来使用 `Code Llama`：

```shell
interpreter --local
```

或使用其 HuggingFace 的 repo ID（如 "tiiuae/falcon-180B"）来**本地**运行任何 HuggingFace 模型：

```shell
interpreter --model tiiuae/falcon-180B
```

### Azure 支持

要连接到 Azure 部署，请使用 `--use-azure` 以进行设置：

```shell
interpreter --use-azure
```

在 Python 中，需要设置以下变量：

```
interpreter.use_azure = True
interpreter.api_key = "your_openai_api_key"
interpreter.azure_api_base = "your_azure_api_base"
interpreter.azure_api_version = "your_azure_api_version"
interpreter.azure_deployment_name = "your_azure_deployment_name"
interpreter.azure_api_type = "azure"
```

### 调试模式

为了帮助贡献者检查和调试 Open Interpreter，`--debug` 模式提供了详细的日志。

您可以使用 `interpreter --debug` 来激活调试模式，或者直接在聊天时输入：

```shell
$ interpreter
...
> %debug # <- 开启调试模式
```

### 使用 .env 配置

Open Interpreter 允许你使用 .env 文件设置默认行为。这提供了一种灵活的方式来配置 Open Interpreter，而无需每次都手动更改命令行参数。

下面是一个 .env 的配置示例：

```
INTERPRETER_CLI_AUTO_RUN=False
INTERPRETER_CLI_FAST_MODE=False
INTERPRETER_CLI_LOCAL_RUN=False
INTERPRETER_CLI_DEBUG=False
INTERPRETER_CLI_USE_AZURE=False
```

您可以修改 .env 文件中的这些值，以更改 Open Interpreter 的默认行为。

## 安全提示

由于生成的代码是在本地环境中运行的，因此会与文件和系统设置发生交互，从而可能导致本地数据丢失或安全风险等意想不到的结果。

**⚠️ 所以在执行任何代码之前，Open Interpreter 都会要求用户确认是否运行。**

您可以运行 `interpreter -y` 或设置 `interpreter.auto_run = True` 来绕过此确认，此时：

-   在运行请求修改本地文件或系统设置的命令时要谨慎。
-   请像驾驶自动驾驶汽车一样留意 Open Interpreter，并随时做好通过关闭终端来结束进程的准备。
-   考虑在 Google Colab 或 Replit 等受限环境中运行 Open Interpreter。主要是这些环境更加独立，从而降低执行任意代码导致出现问题的风险。

## 它是如何工作的？

Open Interpreter 为[函数调用语言模型](https://platform.openai.com/docs/guides/gpt/function-calling)配备了 `exec()` 函数，该函数接受 `编程语言`（如 "Python "或 "JavaScript"）和要运行的 `代码`。

然后，它会将模型的信息、代码和系统的输出以 Markdown 的形式流式传输到终端。

# 作出贡献

感谢您对本项目参与的贡献！我们欢迎所有人贡献到本项目里面。

请参阅我们的 [贡献准则](/docs/contributing.md)，了解如何参与贡献的更多详情。

## 许可证

Open Interpreter 采用 MIT 许可授权。您可以使用、复制、修改、分发、转授权和出售该软件的副本。

**请注意**：此软件与 OpenAI 无关。

> 拥有一个像您的指尖一样快速工作的初级程序员...可以使新的工作流程变得轻松高效，同时也能让新的受众群体享受到编程的好处。
>
> — _OpenAI 的代码解释器发布_

<br>
