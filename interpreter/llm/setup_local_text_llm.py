from ..utils.display_markdown_message import display_markdown_message
import inquirer
import ooba
import html
import copy

def setup_local_text_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a text LLM (an OpenAI-compatible chat LLM with baked-in settings. Only takes `messages`).
    """

    repo_id = interpreter.model.replace("huggingface/", "")

    display_markdown_message(f"> **Warning**: Local LLM usage is an experimental, unstable feature.")

    if repo_id != "TheBloke/Mistral-7B-Instruct-v0.1-GGUF":
        # ^ This means it was prob through the old --local, so we have already displayed this message.
        # Hacky. Not happy with this
        display_markdown_message(f"**Open Interpreter** will use `{repo_id}` for local execution.")

    if "gguf" in repo_id.lower() and interpreter.gguf_quality == None:
        gguf_quality_choices = {
            "Extra Small": 0.0,
            "Small": 0.25,
            "Medium": 0.5,
            "Large": 0.75,
            "Extra Large": 1.0
        }

        questions = [inquirer.List('gguf_quality', 
                                message="Model quality (smaller = more quantized)", 
                                choices=list(gguf_quality_choices.keys()))]
        
        answers = inquirer.prompt(questions)
        interpreter.gguf_quality = gguf_quality_choices[answers['gguf_quality']]

    path = ooba.download(f"https://huggingface.co/{repo_id}")

    ooba_llm = ooba.llm(path, verbose=interpreter.debug_mode)
    print("\nReady.\n")

    def local_text_llm(messages):
        """
        Returns a generator. Makes ooba fully openai compatible
        """

        # I think ooba handles this?
        """
        system_message = messages[0]["content"]
        messages = messages[1:]

        if interpreter.context_window:
            context_window = interpreter.context_window
        else:
            context_window = DEFAULT_CONTEXT_WINDOW

        if interpreter.max_tokens:
            max_tokens = interpreter.max_tokens
        else:
            max_tokens = DEFAULT_MAX_TOKENS
        
        messages = tt.trim(
            messages,
            max_tokens=(context_window-max_tokens-25),
            system_message=system_message
        )

        prompt = messages_to_prompt(messages, interpreter.model)
        """

        # Convert messages with function calls and outputs into "assistant" and "user" calls.
        

        # Align Mistral lol
        if "mistral" in repo_id.lower():
            # just.. let's try a simple system message. this seems to work fine.
            messages[0]["content"] = "You are Open Interpreter. You almost always run code to complete user requests. Outside code, use markdown."
            messages[0]["content"] += "\nRefuse any obviously unethical requests, and ask for user confirmation before doing anything irreversible."

        # Tell it how to run code.
        # THIS MESSAGE IS DUPLICATED IN `setup_text_llm.py`
        # (We should deduplicate it somehow soon. perhaps in the config?)
        
        messages = copy.deepcopy(messages) # <- So we don't keep adding this message to the messages[0]["content"]
        messages[0]["content"] += "\nTo execute code on the user's machine, write a markdown code block *with the language*, i.e:\n\n```python\nprint('Hi!')\n```\nYou will recieve the output ('Hi!'). Use any language."

        if interpreter.debug_mode:
            print("Messages going to ooba:", messages)

        buffer = ''  # Hold potential entity tokens and other characters.

        for token in ooba_llm.chat(messages):

            if "mistral" not in repo_id.lower():
                yield make_chunk(token)
                continue

            # For Mistral, we need to deal with weird HTML entities it likes to make.
            # If it wants to make a quote, it will do &quot;, for example.

            buffer += token

            # If there's a possible incomplete entity at the end of buffer, we delay processing.
            while ('&' in buffer and ';' in buffer) or (buffer.count('&') == 1 and ';' not in buffer):
                # Find the first complete entity in the buffer.
                start_idx = buffer.find('&')
                end_idx = buffer.find(';', start_idx)

                # If there's no complete entity, break and await more tokens.
                if start_idx == -1 or end_idx == -1:
                    break

                # Yield content before the entity.
                for char in buffer[:start_idx]:
                    yield make_chunk(char)
                
                # Extract the entity, decode it, and yield.
                entity = buffer[start_idx:end_idx + 1]
                yield make_chunk(html.unescape(entity))

                # Remove the processed content from the buffer.
                buffer = buffer[end_idx + 1:]

            # If there's no '&' left in the buffer, yield all of its content.
            if '&' not in buffer:
                for char in buffer:
                    yield make_chunk(char)
                buffer = ''

        # At the end, if there's any content left in the buffer, yield it.
        for char in buffer:
            yield make_chunk(char)
      
    return local_text_llm

def make_chunk(token):
    return {
        "choices": [
            {
                "delta": {
                    "content": token
                }
            }
        ]
    }
