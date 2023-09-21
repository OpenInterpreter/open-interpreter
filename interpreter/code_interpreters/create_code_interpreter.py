"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

from .languages.python import Python
#from .languages.bash import Bash
#from .ruby import Ruby

def create_code_interpreter(language):
    language_map = {
        "python": Python,
        #"bash": Bash,
        #"shell": Bash,
        #"ruby": Ruby
    }

    try:
        CodeInterpreter = language_map[language]
        return CodeInterpreter()
    except KeyError:
        raise ValueError(f"Unknown or unsupported language: {language}")
