<h1 align="center">● Open Interpreter（开放解释器）</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm"><img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"></a>
    <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"></a>
    <a href="README_ES.md"> <img src="https://img.shields.io/badge/Español-white.svg" alt="ES doc"/></a>
    <a href="README_UK.md"><img src="https://img.shields.io/badge/Українська-white.svg" alt="UK doc"/></a>
    <a href="README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <a href="../README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
    <a href="../LICENSE"><img src="https://img.shields.io/static/v1?label=license&message=AGPL&color=white&style=flat" alt="License"/></a>
    <br>
    <br>
    <b>让语言模型在您的计算机上运行代码。</b><br>
    在本地实现的开源OpenAI的代码解释器。<br>
    <br><a href="https://0ggfznkwh4j.typeform.com/to/G21i9lJ2">获取桌面程序的 Early Access 资格</a>‎ ‎ |‎ ‎ <b><a href="https://docs.openinterpreter.com/">文档</a></b><br>
</p>

<br>

<img alt="local_explorer" src="https://github.com/OpenInterpreter/open-interpreter/assets/63927363/d941c3b4-b5ad-4642-992c-40edf31e2e7a">

<br>
<br>
<p align="center">
这周我们启动了 <strong>Local III</strong>, 你可以使用 <strong><code>--local</code></strong> 来打开 Local Explorer. <a href="https://changes.openinterpreter.com/log/local-iii">了解更多 →</a>
</p>
<br>

```shell
pip install open-interpreter
```

> 没跑起来吗？ 可以读一读我们的[安装指南](https://docs.openinterpreter.com/getting-started/setup).


```shell
interpreter
```

<br>

**Open Interpreter（开放解释器）** 可以让大语言模型（LLMs）在本地运行代码（比如 Python、JavaScript、Shell 等）。安装后，在终端上运行 `$ interpreter` 即可通过类似 ChatGPT 的界面与 Open Interpreter 聊天。

本软件为计算机的通用功能提供了一个自然语言界面，比如：

- 创建和编辑照片、视频、PDF 等
- 控制 Chrome 浏览器进行搜索
- 绘制、清理和分析大型数据集
- ...

**⚠️ 注意：在代码运行前都会要求您批准执行代码。**

<br>

## 演示

### 英文版原视频
https://github.com/OpenInterpreter/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

### 中文版视频

[![Open Interpreter 中文版非官方演示视频](https://res.cloudinary.com/marcomontalbano/image/upload/v1727494759/video_to_markdown/images/youtube--hRwZfZ5oqjA-c05b58ac6eb4c4700831b2b3070cd403.jpg)](https://youtu.be/hRwZfZ5oqjA "Open Interpreter 中文版非官方演示视频")

#### Google Colab 上也提供了交互式演示：

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### 以及一个受 _Her_ 启发的语音界面示例：:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## 快速开始

```shell
pip install open-interpreter
```

### 终端

安装后，运行 `interpreter`：

```shell
interpreter
```

### Python

```python
from interpreter import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices") # 执行单一命令
interpreter.chat() # 开始交互式聊天
```

### GitHub Codespaces

按此仓库 GitHub 页面上的 “,” 键创建 Codespace。过一会，你将收到一个预装了 Open Interpreter 的云虚拟机环境。然后，您可以直接开始与它聊天，并放心确认其执行系统命令，而不必担心损坏系统。

## 与 ChatGPT 的代码解释器比较

OpenAI 发布的 [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) 和 GPT-4 提供了一个与 ChatGPT 完成实际任务的绝佳机会。

但是，OpenAI 的服务是托管的，闭源的，并且受到严格限制：

- 无法访问互联网。
- [预装软件包数量有限](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 允许的最大上传为 100 MB，且最大运行时间限制为 120.0 秒
- 当运行环境中途结束时，之前的状态会被清除（包括任何生成的文件或链接）。

---

Open Interpreter（开放解释器）通过在本地环境中运行克服了这些限制。它可以完全访问互联网，不受运行时间或是文件大小的限制，也可以使用任何软件包或库。

它将 GPT-4 代码解释器的强大功能与本地开发环境的灵活性相结合。

## 命令

**Update:** 在版本 0.1.5 更新时引入了流式处理:

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### 交互式聊天

要在终端中开始交互式聊天，从命令行运行 `interpreter`：

```shell
interpreter
```

或者从.py 文件中运行 `interpreter.chat()`：

```python
interpreter.chat()
```

**你也可以使用流式处理**

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
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
interpreter.messages = []
```

### 保存和恢复聊天

```python
messages = interpreter.chat("My name is Killian.") # 保存消息到 'messages'
interpreter.messages = [] # 重置解释器 ("Killian" 的记忆将被删除)

interpreter.messages = messages # 从 'messages' 恢复聊天 ("Killian" 将被记忆)
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

Open Interpreter 使用[LiteLLM](https://docs.litellm.ai/docs/providers/)连接到语言模型。

您可以通过设置模型参数来更改模型：

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

在 Python 环境下，您需要手动设置模型：

```python
interpreter.llm.model = "gpt-3.5-turbo"
```

### 在本地运行 Open Interpreter（开放解释器）

```shell
interpreter --local
```

[在此处找到模型列表](https://docs.litellm.ai/docs/providers/)

### 本地运行 Open Interpreter

#### 终端

Open Interpreter 可以使用兼容 OpenAI 的服务器在本地运行模型（如 LM Studio、jan.ai、ollama 等）。

只需使用推理服务器的 `api_base` URL 运行 `interpreter`（对于 LM Studio，默认是 `http://localhost:1234/v1`）：

```shell
interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key"
```

或者，也可以在不安装任何第三方软件的情况下，直接通过运行以下命令使用 Llamafile：

```shell
interpreter --local
```

欲了解更详细的指南，请查看 [Mike Bird 的这个视频](https://www.youtube.com/watch?v=CEs51hGWuGU?si=cN7f6QhfT4edfG5H)。

**如何在后台运行 LM Studio。**

1. 下载 [https://lmstudio.ai/](https://lmstudio.ai/)，然后启动它。
2. 选择一个模型，然后点击 **↓ 下载**。
3. 点击左侧的 **↔️** 按钮（💬 的下方）。
4. 在顶部选择你的模型，然后点击 **启动服务器**。

一旦服务器启动后，你就可以开始使用 Open Interpreter 进行对话了。

> **注意：** 本地模式将 `context_window` 设置为 3000，将 `max_tokens` 设置为 1000。如果你的模型有不同的要求，可以手动设置这些参数（参见下文）。

#### Python

我们的 Python 包提供了更多的设置控制。要复制并连接到 LM Studio，请使用以下设置：

```python
from interpreter import interpreter

interpreter.offline = True # 禁用在线功能，如 Open Procedures
interpreter.llm.model = "openai/x" # 告诉 OI 以 OpenAI 的格式发送消息
interpreter.llm.api_key = "fake_key" # LiteLLM 用于与 LM Studio 通信时需要此项
interpreter.llm.api_base = "http://localhost:1234/v1" # 指向任何兼容 OpenAI 的服务器

interpreter.chat()
```

#### 上下文窗口和最大 token

你可以修改本地运行模型的 `max_tokens` 和 `context_window`（以 tokens 为单位）。

对于本地模式，较小的上下文窗口将占用更少的内存，因此如果系统性能不佳或运行缓慢，建议使用较短的窗口（~1000）。确保 `max_tokens` 小于 `context_window`。

```shell
interpreter --local --max_tokens 1000 --context_window 3000
```

### 调试模式

为了帮助贡献者检查和调试 Open Interpreter，`--verbose` 模式提供了详细的日志。

您可以使用 `interpreter --verbose` 来激活调试模式，或者直接在终端输入：

```shell
$ interpreter
...
> %verbose true <- 开启调试模式

> %verbose false <- 关闭调试模式
```

### 交互模式命令

在交互模式下，可以使用以下命令来增强体验。以下是可用命令列表：

**可用命令：**

- `%verbose [true/false]`：切换调试模式。不带参数或使用 `true` 进入调试模式，使用 `false` 退出详细模式。
- `%reset`：重置当前会话的对话内容。
- `%undo`：删除上一条用户消息及 AI 的响应记录。
- `%tokens [prompt]`：(_实验性功能_) 计算下一个提示语作为上下文时将发送的 token 数量，并估算其成本。如果提供了 `prompt` 参数，还可以计算该提示语的 token 数量及预估成本。依赖 [LiteLLM 的 `cost_per_token()` 方法](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token) 来估算成本。
- `%help`：显示帮助信息。

### 配置 / 配置文件

Open Interpreter 允许使用 `yaml` 文件设置默认行为。

这种方式提供了一种灵活的方式来配置解释器，而无需每次更改命令行参数。

运行以下命令打开配置文件目录：

```
interpreter --profiles
```

可以在那里添加 `yaml` 文件，默认的配置文件名为 `default.yaml`。

#### 多配置文件

Open Interpreter 支持多个 `yaml` 文件，允许大家轻松切换配置：

```
interpreter --profile my_profile.yaml
```

## FastAPI 示例服务器

生成器更新使得 Open Interpreter 可以通过 HTTP REST 端点进行控制：

```python
# server.py

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from interpreter import interpreter

app = FastAPI()

@app.get("/chat")
def chat_endpoint(message: str):
    def event_stream():
        for result in interpreter.chat(message, stream=True):
            yield f"data: {result}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/history")
def history_endpoint():
    return interpreter.messages
```

```shell
pip install fastapi uvicorn
uvicorn server:app --reload
```

也可以通过简单运行 `interpreter.server()` 启动与上面相同的服务器。

## Android

有关在 Android 设备上安装 Open Interpreter 的详细指南，请参阅 [open-interpreter-termux 仓库](https://github.com/MikeBirdTech/open-interpreter-termux)。

## 安全提示

由于生成的代码是在本地环境中运行的，因此会与文件和系统设置发生交互，从而可能导致本地数据丢失或安全风险等意想不到的结果。

**⚠️ 所以在执行任何代码之前，Open Interpreter 都会询问用户是否运行。**

您可以运行 `interpreter -y` 或设置 `interpreter.auto_run = True` 来绕过此确认，此时：

- 在运行请求修改本地文件或系统设置的命令时要谨慎。
- 请像驾驶自动驾驶汽车一直握着方向盘一样留意 Open Interpreter，并随时做好通过关闭终端来结束进程的准备，或者打开任务管理器。
- 考虑在 Google Colab 或 Replit 等受限环境中运行 Open Interpreter 的主要原因是这些环境更加独立，从而降低执行任意代码导致出现问题的风险。

## 它是如何工作的？

Open Interpreter 为[函数调用语言模型](https://platform.openai.com/docs/guides/gpt/function-calling)配备了 `exec()` 函数，该函数接受 `编程语言`（如 "Python "或 "JavaScript"）和要运行的 `代码`。

然后，它会将模型的信息、代码和系统的输出以 Markdown 的形式流式传输到终端。

# 离线访问文档

完整的[文档](https://docs.openinterpreter.com/)可以在无需互联网连接的情况下随时访问。

需要使用 [Node.js](https://nodejs.org/zh-cn) ：

- 版本 18.17.0 或任何更新的 18.x.x 版本。
- 版本 20.3.0 或任何更新的 20.x.x 版本。
- 版本 21.0.0 或以上。

安装 [Mintlify](https://mintlify.com/)：

```bash
npm i -g mintlify@latest
```

进入文档目录并运行相应的命令：

```bash
# 假设当前在项目根目录下
cd ./docs

# 运行文档服务器
mintlify dev
```

一个新的浏览器窗口会自动打开，只要文档服务器正在运行，文档就可以通过 [http://localhost:3000](http://localhost:3000) 访问。
# 作出贡献

感谢您对本项目参与的贡献！我们欢迎所有人贡献到本项目里面。

请参阅我们的 [贡献准则](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/CONTRIBUTING.md)，了解如何参与贡献的更多详情。

## 规划

若要预览 Open Interpreter 的未来，请查看[我们的规划](https://github.com/OpenInterpreter/open-interpreter/blob/main/docs/ROADMAP.md) 。

**请注意**：此软件与 OpenAI 无关。

![thumbnail-ncu](https://github.com/OpenInterpreter/open-interpreter/assets/63927363/1b19a5db-b486-41fd-a7a1-fe2028031686)


> 拥有一个像您的指尖一样快速工作的初级程序员...可以使新的工作流程变得轻松高效，同时也能让新的受众群体享受到编程的好处。
>
> — _OpenAI 的代码解释器发布宣传语_

<br>
