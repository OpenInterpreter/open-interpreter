# Roadmap

- [ ] Allow for limited functions (`interpreter.functions`)
- [ ] Switch core code interpreter to by Jupyter-powered
- [ ] Create more intensive tests for benchmarks
- [ ] Connect benchmarks to multiple open-source LLMs
- [ ] Allow for custom llms (`interpreter.llm`)
- [ ] Allow for custom languages (`interpreter.languages.append(class_that_conforms_to_base_language)`)
- [ ] Stateless core python package, config passed in by TUI
- [ ] Expand "safe mode" to have proper Docker support
- [ ] Make it so core can be run elsewhere from terminal package — perhaps split over HTTP (this would make docker easier too)
- [ ] Support multiple instances of OI (`import Interpreter`)
- [ ] Expose tool (`code_interpreter`)
- [ ] Improve partnership with `languagetools`
- [ ] Remove `procedures` (there must be a better way)
- [ ] Better comments throughout the package (they're like docs for contributors)
- [ ] Up-to-date documentation, requiring documentation for PRs
- [ ] Split TUI from core — two seperate folders

### Post TUI/core split structure:

```
/open_interpreter
  /terminal_interface
    tui.py
    chat.py
    /utils
  /core
    core.py
    respond.py
    /utils
    /code_interpreter
      core.py
      /languages
        __init__.py
        python.py
        shell.py
        ...
    ...
```

# What's in our scope?

Open Interpreter contains two projects which support eachother, whose scopes are as follows:

1. `core`, which is dedicated to figuring out how to get LLMs to control a computer. Right now, this means creating a real-time code execution environment that language models can operate.
2. `terminal_interface`, a text-only way for users to direct the LLM running inside `core`. This includes functions for connecting the `core` to various local and hosted LLMs (which the `core` itself should know about).

# What's not in our scope?

Our guiding philosphy is minimalism, so we have also decided to explicitly consider the following as **out of scope**:

1. Additional functions in `core` beyond running code.
2. Advanced memory or planning. We consider these to be the LLM's responsibility, and as such OI will remain single-threaded.
3. More complex interactions with the LLM in `terminal_interface` beyond text (but file paths to more complex inputs, like images or video, can be included in that text).
