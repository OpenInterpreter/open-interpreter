from ..utils.display_markdown_message import display_markdown_message
import inquirer
import ooba

def setup_local_text_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a text LLM (an OpenAI-compatible chat LLM with baked-in settings. Only takes `messages`).
    """

    repo_id = interpreter.model.replace("huggingface/", "")

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

    ooba_llm = ooba.llm(path)
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

        if interpreter.debug_mode:
            print("Messages going to ooba:", messages)

        for token in ooba_llm.chat(messages):

            chunk = {
                "choices": [
                    {
                        "delta": {
                            "content": token
                        }
                    }
                ]
            }

            yield chunk
      
    return local_text_llm