

from ..utils.convert_to_openai_messages import convert_to_openai_messages
from .setup_text_llm import setup_text_llm

def convert_to_coding_llm(text_llm, debug_mode=False):
    """
    Takes a text_llm
    returns an OI Coding LLM (a generator that takes OI messages and streams deltas with `message`, 'language', and `code`).
    """

    def coding_llm(messages):
        messages = convert_to_openai_messages(messages)

        inside_code_block = False
        accumulated_block = ""
        language = None
        
        for chunk in text_llm(messages):

            if debug_mode:
                print("Chunk in coding_llm", chunk)
            
            content = chunk['choices'][0]['delta'].get('content', "")
            
            accumulated_block += content
            
            # Did we just enter a code block?
            if "```" in accumulated_block and not inside_code_block:
                inside_code_block = True
                accumulated_block = accumulated_block.split("```")[1]

            # Did we just exit a code block?
            if inside_code_block and "```" in accumulated_block:
                return

            # If we're in a code block,
            if inside_code_block:
                
                # If we don't have a `language`, find it
                if language is None and "\n" in accumulated_block:
                    language = accumulated_block.split("\n")[0]

                    # Default to python if not specified
                    if language == "":
                        language = "python"

                    output = {"language": language}

                    # If we recieved more than just the language in this chunk, send that
                    if content.split("\n")[1]:
                        output["code"] = content.split("\n")[1]
                    
                    yield output
                
                # If we do have a `language`, send the output as code
                elif language:
                    yield {"code": content}
            
            # If we're not in a code block, send the output as a message
            if not inside_code_block:
                yield {"message": content}

    return coding_llm