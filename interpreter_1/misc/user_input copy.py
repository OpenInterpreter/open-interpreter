# from prompt_toolkit import PromptSession
# from prompt_toolkit.formatted_text import HTML
# import os


def get_user_input(
    placeholder_text: str = "", placeholder_color: str = "ansigray", prompt_session=None
) -> str:
    """
    Get user input with support for multi-line input and fallback to standard input.

    Args:
        placeholder_text: Text to show as placeholder
        placeholder_color: Color of the placeholder text
        prompt_session: Optional PromptSession instance to use

    Returns:
        The user's input as a string
    """
    return input("> ")
    # Create placeholder HTML
    placeholder = HTML(f"<{placeholder_color}>{placeholder_text}</{placeholder_color}>")

    # Use provided prompt session or create new one
    if prompt_session is None:
        prompt_session = PromptSession()

    try:
        # Prompt toolkit requires terminal size to work properly
        # If this fails, prompt toolkit will look weird, so we fall back to standard input
        os.get_terminal_size()
        user_input = prompt_session.prompt(
            "> ",
            placeholder=placeholder,
        ).strip()
    except KeyboardInterrupt:
        raise
    except:
        user_input = input("> ").strip()
    print()

    # Handle multi-line input
    if user_input == '"""':
        user_input = ""
        while True:
            placeholder = HTML(
                f'<{placeholder_color}>Use """ again to finish</{placeholder_color}>'
            )
            line = prompt_session.prompt("", placeholder=placeholder).strip()
            if line == '"""':
                break
            user_input += line + "\n"
        print()

    return user_input
