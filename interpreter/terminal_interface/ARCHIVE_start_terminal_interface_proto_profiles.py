if args.local:
    # Default local (LM studio) attributes

    if not (args.os or args.vision):
        interpreter.system_message = "You are Open Interpreter, a world-class programmer that can execute code on the user's machine."

    interpreter.offline = True
    interpreter.llm.model = "openai/x"  # "openai/" tells LiteLLM it's an OpenAI compatible server, the "x" part doesn't matter
    interpreter.llm.api_base = "http://localhost:1234/v1"
    interpreter.llm.max_tokens = 1000
    interpreter.llm.context_window = 3000
    interpreter.llm.api_key = "x"

    if not (args.os or args.vision):
        display_markdown_message(
            """
> Open Interpreter's local mode is powered by **`LM Studio`**.


You will need to run **LM Studio** in the background.

1. Download **LM Studio** from [https://lmstudio.ai/](https://lmstudio.ai/) then start it.
2. Select a language model then click **Download**.
3. Click the **<->** button on the left (below the chat button).
4. Select your model at the top, then click **Start Server**.


Once the server is running, you can begin your conversation below.

> **Warning:** This feature is highly experimental.
> Don't expect `gpt-3.5` / `gpt-4` level quality, speed, or reliability yet!

"""
        )
    else:
        if args.vision:
            display_markdown_message(
                "> `Local Vision` enabled (experimental)\n\nEnsure LM Studio's local server is running in the background **and using a vision-compatible model**.\n\nRun `interpreter --local` with no other arguments for a setup guide.\n"
            )
            time.sleep(1)
            display_markdown_message("---\n")
        elif args.os:
            time.sleep(1)
            display_markdown_message("*Setting up local OS control...*\n")
            time.sleep(2.5)
            display_markdown_message("---")
            display_markdown_message(
                "> `Local Vision` enabled (experimental)\n\nEnsure LM Studio's local server is running in the background **and using a vision-compatible model**.\n\nRun `interpreter --local` with no other arguments for a setup guide.\n"
            )
        else:
            time.sleep(1)
            display_markdown_message(
                "> `Local Mode` enabled (experimental)\n\nEnsure LM Studio's local server is running in the background.\n\nRun `interpreter --local` with no other arguments for a setup guide.\n"
            )
