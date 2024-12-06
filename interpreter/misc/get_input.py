from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings


async def async_get_input(
    placeholder_text: Optional[str] = None,
    placeholder_color: str = "gray",
    multiline_support: bool = True,
) -> str:
    # placeholder_text = "Describe command"
    placeholder_text = 'Use """ for multi-line input'
    history = InMemoryHistory()
    session = PromptSession(
        history=history,
        enable_open_in_editor=False,
        enable_history_search=False,
        auto_suggest=None,
        multiline=True,
    )
    kb = KeyBindings()
    multiline = [False]

    @kb.add("enter")
    def _(event):
        current_line = event.current_buffer.document.current_line.rstrip()

        if not multiline[0] and current_line.endswith('"""'):
            # Enter multiline mode
            multiline[0] = True
            event.current_buffer.insert_text("\n")
            return

        if multiline[0] and current_line.startswith('"""'):
            # Exit multiline mode and submit
            multiline[0] = False
            event.current_buffer.validate_and_handle()
            return

        if multiline[0]:
            event.current_buffer.insert_text("\n")
        else:
            event.current_buffer.validate_and_handle()

    result = await session.prompt_async(
        "> ",
        placeholder=HTML(f'<style fg="{placeholder_color}">{placeholder_text}</style>')
        if placeholder_text
        else None,
        key_bindings=kb,
        complete_while_typing=False,
        enable_suspend=False,
        search_ignore_case=True,
        include_default_pygments_style=False,
        input_processors=[],
        enable_system_prompt=False,
    )
    return result


# def get_input(
#     placeholder_text: Optional[str] = None,
#     placeholder_color: str = "gray",
#     multiline_support: bool = True,
# ) -> str:
#     placeholder_text = "Describe command"
#     history = InMemoryHistory()
#     session = PromptSession(
#         history=history,
#         enable_open_in_editor=False,
#         enable_history_search=False,
#         auto_suggest=None,
#         multiline=True,
#     )
#     kb = KeyBindings()
#     multiline = [False]

#     @kb.add("enter")
#     def _(event):
#         current_line = event.current_buffer.document.current_line.rstrip()

#         if current_line == '"""':
#             multiline[0] = not multiline[0]
#             event.current_buffer.insert_text("\n")
#             if not multiline[0]:  # If exiting multiline mode, submit
#                 event.current_buffer.validate_and_handle()
#             return

#         if multiline[0]:
#             event.current_buffer.insert_text("\n")
#         else:
#             event.current_buffer.validate_and_handle()

#     result = session.prompt(
#         "> ",
#         placeholder=HTML(f'<style fg="{placeholder_color}">{placeholder_text}</style>')
#         if placeholder_text
#         else None,
#         key_bindings=kb,
#         complete_while_typing=False,
#         enable_suspend=False,
#         search_ignore_case=True,
#         include_default_pygments_style=False,
#         input_processors=[],
#         enable_system_prompt=False,
#     )
#     return result
