# Open Interpreter

A minimal, open-source implementation of OpenAI's code interpreter.

![Interpreter Demo](https://github.com/KillianLucas/open-interpreter/assets/63927363/a1597f66-d298-4172-bc0b-35b36e1479eb)

## What is this?

<br>

> Having access to a junior programmer working at the speed of your fingertips ... can make new workflows effortless and efficient, as well as open the benefits of programming to new audiences.
>
> — _OpenAI's Code Interpreter Release_

<br>

**Open Interpreter** lets GPT-4 run Python code locally. You can chat with Open Interpreter through a ChatGPT-like interface in your terminal by running `$ interpreter` after installing. **You'll be asked to approve any code before it's run.**

This provides a natural language interface to Python's general-purpose capabilities:

- Create and edit photos, videos, PDFs, etc.
- Run `selenium` to control a Chrome browser.
- Modify files/folders on your local system.
- ...etc.

<br>

[How does this compare to OpenAI's code interpreter?](https://github.com/KillianLucas/open-interpreter#comparison-to-chatgpts-code-interpreter)<br>

## Demo Notebook

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1WKmRXZgsErej2xUriKzxrEAXdxMSgWbb?usp=sharing)

## Features

- **User confirmation required to run code.**
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

## Safety Notice

Since generated code is executed in your local environment, it can interact with your files and system settings, potentially leading to unexpected outcomes like data loss or security risks.

**Open Interpreter will ask for confirmation before executing any code.**

You can run `interpreter --no_confirm` or set `interpreter.no_confirm = True` to bypass this confirmation, in which case:

- Be cautious when requesting commands that modify files or system settings.
- Watch Open Interpreter like a self-driving car, and be prepared to end the process by closing your terminal.
- Consider running Open Interpreter in a restricted environment like Google Colab or Replit. These environments are more isolated, reducing the risks associated with executing arbitrary code.

For added security, Open Interpreter also respects `interpreter.forbidden_commands`, a list of potentially harmful commands that are disallowed by default. You can modify this list, but do so with caution.

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

`interpreter.chat()` returns a List of messages when return_messages=True, which can be used to resume a conversation with `interpreter.load(messages)`:

```python
messages = interpreter.chat("My name is Killian.", return_messages=True) # Save messages to 'messages'
interpreter.reset() # Reset interpreter ("Killian" will be forgotten)

interpreter.load(messages) # Resume chat from 'messages' ("Killian" will be remembered)
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

## Contributing

As an open-source project, we are extremely open to contributions, whether it be in the form of a new feature, improved infrastructure, or better documentation.

## License

Open Interpreter is licensed under the MIT License. You are permitted to use, copy, modify, distribute, sublicense and sell copies of the software.

**Note**: This software is not affiliated with OpenAI.

![Banner Image](https://i.ibb.co/ZHfB9sm/open-interpreter-banner.png)

<p align="right">
    <sub><i>Illustration by Open Interpreter. Inspired by <a href="https://rubywjchen.com/">Ruby Chen's</a> GPT-4 artwork.</i></sub>
</p>
