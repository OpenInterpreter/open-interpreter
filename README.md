# Open Interpreter

A modern command line assistant.

[Documentation](https://docs.openinterpreter.com/) | [Discord](https://discord.gg/Hvz9Axh84z)

## Install

```bash
curl https://raw.githubusercontent.com/OpenInterpreter/open-interpreter/refs/heads/development/installers/new-installer.sh | sh
```

## Usage

Start a conversation:
```bash
$ interpreter
> help me set up a new fastapi project
Creating project structure...
Added requirements.txt, main.py, and Dockerfile
> add a /users endpoint
Adding routes/users.py...
```

Instant chats with `i [prompt]`:
```bash
$ i want a venv here
$ i want to undo the last commit
$ i need deno
```

Fix errors with `wtf`:
```bash
$ python test.py
ImportError: No module named 'requests'
$ wtf
Installing requests...
Done. Try running your script again.
```

## Configuration

```bash
# Choose your model
interpreter --model gpt-4o
interpreter --model claude-3-sonnet

# Save configurations
interpreter --model gpt-4o --save-profile 4o
interpreter --profile 4o

# Enable tools (default: interpreter,editor)
interpreter --tools interpreter,editor,gui
```

## Python

```bash
pip install open-interpreter
```

```python
from interpreter import Interpreter

# Start interpreter
interpreter = Interpreter()

# Multiple tasks in same context
messages = interpreter.respond("write a test for this function")
messages = interpreter.respond("now add error handling")

# Reset context
interpreter.messages = []

# Set custom context
interpreter.messages = [{"role": "user", "content": "write a test for this function"}]

# Stream output
for chunk in interpreter.respond(stream=True):
    print(chunk, end="")

# Start an interactive chat
interpreter.chat()

# View conversation history
print(interpreter.messages)
```

## Benchmarks

(Coming soon)

## License

[AGPL-3.0](LICENSE)