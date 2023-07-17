# Open Interpreter

A minimal, open-source implementation of OpenAI's code interpreter.

```python
interpreter.chat("Add subtitles to video.mp4 on my Desktop.")
```
```
Understood. First, let's check if any speech-to-text libraries are installed...
```

<br>

![Banner Image](https://github.com/KillianLucas/open-interpreter/blob/main/misc/banner.png)

<p align="right">
    <sub><i>Illustration by Open Interpreter. Inspired by <a href="https://rubywjchen.com/">Ruby Chen's</a> GPT-4 artwork.</i></sub>
</p>

## What is this?

<br>

> Having access to a junior programmer working at the speed of your fingertips ... can make new workflows effortless and efficient, as well as open the benefits of programming to new audiences. - [OpenAI code interpreter release](https://openai.com/blog/chatgpt-plugins#code-interpreter)

<br>

**Open Interpreter** lets GPT-4 execute Python code locally. Running `$ interpreter` opens a ChatGPT-like interface to this model in your terminal.

This extends GPT-4 with Python's general-purpose capabilities:

- Create and edit photos, videos, PDFs, etc.
- Run `selenium` to control a Chrome browser.
- Convert DNA to proteins with `biopython`.
- ...etc.

[How does this compare to OpenAI's code interpreter?](https://github.com/KillianLucas/open-interpreter#comparison-to-chatgpts-code-interpreter)

<br>

## Demo Notebook

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

## Features

- Generated code runs locally.
- Uses `pip` and `apt-get` to extend itself.
- Interactive, streaming chat inside your terminal.

## Quick Start

```shell
pip install open-interpreter
```

### Terminal

After installation, set your `OPENAI_API_KEY` environment variable, then simply run `interpreter`:

```shell
interpreter
```

### Python

```python
import interpreter

interpreter.api_key = "<openai_api_key>"
interpreter.chat() # Starts an interactive chat
```

## Comparison to ChatGPT's Code Interpreter

OpenAI's recent release of [Code Interpreter](https://openai.com/blog/chatgpt-plugins#code-interpreter) with GPT-4 presents a fantastic opportunity to accomplish real-world tasks with ChatGPT.

However, OpenAI's service is hosted, closed-source, and heavily restricted:
- No internet access.
- [Limited set  of pre-installed packages](https://wfhbrian.com/mastering-chatgpts-code-interpreter-list-of-python-packages/).
- 100 MB maximum upload, 120.0 second runtime limit.
- State is cleared (along with any generated files or links) when the environment dies.

---

Open Interpreter overcomes these limitations by running in a stateful Jupyter notebook on your local environment. It has full access to the internet, isn't restricted by time or file size, and can utilize any package or library.

**Open Interpreter combines the power of GPT-4's Code Interpreter with the flexibility of your local development environment.**

## Commands

#### Interactive Chat

To start an interactive chat in your terminal, either run `interpreter` from the command line:

```shell
interpreter
```

Or `interpreter.chat()` from a .py file:

```python
interpreter.chat()
```

#### Programmatic Chat

For more precise control, you can pass messages directly to `.chat(message)`:

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Streams output to your terminal, completes task ...

interpreter.chat("These look great but can you make the subtitles bigger?")

# ...
```

#### Start a New Chat

In Python, Open Interpreter remembers conversation history. If you want to start fresh, you can reset it:

```python
interpreter.reset()
```

#### Save and Restore Chats

`interpreter.chat()` returns a List of messages, which can be restored with `interpreter.load(messages)`:

```python
messages = interpreter.chat() # Save chat to 'messages'
interpreter.reset() # Reset interpreter

interpreter.load(messages) # Resume chat from 'messages'
```

#### Customize System Message

You can inspect and configure Open Interpreter's system message to extend its functionality, modify permissions, or give it more context.

```python
interpreter.system_message += """
Run shell commands with -y so the user doesn't have to confirm them.
"""
print(interpreter.system_message)
```

## How Does it Work?

Open Interpreter equips a [function-calling GPT-4](https://platform.openai.com/docs/guides/gpt/function-calling) with the `exec()` function.

We then stream the model's messages, code, and your system's outputs to the terminal as Markdown.

Only the last `model_max_tokens` of the conversation are shown to the model, so conversations can be any length, but older messages may be forgotten.

## Safety Notice

Since generated code is executed in your local environment, it can interact with your files and system settings, potentially leading to unexpected outcomes like data loss or security risks.

- Be cautious when requesting commands that modify files or system settings.
- Watch Open Interpreter like a self-driving car, and be prepared to end the process by closing your terminal.
- Regularly back up your data and work in a virtual environment.

## Contributing

As an open-source project, we are extremely open to contributions, whether it be in the form of a new feature, improved infrastructure, or better documentation.

## License

Open Interpreter is licensed under the MIT License. You are permitted to use, copy, modify, distribute, sublicense and sell copies of the software.

**Note**: This software is not affiliated with OpenAI.
