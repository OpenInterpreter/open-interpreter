from interpreter import __version__

def help_message():
    tips = [
        "\033[38;5;240mTip: Pipe in prompts using `$ANYTHING | i`\033[0m",
        "\033[38;5;240mTip: Type `wtf` in your terminal to fix the last error\033[0m",
        "\033[38;5;240mTip: Your terminal is a chatbox. Type `i want to...`\033[0m",
    ]
    BLUE_COLOR = "\033[94m"
    RESET_COLOR = "\033[0m"

    content = f"""Open Interpreter {__version__}
Copyright (C) 2024 Open Interpreter Team
Licensed under GNU AGPL v3.0

A modern command-line assistant.

\033[1mUSAGE\033[0m 

{BLUE_COLOR}interpreter{RESET_COLOR} [flags]  \033[38;5;240m(e.g. interpreter --model gpt-4o)\033[0m
{BLUE_COLOR}i{RESET_COLOR} [prompt]           \033[38;5;240m(e.g. i want deno)\033[0m


\033[1mFLAGS\033[0m

{BLUE_COLOR}--model{RESET_COLOR}              Model to use for completion
{BLUE_COLOR}--provider{RESET_COLOR}           API provider (e.g. OpenAI, Anthropic)
{BLUE_COLOR}--api-base{RESET_COLOR}           Base URL for API requests
{BLUE_COLOR}--api-key{RESET_COLOR}            API key for authentication
{BLUE_COLOR}--api-version{RESET_COLOR}        API version to use
{BLUE_COLOR}--temperature{RESET_COLOR}        Sampling temperature (default: 0)

{BLUE_COLOR}--tools{RESET_COLOR}              Comma-separated tools: interpreter,editor,gui
{BLUE_COLOR}--allowed-commands{RESET_COLOR}   Commands the model can execute
{BLUE_COLOR}--allowed-paths{RESET_COLOR}      Paths the model can access
{BLUE_COLOR}--no-tool-calling{RESET_COLOR}    Disable tool usage (enabled by default)
{BLUE_COLOR}--auto-run{RESET_COLOR}, {BLUE_COLOR}-y{RESET_COLOR}       Auto-run suggested commands
{BLUE_COLOR}--interactive{RESET_COLOR}        Enable interactive mode (enabled if sys.stdin.isatty())
{BLUE_COLOR}--no-interactive{RESET_COLOR}     Disable interactive mode

{BLUE_COLOR}--system-message{RESET_COLOR}     Override default system message
{BLUE_COLOR}--instructions{RESET_COLOR}       Additional instructions in system message
{BLUE_COLOR}--max-turns{RESET_COLOR}          Maximum conversation turns (-1 for unlimited)

{BLUE_COLOR}--profile{RESET_COLOR}            Load settings from config file
{BLUE_COLOR}--profiles{RESET_COLOR}           Open profiles directory
{BLUE_COLOR}--serve{RESET_COLOR}              Start OpenAI-compatible server
"""

    # Add an indent to each line
    # content = "\n".join(f"  {line}" for line in content.split("\n"))

    # string = json.dumps(
    #     {"command": "Open Interpreter", "path": "", "file_text": content}
    # )

    # renderer = ToolRenderer(name="str_replace_editor")

    # for chunk in stream_text(string, min_delay=0.00001, max_delay=0.0001, max_chunk=50):
    #     renderer.feed(chunk)

    # renderer.feed(string)

    # renderer.close()

    print(content)

    # time.sleep(0.03)
    print("")
    # time.sleep(0.04)
    # print("\033[38;5;238mA.C., 2024. https://openinterpreter.com/\033[0m\n")
    print("\033[38;5;238mhttps://docs.openinterpreter.com/\033[0m\n")
    # time.sleep(0.05)


def help_message():
    print(
        """
usage: interpreter [options]
       i [prompt]

A modern command-line assistant.

options:
        --models                   show available models
        --model <model>            model to use for completion
        --provider <provider>      api provider (e.g. openai, anthropic)
        --api-base <url>           base url for api requests
        --api-key <key>            api key for authentication
        --api-version <version>    api version to use
        --temperature <float>      sampling temperature (default: 0)

        --tools <list>             comma-separated tools: interpreter,editor,gui
        --allowed-commands <list>  commands the model can execute
        --allowed-paths <list>     paths the model can access
        --no-tool-calling          disable tool calling (instead parse markdown code)
        --auto-run, -y             auto-run suggested commands
        --interactive              force interactive mode (true if sys.stdin.isatty())
        --no-interactive           disable interactive mode

        --instructions <text>      additional instructions in system message
        --input <text>             pre-fill first user message
        --system-message <text>    override default system message
        --max-turns <int>          maximum conversation turns (-1 for unlimited)

        --profile <path>           load settings from config file or url
        --save <path>              save settings to config file
        --profiles                 open profiles directory
        --serve                    start openai-compatible server

example:  i want a venv
example:  interpreter --model ollama/llama3.2 --serve
example:  i -y --input "run pytest, fix errors"
example:  cat instructions.txt | i
example:  i --tools gui "try to earn $1"
    """
    )
