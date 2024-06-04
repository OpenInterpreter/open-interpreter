import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

litellm.suppress_debug_info = True
import time
import uuid

import tokentrim as tt

from ...terminal_interface.utils.display_markdown_message import (
    display_markdown_message,
)
from .run_function_calling_llm import run_function_calling_llm
from .run_text_llm import run_text_llm
from .utils.convert_to_openai_messages import convert_to_openai_messages


class Llm:
    """
    A stateless LMC-style LLM with some helpful properties.
    """

    def __init__(self, interpreter):
        # Store a reference to parent interpreter
        self.interpreter = interpreter

        # OpenAI-compatible chat completions "endpoint"
        self.completions = fixed_litellm_completions

        # Settings
        self.model = "gpt-4-turbo"
        self.temperature = 0

        self.supports_vision = None  # Will try to auto-detect
        self.vision_renderer = (
            self.interpreter.computer.vision.query
        )  # Will only use if supports_vision is False

        self.supports_functions = None  # Will try to auto-detect
        self.execution_instructions = "To execute code on the user's machine, write a markdown code block. Specify the language after the ```. You will receive the output. Use any programming language."  # If supports_functions is False, this will be added to the system message

        # Optional settings
        self.context_window = None
        self.max_tokens = None
        self.api_base = None
        self.api_key = None
        self.api_version = None

        # Budget manager powered by LiteLLM
        self.max_budget = None

    def run(self, messages):
        """
        We're responsible for formatting the call into the llm.completions object,
        starting with LMC messages in interpreter.messages, going to OpenAI compatible messages into the llm,
        respecting whether it's a vision or function model, respecting its context window and max tokens, etc.

        And then processing its output, whether it's a function or non function calling model, into LMC format.
        """

        # Assertions
        assert (
            messages[0]["role"] == "system"
        ), "First message must have the role 'system'"
        for msg in messages[1:]:
            assert (
                msg["role"] != "system"
            ), "No message after the first can have the role 'system'"

        model = self.model
        # Setup our model endpoint
        if model == "i":
            model = "openai/i"
            if not hasattr(self.interpreter, "conversation_id"):  # Only do this once
                self.context_window = 7000
                self.api_key = "x"
                self.max_tokens = 1000
                self.api_base = "https://api.openinterpreter.com/v0"
                self.interpreter.conversation_id = str(uuid.uuid4())

        # Detect function support
        if self.supports_functions == None:
            try:
                if litellm.supports_function_calling(model):
                    self.supports_functions = True
                else:
                    self.supports_functions = False
            except:
                self.supports_functions = False

        # Detect vision support
        if self.supports_vision == None:
            try:
                if litellm.supports_vision(model):
                    self.supports_vision = True
                else:
                    self.supports_vision = False
            except:
                self.supports_vision = False

        # Trim image messages if they're there
        image_messages = [msg for msg in messages if msg["type"] == "image"]
        if self.supports_vision:
            if self.interpreter.os:
                # Keep only the last two images if the interpreter is running in OS mode
                if len(image_messages) > 1:
                    for img_msg in image_messages[:-2]:
                        messages.remove(img_msg)
                        if self.interpreter.verbose:
                            print("Removing image message!")
            else:
                # Delete all the middle ones (leave only the first and last 2 images) from messages_for_llm
                if len(image_messages) > 3:
                    for img_msg in image_messages[1:-2]:
                        messages.remove(img_msg)
                        if self.interpreter.verbose:
                            print("Removing image message!")
                # Idea: we could set detail: low for the middle messages, instead of deleting them
        elif self.supports_vision == False and self.vision_renderer:
            for img_msg in image_messages:
                if img_msg["format"] != "description":
                    self.interpreter.display_message("\n  *Viewing image...*\n")

                    if img_msg["format"] == "path":
                        precursor = f"The image I'm referring to ({img_msg['content']}) contains the following: "
                        if self.interpreter.computer.import_computer_api:
                            postcursor = f"\nIf you want to ask questions about the image, run `computer.vision.query(path='{img_msg['content']}', query='(ask any question here)')` and a vision AI will answer it."
                        else:
                            postcursor = ""
                    else:
                        precursor = "Imagine I have just shown you an image with this description: "
                        postcursor = ""

                    img_msg["content"] = (
                        # precursor
                        # + self.vision_renderer(lmc=img_msg) +
                        "\n---\nThe image contains the following text exactly: '''\n"
                        + self.interpreter.computer.vision.ocr(lmc=img_msg)
                        + "\n'''"
                        + postcursor
                    )
                    img_msg["format"] = "description"

        # Convert to OpenAI messages format
        messages = convert_to_openai_messages(
            messages,
            function_calling=self.supports_functions,
            vision=self.supports_vision,
            shrink_images=self.interpreter.shrink_images,
            interpreter=self.interpreter,
        )

        system_message = messages[0]["content"]
        messages = messages[1:]

        # Trim messages
        try:
            if self.context_window and self.max_tokens:
                trim_to_be_this_many_tokens = (
                    self.context_window - self.max_tokens - 25
                )  # arbitrary buffer
                messages = tt.trim(
                    messages,
                    system_message=system_message,
                    max_tokens=trim_to_be_this_many_tokens,
                )
            elif self.context_window and not self.max_tokens:
                # Just trim to the context window if max_tokens not set
                messages = tt.trim(
                    messages,
                    system_message=system_message,
                    max_tokens=self.context_window,
                )
            else:
                try:
                    messages = tt.trim(
                        messages, system_message=system_message, model=model
                    )
                except:
                    if len(messages) == 1:
                        if self.interpreter.in_terminal_interface:
                            display_markdown_message(
                                """
**We were unable to determine the context window of this model.** Defaulting to 3000.

If your model can handle more, run `interpreter --context_window {token limit} --max_tokens {max tokens per response}`.

Continuing...
                            """
                            )
                        else:
                            display_markdown_message(
                                """
**We were unable to determine the context window of this model.** Defaulting to 3000.

If your model can handle more, run `interpreter.llm.context_window = {token limit}`.

Also please set `interpreter.llm.max_tokens = {max tokens per response}`.

Continuing...
                            """
                            )
                    messages = tt.trim(
                        messages, system_message=system_message, max_tokens=3000
                    )
        except:
            # If we're trimming messages, this won't work.
            # If we're trimming from a model we don't know, this won't work.
            # Better not to fail until `messages` is too big, just for frustrations sake, I suppose.

            # Reunite system message with messages
            messages = [{"role": "system", "content": system_message}] + messages

            pass

        ## Start forming the request

        params = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        # Optional inputs
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_version:
            params["api_version"] = self.api_version
        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if self.temperature:
            params["temperature"] = self.temperature
        if hasattr(self.interpreter, "conversation_id"):
            params["conversation_id"] = self.interpreter.conversation_id

        # Set some params directly on LiteLLM
        if self.max_budget:
            litellm.max_budget = self.max_budget
        if self.interpreter.verbose:
            litellm.set_verbose = True

        if self.interpreter.debug:
            print("\n\n\nOPENAI COMPATIBLE MESSAGES\n\n\n")
            for message in messages:
                if len(str(message)) > 5000:
                    print(str(message)[:200] + "...")
                else:
                    print(message)
                print("\n")
            print("\n\n\n")
            time.sleep(5)

        if self.supports_functions:
            yield from run_function_calling_llm(self, params)
        else:
            yield from run_text_llm(self, params)


def fixed_litellm_completions(**params):
    """
    Just uses a dummy API key, since we use litellm without an API key sometimes.
    Hopefully they will fix this!
    """

    if "local" in params.get("model"):
        # Kinda hacky, but this helps sometimes
        params["stop"] = ["<|assistant|>", "<|end|>", "<|eot_id|>"]

    if params.get("model") == "i" and "conversation_id" in params:
        litellm.drop_params = (
            False  # If we don't do this, litellm will drop this param!
        )
    else:
        litellm.drop_params = True

    # Run completion
    first_error = None
    try:
        yield from litellm.completion(**params)
    except Exception as e:
        # Store the first error
        first_error = e
        # LiteLLM can fail if there's no API key,
        # even though some models (like local ones) don't require it.

        if "api key" in str(first_error).lower() and "api_key" not in params:
            print(
                "LiteLLM requires an API key. Please set a dummy API key to prevent this message. (e.g `interpreter --api_key x` or `interpreter.llm.api_key = 'x'`)"
            )

        # So, let's try one more time with a dummy API key:
        params["api_key"] = "x"

        try:
            yield from litellm.completion(**params)
        except:
            # If the second attempt also fails, raise the first error
            raise first_error
