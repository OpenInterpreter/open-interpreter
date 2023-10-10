<h1 align="center">● Open Interpreter</h1>

<p align="center">
    <a href="https://discord.gg/6p3fD6rBVm">
        <img alt="Discord" src="https://img.shields.io/discord/1146610656779440188?logo=discord&style=flat&logoColor=white"/>
    </a>
    <a href="README_JA.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
    <a href="README_ZH.md"><img src="https://img.shields.io/badge/文档-中文版-white.svg" alt="ZH doc"/></a>
    <a href="README_IN.md"><img src="https://img.shields.io/badge/Hindi-white.svg" alt="IN doc"/></a>
    <img src="https://img.shields.io/static/v1?label=license&message=MIT&color=white&style=flat" alt="License"/>
    <br>
    <br>
    <b>讓語言模型在電腦上執行程式碼。</b><br>
    OpenAI Code Interpreter的開源本地執行實現。<br>
    <br><a href="https://openinterpreter.com">搶先使用桌面應用程式</a>‎ ‎ |‎ ‎ <b><a href="https://docs.openinterpreter.com/">閱讀我們的最新文件</a></b><br>
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

**Open Interpreter** 可讓 LLM 在本地執行程式碼（Python、Javascript、Shell 等）。安裝後執行 `$ interpreter` 即可在終端中透過類似 ChatGPT 的介面與 Open Interpreter 聊天。

它為電腦的通用功能提供了一個自然語言介面：

- 建立和編輯照片、影片、PDF 等。
- 控制 Chrome 瀏覽器進行研究
- 繪製、清理和分析大型資料集
- ......等等。

**⚠️ 注意：程式碼執行前會要求您批准。**

<br>

## 演示

https://github.com/KillianLucas/open-interpreter/assets/63927363/37152071-680d-4423-9af3-64836a6f7b60

#### Google Colab 上提供了互動演示：

[![在Colab中打開](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

#### 還有一個語音介面的實現範例（靈感來自 _Her_）：

[![在Colab中打開](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1NojYGHDgxH6Y1G1oxThEBBb2AtyODBIK)

## 快速上手

```shell
pip install open-interpreter
```

### 終端機

安裝完成後，執行 `interpreter` 即可：

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.chat("Plot AAPL and META's normalized stock prices") # 執行單行程式碼
interpreter.chat() # 開始聊天模式
```

## 與 ChatGPT 程式碼直譯器的比較

OpenAI 釋出的帶有 GPT-4 的 [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) 為使用 ChatGPT 完成實際任務提供了絕佳的機會。

然而，OpenAI 的服務是託管的、閉源的，並且受到嚴格限制：

- 無法上網。
- [預裝軟體包數量有限](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/)。
- 最大上傳量為 100 MB，執行時間限制為 120.0 秒。
- 當執行階段中止時，狀態（以及任何生成的檔案或連結）將被清除。

---

Open Interpreter 透過在本地環境中執行克服了這些限制。它可以完全訪問網際網路，不受時間或檔案大小的限制，可以使用任何軟體包或庫。

它將 GPT-4 程式碼直譯器的強大功能與本地開發環境的靈活性結合在一起。

## 命令

**更新：** 生成器更新（0.1.5）引入了串流：

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### 互動式聊天

要在終端中啟動互動式聊天，可以從命令列執行 `interpreter` ：

```shell
interpreter
```

或 .py 檔案中的 `interpreter.chat()`：

```python
interpreter.chat()
```

**您還可以對每個片段進行互動：**

```python
message = "What operating system are we on?"

for chunk in interpreter.chat(message, display=False, stream=True):
  print(chunk)
```

### 程式化聊天

要實現更精確的控制，可以直接將訊息傳遞給 `.chat(message)`：

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Streams output to your terminal, completes task ...

interpreter.chat("These look great but can you make the subtitles bigger?")

# ...
```

### 開始新的聊天

在 Python 中，Open Interpreter 會記住對話紀錄。如果你想重新開始，可以重新設定：

```python
interpreter.reset()
```

### 儲存和恢復聊天記錄

`interpreter.chat()` 回傳一個資訊列表，可以用 `interpreter.messages = messages` 恢復對話：

```python
messages = interpreter.chat("My name is Killian.") # Save messages to 'messages'
interpreter.reset() # Reset interpreter ("Killian" will be forgotten)

interpreter.messages = messages # Resume chat from 'messages' ("Killian" will be remembered)
```

### 自定系統訊息

你可以檢查和設定 Open Interpreter 的系統資訊，以擴充套件其功能、修改許可權或賦予其更多上下文。

```python
interpreter.system_message += """
Run shell commands with -y so the user doesn't have to confirm them.
"""
print(interpreter.system_message)
```

### 更換語言模型

Open Interpreter 使用 [LiteLLM](https://docs.litellm.ai/docs/providers/) 來連線語言模型

您可以透過設定模型參數來更改模型：

```shell
interpreter --model gpt-3.5-turbo
interpreter --model claude-2
interpreter --model command-nightly
```

在 Python 為物件設定模型

```python
interpreter.model = "gpt-3.5-turbo"
```

[為您的語言找到適合的模型](https://docs.litellm.ai/docs/providers/)

### 在本地端執行 Open Interpreter 

ⓘ **在本地端執行時發生問題？** 閱讀最新 [顯卡設定指南](./docs/GPU.md) and [Windows 設定指南](./docs/WINDOWS.md)。

你可以從命令列以本地模式執行 `interpreter` 來使用 `Code Llama`：

```shell
interpreter --local
```

或者透過執行 `--local`和 repo ID（例如 "tiiuae/falcon-180B"），在**本地**執行任何 Hugging Face 模型：

```shell
interpreter --local --model tiiuae/falcon-180B
```

#### 本地模型參數

您可以輕鬆修改本地執行模型的 "max_tokens"（最大token）和 "context_window"（上下文視窗）（以token為單位）。

較小的上下文視窗將使用較少的 RAM，因此如果 GPU 出現故障，我們建議嘗試使用較短的視窗。

```shell
interpreter --max_tokens 2000 --context_window 16000
```

### 除錯模式

為了幫助貢獻者檢查 Open Interpreter，"--debug "模式是高度冗長的。

你可以使用除錯模式的標誌（`interpreter --debug` ）或在聊天過程中啟用除錯模式：

```shell
$ interpreter
...
> %debug true <- Turns on debug mode

> %debug false <- Turns off debug mode
```

### 互動模式指令

在互動模式下，您可以使用以下命令來增強您的體驗。以下是可用命令列表：

**Available Commands:**  
 • `%debug [true/false]`: 切換除錯模式。不帶引數或使用 "true "時
進入除錯模式。如果使用 "false"，則退出除錯模式。\
 • `%reset`: 重置目前執行階段。\
 • `%undo`: 從訊息歷史中刪除以前的訊息及其回覆。\
 • `%save_message[path]`： 將訊息儲存到指定的 JSON 路徑。如果未提供路徑
則預設為 "messages.json"。\
 • `%load_message [path]`： 從指定的 JSON 路徑載入訊息。如果未提供路徑，則預設為'messages.json'。\
 • `%tokens`： 透過 [LiteLLM 的 `cost_per_token()` 方法](https://docs.litellm.ai/docs/completion/token_usage#2-cost_per_token)，計算目前對話訊息使用的token數量並顯示成本估算。**注意**： 這隻計算目前對話中的訊息，不包括已傳送或已接收並透過 `%undo` 刪除的資訊。\
 • `%help`： 顯示幫助資訊。
### 配置

Open Interpreter 允許你使用 `config.yaml` 檔案設定預設行為。

這提供了一種靈活的方式來配置直譯器，而無需每次都更改命令列引數。

執行以下命令開啟配置檔案：

```
interpreter --config
```

### 安全注意事項

由於生成的程式碼是在本地環境中執行的，因此可能會與您的檔案和系統設定發生互動，從而可能導致意想不到的結果，如資料丟失或安全風險。

**⚠️ Open Interpreter 在執行程式碼前會要求使用者確認。**

你可以執行 "interpreter -y "或設定 "interpreter.auto_run = True "來繞過這一確認，在這種情況下：

- 在請求修改檔案或系統設定的命令時要謹慎。
- 觀察 Open Interpreter，就像觀察一輛自動駕駛汽車，並做好關閉終端結束程序的準備。
- 考慮在 Google Colab 或 Replit 等受限環境中執行 Open Interpreter。這些環境更加獨立，可降低執行任意程式碼的風險。

## 它是如何工作的？

Open Interpreter 為[呼叫函式的語言模型](https://platform.openai.com/docs/guides/gpt/function-calling)配備了一個 `exec()` 函式，該函式接受`語言`（如 "Python "或 "JavaScript"）和`程式碼`來執行。

然後，我們會將模型的資訊、程式碼和您系統的輸出以 Markdown 的形式流式傳輸到終端。

# 貢獻

感謝您的貢獻！我們歡迎社群的參與。

請參閱我們的 [貢獻指南](./CONTRIBUTING.md)，瞭解如何參與的更多詳情。

## 授權

Open Interpreter 採用 MIT 許可授權。您可以使用、複製、修改、分發、轉授權和出售該軟體的副本。

**注**: 本軟體與 OpenAI 無關。

> Having access to a junior programmer working at the speed of your fingertips ... can make new workflows effortless and efficient, as well as open the benefits of programming to new audiences.
>
> — _OpenAI's Code Interpreter Release_

<br>
