import os
import platform
import time
from random import randint

import pytest

import interpreter
from interpreter.terminal_interface.utils.count_tokens import (
    count_messages_tokens,
    count_tokens,
)


# this function will run before each test
# we're clearing out the messages Array so we can start fresh and reduce token usage
def setup_function():
    interpreter.reset()
    interpreter.temperature = 0
    interpreter.auto_run = True
    interpreter.model = "gpt-3.5-turbo"
    interpreter.debug_mode = False


# this function will run after each test
# we're introducing some sleep to help avoid timeout issues with the OpenAI API
def teardown_function():
    time.sleep(4)


@pytest.mark.skip(reason="Mac only + no way to fail test")
def test_spotlight():
    interpreter.computer.keyboard.hotkey("command", "space")


def test_config_loading():
    # because our test is running from the root directory, we need to do some
    # path manipulation to get the actual path to the config file or our config
    # loader will try to load from the wrong directory and fail
    currentPath = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(currentPath, "./config.test.yaml")

    interpreter.extend_config(config_path=config_path)

    # check the settings we configured in our config.test.yaml file
    temperature_ok = interpreter.temperature == 0.25
    model_ok = interpreter.model == "gpt-3.5-turbo"
    debug_mode_ok = interpreter.debug_mode == True

    assert temperature_ok and model_ok and debug_mode_ok


def test_files():
    messages = [
        {"role": "user", "type": "message", "content": "Does this file exist?"},
        {
            "role": "user",
            "type": "file",
            "format": "path",
            "content": "/Users/Killian/image.png",
        },
    ]
    interpreter.chat(messages)


@pytest.mark.skip(reason="Only 100 vision calls allowed / day!")
def test_vision():
    base64png = "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAIAAADTED8xAAADMElEQVR4nOzVwQnAIBQFQYXff81RUkQCOyDj1YOPnbXWPmeTRef+/3O/OyBjzh3CD95BfqICMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMK0CMO0TAAD//2Anhf4QtqobAAAAAElFTkSuQmCC"
    messages = [
        {"role": "user", "type": "message", "content": "describe this image"},
        {
            "role": "user",
            "type": "image",
            "format": "base64.png",
            "content": base64png,
        },
    ]

    interpreter.vision = True
    interpreter.model = "gpt-4-vision-preview"
    interpreter.system_message += "\nThe user will show you an image of the code you write. You can view images directly.\n\nFor HTML: This will be run STATELESSLY. You may NEVER write '<!-- previous code here... --!>' or `<!-- header will go here -->` or anything like that. It is CRITICAL TO NEVER WRITE PLACEHOLDERS. Placeholders will BREAK it. You must write the FULL HTML CODE EVERY TIME. Therefore you cannot write HTML piecemeal—write all the HTML, CSS, and possibly Javascript **in one step, in one code block**. The user will help you review it visually.\nIf the user submits a filepath, you will also see the image. The filepath and user image will both be in the user's message.\n\nIf you use `plt.show()`, the resulting image will be sent to you. However, if you use `PIL.Image.show()`, the resulting image will NOT be sent to you."
    interpreter.function_calling_llm = False
    interpreter.context_window = 110000
    interpreter.max_tokens = 4096
    interpreter.force_task_completion = True

    interpreter.chat(messages)


def test_generator():
    """
    Sends two messages, makes sure everything is correct with display both on and off.
    """

    for tests in [
        {"query": "What's 38023*40334?", "display": True},
        {"query": "What's 2334*34335555?", "display": True},
        {"query": "What's 3545*22?", "display": False},
        {"query": "What's 0.0021*3433335555?", "display": False},
    ]:
        assistant_message_found = False
        console_output_found = False
        active_line_found = False
        flag_checker = []
        for chunk in interpreter.chat(
            tests["query"]
            + "\nNo talk or plan, just immediatly code, then tell me the answer.",
            stream=True,
            display=tests["display"],
        ):
            print(chunk)
            # Check if chunk has the right schema
            assert "role" in chunk, "Chunk missing 'role'"
            assert "type" in chunk, "Chunk missing 'type'"
            if "start" not in chunk and "end" not in chunk:
                assert "content" in chunk, "Chunk missing 'content'"
            if "format" in chunk:
                assert isinstance(chunk["format"], str), "'format' should be a string"

            flag_checker.append(chunk)

            # Check if assistant message, console output, and active line are found
            if chunk["role"] == "assistant" and chunk["type"] == "message":
                assistant_message_found = True
            if chunk["role"] == "computer" and chunk["type"] == "console":
                console_output_found = True
            if "format" in chunk:
                if (
                    chunk["role"] == "computer"
                    and chunk["type"] == "console"
                    and chunk["format"] == "active_line"
                ):
                    active_line_found = True

        # Ensure all flags are proper
        assert (
            flag_checker.count(
                {"role": "assistant", "type": "code", "format": "python", "start": True}
            )
            == 1
        ), "Incorrect number of 'assistant code start' flags"
        assert (
            flag_checker.count(
                {"role": "assistant", "type": "code", "format": "python", "end": True}
            )
            == 1
        ), "Incorrect number of 'assistant code end' flags"
        assert (
            flag_checker.count({"role": "assistant", "type": "message", "start": True})
            == 1
        ), "Incorrect number of 'assistant message start' flags"
        assert (
            flag_checker.count({"role": "assistant", "type": "message", "end": True})
            == 1
        ), "Incorrect number of 'assistant message end' flags"
        assert (
            flag_checker.count({"role": "computer", "type": "console", "start": True})
            == 1
        ), "Incorrect number of 'computer console output start' flags"
        assert (
            flag_checker.count({"role": "computer", "type": "console", "end": True})
            == 1
        ), "Incorrect number of 'computer console output end' flags"

        # Assert that assistant message, console output, and active line were found
        assert assistant_message_found, "No assistant message was found"
        assert console_output_found, "No console output was found"
        assert active_line_found, "No active line was found"


def test_multiple_instances():
    import interpreter

    interpreter.system_message = "i"
    agent_1 = interpreter.Interpreter()
    agent_1.system_message = "<3"
    agent_2 = interpreter.Interpreter()
    agent_2.system_message = "u"

    assert interpreter.system_message == "i"
    assert agent_1.system_message == "<3"
    assert agent_2.system_message == "u"


def test_hello_world():
    hello_world_response = "Hello, World!"

    hello_world_message = f"Please reply with just the words {hello_world_response} and nothing else. Do not run code. No confirmation just the text."

    messages = interpreter.chat(hello_world_message)

    assert messages == [
        {"role": "user", "type": "message", "content": hello_world_message},
        {"role": "assistant", "type": "message", "content": hello_world_response},
    ]


def test_math():
    # we'll generate random integers between this min and max in our math tests
    min_number = randint(1, 99)
    max_number = randint(1001, 9999)

    n1 = randint(min_number, max_number)
    n2 = randint(min_number, max_number)

    test_result = n1 + n2 * (n1 - n2) / (n2 + n1)

    order_of_operations_message = f"""
    Please perform the calculation `{n1} + {n2} * ({n1} - {n2}) / ({n2} + {n1})` then reply with just the answer, nothing else. No confirmation. No explanation. No words. Do not use commas. Do not show your work. Just return the result of the calculation. Do not introduce the results with a phrase like \"The result of the calculation is...\" or \"The answer is...\"
    
    Round to 2 decimal places.
    """.strip()

    print("loading")
    messages = interpreter.chat(order_of_operations_message)
    print("done")

    assert str(round(test_result, 2)) in messages[-1]["content"]


def test_break_execution():
    """
    Breaking from the generator while it's executing should halt the operation.
    """

    code = r"""print("starting")
import time                                                                                                                                
import os                                                                                                                                  
                                                                                                                                            
# Always create a fresh file
open('numbers.txt', 'w').close()
                                                                                                                                            
# Open the file in append mode                                                                                                             
with open('numbers.txt', 'a+') as f:                                                                                                        
    # Loop through the numbers 1 to 5                                                                                                      
    for i in [1,2,3,4,5]:                                                                                                                  
        # Print the number                                                                                                                 
        print("adding", i, "to file")                                                                                                                           
        # Append the number to the file                                                                                                    
        f.write(str(i) + '\n')                                                                                                             
        # Wait for 0.5 second
        print("starting to sleep")
        time.sleep(1)
        # # Read the file to make sure the number is in there
        # # Move the seek pointer to the start of the file
        # f.seek(0)
        # # Read the file content
        # content = f.read()
        # print("Current file content:", content)
        # # Check if the current number is in the file content
        # assert str(i) in content
        # Move the seek pointer to the end of the file for the next append operation
        f.seek(0, os.SEEK_END)
        """
    print("starting to code")
    for chunk in interpreter.computer.run("python", code):
        print(chunk)
        if "format" in chunk and chunk["format"] == "output":
            if "adding 3 to file" in chunk["content"]:
                print("BREAKING")
                break

    time.sleep(3)

    # Open the file and read its content
    with open("numbers.txt", "r") as f:
        content = f.read()

    # Check if '1' and '5' are in the content
    assert "1" in content
    assert "5" not in content


def test_delayed_exec():
    interpreter.chat(
        """Can you write a single block of code and execute it that prints something, then delays 1 second, then prints something else? No talk just code. Thanks!"""
    )


def test_nested_loops_and_multiple_newlines():
    interpreter.chat(
        """Can you write a nested for loop in python and shell and run them? Don't forget to properly format your shell script and use semicolons where necessary. Also put 1-3 newlines between each line in the code. Only generate and execute the code. No explanations. Thanks!"""
    )


def test_write_to_file():
    interpreter.chat("""Write the word 'Washington' to a .txt file called file.txt""")
    assert os.path.exists("file.txt")
    interpreter.messages = []  # Just reset message history, nothing else for this test
    messages = interpreter.chat(
        """Read file.txt in the current directory and tell me what's in it."""
    )
    assert "Washington" in messages[-1]["content"]


def test_markdown():
    interpreter.chat(
        """Hi, can you test out a bunch of markdown features? Try writing a fenced code block, a table, headers, everything. DO NOT write the markdown inside a markdown code block, just write it raw."""
    )


def test_system_message_appending():
    ping_system_message = (
        "Respond to a `ping` with a `pong`. No code. No explanations. Just `pong`."
    )

    ping_request = "ping"
    pong_response = "pong"

    interpreter.system_message += ping_system_message

    messages = interpreter.chat(ping_request)

    assert messages == [
        {"role": "user", "type": "message", "content": ping_request},
        {"role": "assistant", "type": "message", "content": pong_response},
    ]


def test_reset():
    # make sure that interpreter.reset() clears out the messages Array
    assert interpreter.messages == []


def test_token_counter():
    system_tokens = count_tokens(
        text=interpreter.system_message, model=interpreter.model
    )

    prompt = "How many tokens is this?"

    prompt_tokens = count_tokens(text=prompt, model=interpreter.model)

    messages = [
        {"role": "system", "message": interpreter.system_message}
    ] + interpreter.messages

    system_token_test = count_messages_tokens(
        messages=messages, model=interpreter.model
    )

    system_tokens_ok = system_tokens == system_token_test[0]

    messages.append({"role": "user", "message": prompt})

    prompt_token_test = count_messages_tokens(
        messages=messages, model=interpreter.model
    )

    prompt_tokens_ok = system_tokens + prompt_tokens == prompt_token_test[0]

    assert system_tokens_ok and prompt_tokens_ok
