# Open Interpreter

![Banner Image](https://github.com/KillianLucas/open-interpreter/blob/main/misc/banner_3.png)

Open Interpreter is a lightweight, open-source implementation of OpenAI's Code Interpreter that runs locally.

```python
interpreter.chat("Add subtitles to video.mp4 on my Desktop.")
```
```
>>> On it. First, I'll check if any speech-to-text libraries are installed...
```

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

```python
import interpreter
interpreter.api_key = "<your_openai_api_key>"

# Start an interactive chat in your terminal
interpreter.chat()
```

## Use Cases

Open Interpreter acts as a seasoned programmer that can execute code snippets to accomplish tasks.

1. Add subtitles to all videos in a folder.
2. Blur all faces in a photo or video.
4. Edit a large batch of documents.

...

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

#### Terminal Chat

Running `.chat()` will start an interactive session in your terminal:

```python
interpreter.chat()
```

#### Python Chat

For more precise control, you can pass messages directly to `.chat(message)`:

```python
interpreter.chat("Add subtitles to all videos in /videos.")

# ... Streams output to your terminal, completes task ...

interpreter.chat("These look great but can you make the subtitles bigger?") # Note: .chat() remembers conversation history by default

# ...
```

#### Start a New Chat

By default, Open Interpreter remembers conversation history. 

If you want to start fresh, you can reset it:

```python
interpreter.reset()
```

Then open a new **Terminal Chat** or **Python Chat** as described above.

#### Save and Restore Chats

`interpreter.chat()` returns a List of messages, which can be restored with `interpreter.load(messages)`:

```python
interpreter.load(chat)
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

Open Interpreter equips a [function-calling](https://platform.openai.com/docs/guides/gpt/function-calling) GPT-4 with the `exec()` function.

We then stream the model's messages, code, and your system's outputs to the terminal as Markdown.

Only the last `model_max_tokens` of the conversation are shown to the model, so conversations can be any length, but past events may be forgotten.

## Contributing

As an open-source project, we are extremely open to contributions, whether it be in the form of a new feature, improved infrastructure, or better documentation.

## License

Open Interpreter is licensed under the MIT License. You are permitted to use, copy, modify, distribute, sublicense and sell copies of the software.

**Note**: This software is not affiliated with OpenAI.