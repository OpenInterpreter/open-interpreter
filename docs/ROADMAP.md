# Roadmap

## New features
- [ ] Add `interpreter --async` command (that OI itself can use) — pipes answer to output
- [ ] Expose tool (`interpreter.computer.run(language, code)`)
- [ ] Allow for limited functions (`interpreter.functions`)
- [ ] Add anonymous, opt-in data collection → open-source dataset
- [ ] Allow for custom llms (`interpreter.llm`) which conform to some class, properties like `.supports_functions` and `.supports_vision`
- [ ] (Maybe) Allow for a custom embedding function (`interpreter.embed`) which will let us do semantic search
- [ ] Allow for custom languages (`interpreter.computer.languages.append(class_that_conforms_to_base_language)`)
- [ ] Add a skill library, or maybe expose post processing on code, so we can save functions for later & semantically search docstricts. Keep this minimal!
- [ ] Allow for integrations
- [ ] Expand "safe mode" to have proper, simple Docker support
- [ ] Make it so core can be run elsewhere from terminal package — perhaps split over HTTP (this would make docker easier too)
- [ ] Improve partnership with `languagetools`

## Future-proofing
- [ ] Apply to [GAIA](https://huggingface.co/gaia-benchmark) and use them to optimize
- [ ] Add more language models to tests (use Replicate, ask LiteLLM)
- [ ] Make sure breaking from generator during execution stops the execution
- [ ] Stateless core python package, config passed in by TUI
- [ ] Connect %% (shell) magic command to shell interpreter that `interpreter` runs
- [ ] Generalize "output" and "input" — new types other than text: HTML, Image (see below)
- [ ] Switch core code interpreter to be Jupyter-powered
- [ ] Local and vision should be reserved for TUI, more granular settings for Python
- [ ] Further split TUI from core (some utils still reach across)
- [ ] Remove `procedures` (there must be a better way)
- [ ] Better storage of different model keys in TUI / config file. All keys, to multiple providers, should be stored in there. Easy switching

## Documentation
- [ ] **Easy 🟢** Add more hosted models to [docs](https://github.com/KillianLucas/open-interpreter/tree/main/docs/language-model-setup/hosted-models) from [litellm docs](https://docs.litellm.ai/docs/)
- [ ] **Easy 🟢** Require documentation for PRs
- [ ] Work with Mintlify to translate docs
- [ ] Better comments throughout the package (they're like docs for contributors)

## Completed

- [x] (Nov 23rd) **Split TUI from core — two seperate folders.** (This lets us tighten our scope around those two projects. See "What's in our scope" below.)
- [x] (Nov 25th) Add %% (shell) magic command
- [x] (Nov 26th) Support multiple instances
- [x] (Nov 28th) Split ROADMAP into sections

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

### New streaming structure

```
{"role": "assistant", "type": "text", "start": True}
{"role": "assistant", "type": "text", "content": "Pro"}
{"role": "assistant", "type": "text", "content": "cessing"}
{"role": "assistant", "type": "text", "content": "your request"}
{"role": "assistant", "type": "text", "content": "to generate a plot."}
{"role": "assistant", "type": "text", "end": True}  

{"role": "assistant", "type": "python", "start": True}
{"role": "assistant", "type": "python", "content": "plot = create_plot_from_data('data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)"}
{"role": "assistant", "type": "python", "end": True}

{"role": "computer", "type": "text", "start": True}
{"role": "computer", "type": "text", "content": "1"}
{"role": "computer", "type": "text", "content": "2"}
{"role": "computer", "type": "text", "content": "3"}
{"role": "computer", "type": "text", "end": True}

{"role": "computer", "type": "image", "start": True}
{"role": "computer", "type": "image", "content": "base64_encoded_plot_image"}
{"role": "computer", "type": "image", "end": True}

{"role": "computer", "type": "html", "start": True}
{"role": "computer", "type": "html", "content": "<html>Plot in HTML format</html>"}
{"role": "computer", "type": "html", "end": True}

{"role": "computer", "type": "html", "start": True}
{"role": "computer", "type": "html", "content": "<html>Another plot in HTML format</html>"}
{"role": "computer", "type": "html", "end": True}

{"role": "assistant", "type": "text", "start": True}
{"role": "assistant", "type": "text", "content": "Plot"}
{"role": "assistant", "type": "text", "content": "generated"}
{"role": "assistant", "type": "text", "content": "successfully."}
{"role": "assistant", "type": "text", "end": True}
```

### New static messages structure

```
[

  {"role": "user", "type": "text", "content": "Please create a plot from this data and display it as an image and then as HTML."},
  {"role": "user", "type": "image", "content": "{base64}"}
  {"role": "user", "type": "file", "content": "/path/to/file"}
  {"role": "assistant", "type": "text", "content": "Processing your request to generate a plot."}
  {"role": "assistant", "type": "python", "content": "plot = create_plot_from_data('data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)"}
  {"role": "computer", "type": "image", "content": "{base64}"}
  {"role": "computer", "type": "html", "content": "<html>Plot in HTML format</html>"}
  {"role": "assistant", "type": "text", "content": "Plot generated successfully."}

]
```
