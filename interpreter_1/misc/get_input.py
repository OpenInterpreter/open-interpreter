import readline


async def get_input(
    placeholder_text=None, placeholder_color: str = "gray", multiline_support=True
) -> str:
    return input("> ")
