"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

from .setup_text_llm import setup_text_llm
from .convert_to_coding_llm import convert_to_coding_llm
from .setup_openai_coding_llm import setup_openai_coding_llm
import os

def setup_llm(interpreter):
    """
    Takes an Interpreter (which includes a ton of LLM settings),
    returns a Coding LLM (a generator that streams deltas with `message` and `code`).
    """

    if not interpreter.local and "gpt-" in interpreter.model:
        # Function calling LLM
        coding_llm = setup_openai_coding_llm(interpreter)
    else:
        text_llm = setup_text_llm(interpreter)
        coding_llm = convert_to_coding_llm(text_llm)

    return coding_llm