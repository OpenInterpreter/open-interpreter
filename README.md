Lightweight terminal interface for OpenAI's code interpreter that executes code locally.

Lightweight, open-source Code Interpreter implementation that installs new packages and run locally.

Open-source, GPT-4 powered Code Interpreter that installs new packages and runs locally.

Use OpenAI's Code Interpreter from your terminal.

OpenAI's Code Interpreter in Python. Lightweight, open-source.

Open-source ChatGPT in your terminal that can execute code.

Open-source Code Interpreter in your terminal that runs locally.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

# Open Interpreter

Open Interpreter is a lightweight, open-source implementation of OpenAI's code interpreter that runs code locally.

```python
interpreter.chat("Reverse all videos in my /videos folder.")
```

## Features

- Provides GPT-4 access to an `exec(code)` function.
- Installs packages and executes code in your environment.
- Streams messages, code, and outputs directly to your terminal.

## Features

- Generated code runs locally.
- Uses `pip` and `apt-get` to extend itself.
- Interactive, streaming chat inside your terminal.

The main advantage of Open Interpreter over ChatGPT's interpreter is its local operation. Executing generated code locally bypasses multiple limitations:
- Internet access (runs `!pip` and `!apt-get` as needed)
- No filesize or timeout limits

It's Code Interpreter in your terminal.

## Quick Start

```python
!pip install open-interpreter

import interpreter
interpreter.api_key = "<your_openai_api_key>"

# Start an interactive chat in your terminal
interpreter.chat()
```

## Commands

For more precise control, you can pass your message directly to the `chat()` function:

```python
chat = interpreter.chat("Add subtitles to all videos in /videos.")
# ... Streams output to your terminal, completes task ...
chat = interpreter.chat("These look great but can you make the subtitles bigger?")
# ...
```

Passing a message into `.chat()` appends it to your existing conversation. If you want to start fresh, you can reset the interpreter:

```python
interpreter.reset()
```

And optionally load a chat which was previously returned by `interpreter.chat()`:

```python
interpreter.load(chat)
```

## Use Cases

Think of it as having an open conversation with a seasoned programmer, ready to execute code snippets and accomplish tasks at your behest. 

1. Add subtitles to all videos in a folder.
2. Perform facial detection on an image or video, and optionally blur all faces.
3. Utilize an external API to execute novel operations.
4. Process or edit a batch of documents.
5. Download videos from the internet using packages like youtube-dlp.

## Comparison to ChatGPT Code Interpreter

OpenAI's recent release of [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) with GPT-4 presents a fantastic opportunity for developers (and non developers) to let GPT run code and learn from its output. However, OpenAI's service is hosted, closed, and comes with restrictions on operation time, file sizes, and a limited set of pip packages. It also lacks internet access.

---

Open Interpreter overcomes these limitations by running in a stateful Jupyter notebook on your local environment. It has full access to the internet, isn't restricted by time or file size, and can utilize any package you want to install. It combines the power of GPT-4 with the flexibility of your local development environment.

The online code interpreter offered by OpenAI via ChatGPT shares some features with Open Interpreter, such as executing code. However, there are notable differences. The online interpreter can only operate for a maximum of 120 seconds and has file size restrictions. It also has a limited selection of pip packages, does not have internet access, and operates on a cloud server.

In contrast, Open Interpreter, being locally run, doesn't have these limitations. It can install any necessary packages, has access to the internet, can handle more extensive operations, and operates like a stateful Jupyter Notebook.

## How Does it Work?

Open Interpreter equips the [function-calling](https://platform.openai.com/docs/guides/gpt/function-calling) version of GPT-4 with the `exec()` function.

We then stream the model's messages, code, and your system's outputs to the terminal as Markdown.

## Contributing

Contributions to Open Interpreter are welcome. Check out our [CONTRIBUTING](CONTRIBUTING.md) guide for more information.

## License

Open Interpreter is licensed under the MIT License.

**Note**: This software is not affiliated with OpenAI.