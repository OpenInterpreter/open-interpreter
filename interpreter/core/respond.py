import json
import os
import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

# Import performance logging utilities
from .utils.performance_logger import (
    PerformanceTimer,
    log_message_stats,
    log_performance_metric,
)

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

from .render_message import render_message

# Create a thread-local storage for execution context
thread_local = threading.local()


def respond(interpreter):
    """
    Yields chunks.
    Responds until it decides not to run any more code or say anything else.
    """
    # Start performance tracking for the entire response cycle
    overall_start_time = time.time()

    # Initialize context
    last_unsupported_code = ""
    insert_loop_message = False
    code_execution_count = 0
    message_count = 0

    # Log message statistics at the start for performance analysis
    with PerformanceTimer("message_processing", "initialize"):
        log_message_stats(interpreter.messages)

    # Store thread-local config for performance optimization
    thread_local.auto_run = interpreter.auto_run
    thread_local.verbose = interpreter.verbose
    thread_local.debug = interpreter.debug
    thread_local.max_output = interpreter.max_output

    try:
        while True:
            ## RENDER SYSTEM MESSAGE ##
            with PerformanceTimer("message_processing", "render_system_message"):
                system_message = interpreter.system_message

                # Add language-specific system messages
                for language in interpreter.computer.terminal.languages:
                    if hasattr(language, "system_message"):
                        system_message += "\n\n" + language.system_message

                # Add custom instructions
                if interpreter.custom_instructions:
                    system_message += "\n\n" + interpreter.custom_instructions

                # Add computer API system message
                if interpreter.computer.import_computer_api:
                    if interpreter.computer.system_message not in system_message:
                        system_message = (
                            system_message
                            + "\n\n"
                            + interpreter.computer.system_message
                        )

                # Render the system message efficiently
                rendered_system_message = render_message(interpreter, system_message)

                # Create message object
                rendered_system_message = {
                    "role": "system",
                    "type": "message",
                    "content": rendered_system_message,
                }

                # Create the version of messages that we'll send to the LLM
                messages_for_llm = interpreter.messages.copy()
                messages_for_llm = [rendered_system_message] + messages_for_llm

                if insert_loop_message:
                    messages_for_llm.append(
                        {
                            "role": "user",
                            "type": "message",
                            "content": interpreter.loop_message,
                        }
                    )
                    # Yield two newlines to separate the LLMs reply from previous messages.
                    yield {"role": "assistant", "type": "message", "content": "\n\n"}
                    insert_loop_message = False

            ### RUN THE LLM ###
            assert (
                len(interpreter.messages) > 0
            ), "User message was not passed in. You need to pass in at least one message."

            if (
                interpreter.messages[-1]["type"] != "code"
            ):  # If it is, we should run the code (we do below)
                try:
                    # Track LLM API call performance
                    with PerformanceTimer(
                        "llm", "api_call", {"model": interpreter.llm.model}
                    ):
                        message_count += 1
                        for chunk in interpreter.llm.run(messages_for_llm):
                            yield chunk

                except litellm.exceptions.BudgetExceededError:
                    interpreter.display_message(
                        f"""> Max budget exceeded

                        **Session spend:** ${litellm._current_cost}
                        **Max budget:** ${interpreter.max_budget}

                        Press CTRL-C then run `interpreter --max_budget [higher USD amount]` to proceed.
                    """
                    )
                    break

                except Exception as e:
                    error_message = str(e).lower()
                    if (
                        interpreter.offline == False
                        and "auth" in error_message
                        or "api key" in error_message
                    ):
                        output = traceback.format_exc()
                        raise Exception(
                            f"{output}\n\nThere might be an issue with your API key(s).\n\nTo reset your API key (we'll use OPENAI_API_KEY for this example, but you may need to reset your ANTHROPIC_API_KEY, HUGGINGFACE_API_KEY, etc):\n        Mac/Linux: 'export OPENAI_API_KEY=your-key-here'. Update your ~/.zshrc on MacOS or ~/.bashrc on Linux with the new key if it has already been persisted there.,\n        Windows: 'setx OPENAI_API_KEY your-key-here' then restart terminal.\n\n"
                        )
                    elif (
                        type(e) == litellm.exceptions.RateLimitError
                        and "exceeded" in str(e).lower()
                        or "insufficient_quota" in str(e).lower()
                    ):
                        interpreter.display_message(
                            f""" > You ran out of current quota for OpenAI's API, please check your plan and billing details. You can either wait for the quota to reset or upgrade your plan.

                            To check your current usage and billing details, visit the [OpenAI billing page](https://platform.openai.com/settings/organization/billing/overview).

                            You can also use `interpreter --max_budget [higher USD amount]` to set a budget for your sessions.
                            """
                        )

                    elif (
                        interpreter.offline == False
                        and "not have access" in str(e).lower()
                    ):
                        """
                        Check for invalid model in error message and then fallback.
                        """
                        if (
                            "invalid model" in error_message
                            or "model does not exist" in error_message
                        ):
                            provider_message = f"\n\nThe model '{interpreter.llm.model}' does not exist or is invalid. Please check the model name and try again.\n\nWould you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "
                        elif "groq" in error_message:
                            provider_message = f"\n\nYou don't currently have access to '{interpreter.llm.model}' on Groq. Would you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "
                        elif "outdated" in error_message and "library" in error_message:
                            provider_message = f"\n\nYou need to update 'litellm', which Open Interpreter uses to talk to language models. Run `pip install litellm --upgrade`. If you're using Open Interpreter 0.2.0 or higher, try `interpreter --update` to fix this more easily. Would you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "
                        elif "claude" in error_message:
                            provider_message = f"\n\nYou need an API key from Anthropic to use Claude models like '{interpreter.llm.model}'. Would you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "
                        else:
                            provider_message = f"\n\nYou don't currently have access to '{interpreter.llm.model}'. Would you like to try Open Interpreter's hosted `i` model instead? (y/n)\n\n  "

                        user_response = input(provider_message)

                        if user_response.strip().lower() == "y":
                            interpreter.llm.model = "i"
                            interpreter.llm.api_key = (
                                None  # Reset, will pull from env if exists
                            )
                            interpreter.llm.api_base = None
                            interpreter.display_message(
                                "\n\nNow using Open Interpreter's hosted i model.\n\n"
                            )
                            continue  # Retry with the hosted model
                        else:
                            interpreter.display_message(
                                "\n\nIf you'd like help setting up your API key, visit https://docs.openinterpreter.com/language-models/intro\n\n"
                            )
                            break  # Exit
                    elif interpreter.offline and not interpreter.os:
                        interpreter.display_message(
                            "\n\nTo use offline models, install `interpreter[local]`, e.g. `pip install 'open-interpreter[local]'`. See https://docs.openinterpreter.com/local/local"
                        )
                        break
                    else:
                        output = traceback.format_exc()
                        # For other types of errors, print the traceback
                        raise Exception(output) from e

            ### RUN CODE (if it's there) ###

            if interpreter.messages[-1]["type"] == "code":
                # Performance tracking for code execution
                code_execution_start = time.time()
                code_execution_count += 1

                if interpreter.verbose:
                    print("Running code:", interpreter.messages[-1])

                try:
                    # What language/code do you want to run?
                    language = interpreter.messages[-1]["format"].lower().strip()
                    code = interpreter.messages[-1]["content"]

                    # Handle various code formatting edge cases
                    if code.startswith("`\n"):
                        code = code[2:]

                    if code.strip().endswith("```"):
                        code = code.strip()[:-3]

                    if code.startswith("```"):
                        code = code[3:]
                        # Extract language if present in code fence
                        if "\n" in code:
                            maybe_language, rest_of_code = code.split("\n", 1)
                            if (
                                maybe_language.strip()
                                and not maybe_language.strip()[0] in "!@#$%^&*()"
                            ):
                                language = maybe_language.strip()
                                code = rest_of_code

                    # Handle common hallucinations
                    if code.strip().endswith("executeexecute"):
                        code = code.strip()[:-12]

                    # Handle JSON-formatted code objects
                    if (
                        code.replace("\n", "")
                        .replace(" ", "")
                        .startswith('{"language":')
                    ):
                        try:
                            code_object = json.loads(code)
                            language = code_object.get("language", language)
                            code = code_object.get("code", code)
                        except:
                            pass

                    if code.replace("\n", "").replace(" ", "").startswith("{language:"):
                        try:
                            # This isn't valid JSON, but language models sometimes output this
                            # Extract with regex
                            language_match = re.search(
                                r'{language:\s*[\'"]?(.*?)[\'"]?,', code
                            )
                            code_match = re.search(
                                r'code:\s*[\'"]?(.*?)[\'"]?}', code, re.DOTALL
                            )
                            if language_match:
                                language = language_match.group(1)
                            if code_match:
                                code = code_match.group(1)
                        except:
                            pass

                    # Handle text or markdown content differently
                    if (
                        language == "text"
                        or language == "markdown"
                        or language == "plaintext"
                    ):
                        yield {
                            "role": "assistant",
                            "type": "message",
                            "content": code,
                        }
                        continue

                    # Check if language is supported
                    if interpreter.computer.terminal.get_language(language) == None:
                        yield {
                            "role": "assistant",
                            "type": "message",
                            "content": f"I apologize, but I don't know how to execute `{language}` code. I can help you with Python, JavaScript, shell scripts, and many other languages though!",
                        }
                        # Store this for future reference
                        last_unsupported_code = code
                        continue

                    # Check if there's any code to run
                    if code.strip() == "":
                        yield {
                            "role": "assistant",
                            "type": "message",
                            "content": "It seems the code block is empty. Can you please provide the code you'd like me to execute?",
                        }
                        continue

                    # Yield a message to allow user to interrupt code execution
                    try:
                        yield {
                            "role": "computer",
                            "type": "confirmation",
                            "format": language,
                            "content": code,
                        }
                    except GeneratorExit:
                        raise

                    # They may have edited the code! Grab it again
                    code = [m for m in interpreter.messages if m["type"] == "code"][-1][
                        "content"
                    ]

                    # Don't let it import computer — we handle that!
                    if (
                        interpreter.computer.import_computer_api
                        and language == "python"
                    ):
                        # If we're importing computer, we want to make sure we don't import computer again
                        if (
                            "import computer" in code.lower()
                            and "# import computer" not in code.lower()
                        ):
                            if "import computer" in code:
                                code = code.replace(
                                    "import computer",
                                    "# import computer (already imported)",
                                )
                            if "from computer" in code:
                                code = code.replace(
                                    "from computer",
                                    "# from computer (already imported)",
                                )

                    # Synchronize settings to improve performance
                    interpreter.computer.verbose = interpreter.verbose
                    interpreter.computer.debug = interpreter.debug
                    interpreter.computer.emit_images = interpreter.llm.supports_vision
                    interpreter.computer.max_output = interpreter.max_output

                    # Synchronize computer state if needed (in a background thread to avoid blocking)
                    if interpreter.sync_computer:

                        def sync_computer():
                            try:
                                if hasattr(interpreter.computer, "sync"):
                                    interpreter.computer.sync()
                            except Exception as e:
                                if interpreter.debug:
                                    print(f"Computer sync error: {str(e)}")

                        # Run sync in background if it's not a critical operation
                        threading.Thread(target=sync_computer).start()

                    ## ↓ CODE IS RUN HERE
                    for line in interpreter.computer.run(language, code, stream=True):
                        yield {"role": "computer", **line}

                    ## ↑ CODE IS RUN HERE

                    # Log code execution performance
                    execution_time = time.time() - code_execution_start
                    log_performance_metric(
                        "code_execution",
                        language,
                        execution_time,
                        {
                            "code_length": len(code),
                            "execution_count": code_execution_count,
                        },
                    )

                    # Synchronize computer state after execution if needed
                    if interpreter.sync_computer and language == "python":
                        try:
                            # Extract computer state as a Python dict
                            result = interpreter.computer.run(
                                "python",
                                """
                                import json
                                computer_dict = computer.to_dict()
                                if '_hashes' in computer_dict:
                                    computer_dict.pop('_hashes')
                                if "system_message" in computer_dict:
                                    computer_dict.pop("system_message")
                                print(json.dumps(computer_dict))
                                """,
                                stream=False,
                            )
                            # Process the result only if successful
                            if result and len(result) > 0:
                                result_content = result[-1].get("content", "").strip()
                                if result_content:
                                    try:
                                        computer_dict = json.loads(
                                            result_content.strip('"').strip("'")
                                        )
                                        interpreter.computer.load_dict(computer_dict)
                                    except json.JSONDecodeError:
                                        if interpreter.debug:
                                            print(
                                                "Failed to parse computer state as JSON"
                                            )
                        except Exception as e:
                            if interpreter.debug:
                                print(f"Error synchronizing computer state: {str(e)}")

                    # Send active_line = None to clear any active line highlighting
                    yield {
                        "role": "computer",
                        "type": "console",
                        "format": "active_line",
                        "content": None,
                    }

                except KeyboardInterrupt:
                    # Handle user interruption gracefully
                    yield {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": "\n[Code execution interrupted by user]",
                    }
                    break

                except Exception as e:
                    # Log the exception and return it to the user
                    error_traceback = traceback.format_exc()
                    log_performance_metric(
                        "code_execution",
                        language,
                        time.time() - code_execution_start,
                        {
                            "code_length": len(code),
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                        level=1,
                    )  # Log at critical level

                    yield {
                        "role": "computer",
                        "type": "console",
                        "format": "output",
                        "content": error_traceback,
                    }

                # Explicitly clear any temp variables to help with memory usage
                if "language" in locals():
                    del language
                if "code" in locals():
                    del code
                if "result" in locals():
                    del result

            else:
                ## LOOP MESSAGE
                # This makes it utter specific phrases if it doesn't want to be told to "Proceed."
                loop_message = interpreter.loop_message
                if interpreter.os:
                    loop_message = loop_message.replace(
                        "If the entire task I asked for is done,",
                        "If the entire task I asked for is done, take a screenshot to verify it's complete, or if you've already taken a screenshot and verified it's complete,",
                    )
                loop_breakers = interpreter.loop_breakers

                if (
                    interpreter.loop
                    and interpreter.messages
                    and interpreter.messages[-1].get("role", "") == "assistant"
                    and not any(
                        task_status in interpreter.messages[-1].get("content", "")
                        for task_status in loop_breakers
                    )
                ):
                    # Remove past loop_message messages for cleaner history
                    interpreter.messages = [
                        message
                        for message in interpreter.messages
                        if message.get("content", "") != loop_message
                    ]

                    # Combine adjacent assistant messages for better context
                    with PerformanceTimer("message_processing", "combine_messages"):
                        combined_messages = []
                        for message in interpreter.messages:
                            if (
                                combined_messages
                                and message.get("role") == "assistant"
                                and combined_messages[-1].get("role") == "assistant"
                                and message.get("type") == "message"
                                and combined_messages[-1].get("type") == "message"
                            ):
                                # Combine this message with the previous one
                                combined_messages[-1][
                                    "content"
                                ] += "\n\n" + message.get("content", "")
                            else:
                                # Add as a new message
                                combined_messages.append(message)

                        interpreter.messages = combined_messages

                    # Send model the loop_message:
                    insert_loop_message = True
                    continue

                # Doesn't want to run code. We're done!
                break

    except Exception as e:
        # Log any unexpected exceptions
        log_performance_metric(
            "respond",
            "error",
            time.time() - overall_start_time,
            {"error": str(e), "error_type": type(e).__name__},
            level=1,
        )
        raise
    finally:
        # Log overall performance metrics for the entire response cycle
        overall_duration = time.time() - overall_start_time
        log_performance_metric(
            "respond",
            "complete",
            overall_duration,
            {
                "message_count": message_count,
                "code_execution_count": code_execution_count,
            },
        )

    return
