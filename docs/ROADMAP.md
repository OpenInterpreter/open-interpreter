# Roadmap

- [x] **Split TUI from core — two seperate folders.** (This lets us tighten our scope around those two projects. See "What's in our scope" below.)
- [x] Support multiple instances
- [ ] **Easy 🟢** Add more hosted models to [docs](https://github.com/KillianLucas/open-interpreter/tree/main/docs/language-model-setup/hosted-models) from [litellm docs](https://docs.litellm.ai/docs/)
- [ ] **Easy 🟢** Require documentation for PRs
- [ ] Make sure breaking from generator during execution stops the execution
- [ ] Stateless core python package, config passed in by TUI
- [ ] Expose tool (`interpreter.computer.run(language, code)`)
- [ ] Add %% (shell) magic command
- [ ] Allow for limited functions (`interpreter.functions`)
- [ ] Generalize "output" and "input" — new types other than text: HTML, Image (see below)
- [ ] Switch core code interpreter to be Jupyter-powered
- [ ] Local and vision should be reserved for TUI, more granular settings for Python
- [ ] Create more intensive tests for benchmarks
- [ ] Connect benchmarks to multiple open-source LLMs
- [ ] Further split TUI from core (some utils still reach across)
- [ ] Allow for custom llms (`interpreter.llm`) which conform to some class, properties like `.supports_functions` and `.supports_vision`
- [ ] Allow for custom interfaces (`interpreter.computer.interfaces.append(class_that_conforms_to_base_interface)`)
- [ ] Work with mintlfy to translate docs
- [ ] Expand "safe mode" to have proper, simple Docker support
- [ ] Make it so core can be run elsewhere from terminal package — perhaps split over HTTP (this would make docker easier too)
- [ ] Improve partnership with `languagetools`
- [ ] Remove `procedures` (there must be a better way)
- [ ] Better storage of different model keys in TUI / config file. All keys, to multiple providers, should be stored in there. Easy switching
- [ ] Better comments throughout the package (they're like docs for contributors)

# What's in our scope?

Open Interpreter contains two projects which support eachother, whose scopes are as follows:

1. `core`, which is dedicated to figuring out how to get LLMs to safely control a computer. Right now, this means creating a real-time code execution environment that language models can operate.
2. `terminal_interface`, a text-only way for users to direct the code-running LLM running inside `core`. This includes functions for connecting the `core` to various local and hosted LLMs (which the `core` itself should not know about).

# What's not in our scope?

Our guiding philosphy is minimalism, so we have also decided to explicitly consider the following as **out of scope**:

1. Additional functions in `core` beyond running code.
2. Advanced memory or planning. We consider these to be the LLM's responsibility, and as such OI will remain single-threaded.
3. More complex interactions with the LLM in `terminal_interface` beyond text (but file paths to more complex inputs, like images or video, can be included in that text).

# Upcoming structures

### Post TUI/core split structure

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
    /computer
      core.py
      /interfaces
        __init__.py
        python.py
        shell.py
        ...
    ...
```

### New streaming structure

```
{ "start_of_text": true },
{ "text": "Processing your request to generate a plot." }, # Sent token by token
{ "python": "plot = create_plot_from_data('base64_image_of_data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)" }, # Sent token by token
{ "executing": { "python": "plot = create_plot_from_data('base64_image_of_data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)" } },
{ "start_of_output": true },
{ "active_line": 1 },
{ "active_line": 2 },
{ "output": { "type": "image", "content": "base64_encoded_plot_image" } },
{ "active_line": 3 },
{ "output": { "type": "html", "content": "<html>Plot in HTML format</html>" } },
{ "end_of_output": true }
```

### New static messages structure

```
[
  {
    "role": "user",
    "content": [
      {"type": "text", "content": "Please create a plot from this data and display it as an image and then as HTML."},
      {"type": "image", "content": "data"}
    ]
  },
  {
    "role": "assistant",
    "content": [
      {
        "type": "text", 
        "content": "Processing your request to generate a plot."
      },
      {
        "type": "python",
        "content": "plot = create_plot_from_data('data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)"
      },
      {
        "type": "output",
        "content": [
          {"type": "text", "content": "Plot generated successfully."},
          {"type": "image", "content": "base64_encoded_plot_image"},
          {"type": "html", "content": "<html>Plot in HTML format</html>"}
        ]
      }
    ]
  }
]
```
