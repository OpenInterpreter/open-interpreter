"""
 * Copyright (c) 2023 Killian Lucas
 * Licensed under the GNU Affero General Public License, Version 3.
 * See LICENSE in the project root for license information.
"""

from importlib import import_module

def create_code_interpreter(language, debug_mode=False):
    try:
        module = import_module(f'languages.{language}')
        # Get the names of all classes defined in the module
        class_names = [name for name, obj in vars(module).items() if isinstance(obj, type)]

        # Look for a class whose name, when made lowercase, matches the file/language name
        for class_name in class_names:
            if class_name.lower() == language:
                InterpreterClass = getattr(module, class_name)
                return InterpreterClass(debug_mode)

        raise ValueError(f"No matching class found in {language}.py. Make sure you have one class called `{language.capitalize()}`.")

    except ModuleNotFoundError:
        raise ValueError(f"Unknown or unsupported language: {language}")
