# Roadmap

## New features

- [ ] Add anonymous, opt-in data collection → open-source dataset, like `--contribute_conversations`
  - [ ] Make that flag send each message to server
  - [ ] Set up receiving replit server
  - [ ] Add option to send previous conversations
  - [ ] Make the messaging really strong re: "We will be saving this, we will redact PII, we will open source the dataset so we (and others) can train code interpreting models"
- [ ] Let OI use OI. Add `interpreter.chat(async=True)` bool. OI can use this to open OI on a new thread
  - [ ] Also add `interpreter.get_last_assistant_messages()` to return the last assistant messages.
- [ ] Allow for limited functions (`interpreter.functions`) using regex
  - [ ] If `interpreter.functions != []`:
      - [ ] set `interpreter.languages` to only use Python
      - [ ] Use regex to ensure the output of code blocks conforms to just using those functions + other python basics
- [ ] Allow for custom llms (to be stored in `interpreter.llm`) which conform to some class
  - [ ] Should be a generator that can be treated exactly like the OpenAI streaming API
  - [ ] Has attributes `.supports_function_calling`, `.supports_vision`, and `.context_window`
- [ ] (Maybe) Allow for a custom embedding function (`interpreter.embed`) which will let us do semantic search
- [ ] Allow for custom languages (`interpreter.computer.languages.append(class_that_conforms_to_base_language)`)
  - [x] Make it so function calling dynamically uses the languages in interpreter.computer.languages
- [ ] Add a skill library, or maybe expose post processing on code, so we can save functions for later & semantically search docstrings. Keep this minimal!
  - [ ] 
  - [ ] If `interpreter.skill_library == True`, we should add a decorator above all functions, then show OI how to search its skill library
- [ ] Allow for integrations somehow
- [ ] Expand "safe mode" to have proper, simple Docker support, or maybe Cosmopolitan LibC
- [ ] Make it so core can be run elsewhere from terminal package — perhaps split over HTTP (this would make docker easier too)

## Future-proofing

- [ ] Really good tests / optimization framework, to be run less frequently than Github actions tests
  - [ ] Figure out how to run us on [GAIA](https://huggingface.co/gaia-benchmark) and use a subset of that as our tests / optimization framework
    - [ ] How do we just get the questions out of this thing?
    - [ ] How do we assess whether or not OI has solved the task?
  - [ ] Loop over GAIA, use a different language model every time (use Replicate, then ask LiteLLM how they made their "mega key" to many different LLM providers)
  - [ ] Loop over that ↑ using a different prompt each time. Which prompt is best across all LLMs?
  - [ ] (Future future) Use GPT-4 to assess each result, explaining each failure. Summarize. Send it all to GPT-4 + our prompt. Let it redesign the prompt, given the failures, rinse and repeat
- [ ] Use Anthropic function calling
- [ ] Stateless (as in, doesn't use the application directory) core python package. All `appdir` stuff should be only for the TUI
  - [ ] `interpreter.__dict__` = a dict derived from config is how the python package should be set, and this should be from the TUI. `interpreter` should not know about the config
  - [ ] Move conversation storage out of the core and into the TUI. When we exit or error, save messages same as core currently does
- [ ] Local and vision should be reserved for TUI, more granular settings for Python
  - [ ] Rename `interpreter.local` → `interpreter.offline`, implement ↑ custom LLMs with a `.supports_vision` attribute instead of `interpreter.vision`
- [ ] Further split TUI from core (some utils still reach across)
- [ ] Remove `procedures` (there must be a better way)
- [ ] Better storage of different model keys in TUI / config file. All keys, to multiple providers, should be stored in there. Easy switching
  - [ ] Automatically migrate users from old config to new config, display a message of this
- [ ] On update, check for new system message and ask user to overwrite theirs, or only let users pass in "custom instructions" which adds to our system message
  - [ ] I think we could have a config that's like... system_message_version. If system_message_version is below the current version, ask the user if we can overwrite it with the default config system message of that version

## Documentation

- [ ] **Easy 🟢** Add more hosted models to [docs](https://github.com/KillianLucas/open-interpreter/tree/main/docs/language-model-setup/hosted-models) from [litellm docs](https://docs.litellm.ai/docs/)
- [ ] **Easy 🟢** Require documentation for PRs
- [ ] Work with Mintlify to translate docs
- [ ] Better comments throughout the package (they're like docs for contributors)
- [ ] Document the New Computer Update
- [ ] Make a migration guide for the New Computer Update

## Completed

- [x] **Split TUI from core — two seperate folders.** (This lets us tighten our scope around those two projects. See "What's in our scope" below.)
- [x] Add %% (shell) magic command
- [x] Support multiple instances
- [x] Split ROADMAP into sections
- [x] Connect %% (shell) magic command to shell interpreter that `interpreter` runs
- [x] Expose tool (`interpreter.computer.run(language, code)`)
- [x] Generalize "output" and "input" — new types other than text: HTML, Image (see below)
- [x] Switch core code interpreter to be Jupyter-powered
- [x] Make sure breaking from generator during execution stops the execution

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

```python
{"role": "assistant", "type": "message", "start": True}
{"role": "assistant", "type": "message", "content": "Pro"}
{"role": "assistant", "type": "message", "content": "cessing"}
{"role": "assistant", "type": "message", "content": "your request"}
{"role": "assistant", "type": "message", "content": "to generate a plot."}
{"role": "assistant", "type": "message", "end": True}

{"role": "assistant", "type": "code", "format": "python", "start": True}
{"role": "assistant", "type": "code", "format": "python", "content": "plot = create_plot_from_data"}
{"role": "assistant", "type": "code", "format": "python", "content": "('data')\ndisplay_as_image(plot)"}
{"role": "assistant", "type": "code", "format": "python", "content": "\ndisplay_as_html(plot)"}
{"role": "assistant", "type": "code", "format": "python", "end": True}

{"role": "computer", "type": "console", "start": True}
{"role": "computer", "type": "console", "format": "output", "content": "a printed statement"}
{"role": "computer", "type": "console", "format": "active_line", "content": "1"}
{"role": "computer", "type": "console", "format": "active_line", "content": "2"}
{"role": "computer", "type": "console", "format": "active_line", "content": "3"}
{"role": "computer", "type": "console", "format": "output", "content": "another printed statement"}
{"role": "computer", "type": "console", "end": True}

...

# ASSISTANT GENERATED HTML

# The assistant writes some HTML.
# Because recipient isn't explicitly set, it's being "rendered" to both the user and the computer in real-time.
{"role": "assistant", "type": "code", "format": "html", "start": True}
{"role": "assistant", "type": "code", "format": "html", "content": "<html>Some"}
{"role": "assistant", "type": "code", "format": "html", "content": "thing</html>"}
{"role": "assistant", "type": "code", "format": "html", "end": True}

# The computer runs the HTML.

# The running HTML produces some console log / errors.
{"role": "computer", "type": "console", "start": True}
{"role": "computer", "type": "console", "format": "output", "content": "{HTML errors}"}
{"role": "computer", "type": "console", "end": True}

# The computer will make an image for the assistant to see.
# The image's "recipient" is set to "assistant" because **the user has already seen this HTML** as interactive HTML, in block 1
{"role": "computer", "type": "image", "format": "path", "recipient": "assistant", "start": True}
{"role": "computer", "type": "image", "format": "path", "recipient": "assistant", "content": "/path/to/html_block_render.png"}
{"role": "computer", "type": "image", "format": "path", "recipient": "assistant", "end": True}

...

# COMPUTER GENERATED HTML

# The assistant writes some Python.
{"role": "assistant", "type": "code", "format": "python", "start": True}
{"role": "assistant", "type": "code", "format": "python", "content": "display_plot_as_html(plot)"}
{"role": "assistant", "type": "code", "format": "python", "end": True}

# The computer runs the Python.

# The running Python produces some HTML.
# The HTML's "recipient" is set to "user" so the user can interact with it, but the assistant's context won't get stuffed with tokens (instead, it will get an image in a moment)
{"role": "computer", "type": "code", "format": "html", "recipient": "user", "start": True}
{"role": "computer", "type": "code", "format": "html", "recipient": "user", "content": "<html>Something</html>"}
{"role": "computer", "type": "code", "format": "html", "recipient": "user", "end": True}

# The computer runs the HTML.

# The running HTML produces some console log / errors.
{"role": "computer", "type": "console", "start": True}
{"role": "computer", "type": "console", "format": "output", "content": "{HTML errors}"}
{"role": "computer", "type": "console", "end": True}

# The computer will make an image for the assistant to see.
# The image's "recipient" is set to "assistant" because **the user has already seen this HTML** as interactive HTML, in block 2
{"role": "computer", "type": "image", "format": "path", "recipient": "assistant", "start": True}
{"role": "computer", "type": "image", "format": "path", "recipient": "assistant", "content": "/path/to/html_block_render.png"}
{"role": "computer", "type": "image", "format": "path", "recipient": "assistant", "end": True}

...

{"role": "assistant", "type": "message", "start": True}
{"role": "assistant", "type": "message", "content": "Plot"}
{"role": "assistant", "type": "message", "content": "generated"}
{"role": "assistant", "type": "message", "content": "successfully."}
{"role": "assistant", "type": "message", "end": True}
```

### New static messages structure

```
[

  {"role": "user", "type": "message", "content": "Please create a plot from this data and display it as an image and then as HTML."}, # implied format: text (only one format for type message)
  {"role": "user", "type": "image", "format": "path", "content": "path/to/image.png"}
  {"role": "user", "type": "file", "content": "/path/to/file.pdf"} # implied format: path (only one format for type file)
  {"role": "assistant", "type": "message", "content": "Processing your request to generate a plot."} # implied format: text
  {"role": "assistant", "type": "code", "format": "python", "content": "plot = create_plot_from_data('data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)"}
  {"role": "computer", "type": "image", "format": "base64", "content": "base64"}
  {"role": "computer", "type": "code", "format": "html", "content": "<html>Plot in HTML format</html>"}
  {"role": "computer", "type": "console", "format": "output", "content": "{HTML errors}"}
  {"role": "assistant", "type": "message", "content": "Plot generated successfully."} # implied format: text

]
```
