import os
from ..utils.display_markdown_message import display_markdown_message
import time


def validate_sandbox_settings(interpreter):
    """
    Interactively prompt the user for required sandbox settings
    """

    # This runs in a while loop so `continue` lets us start from the top
    # after changing settings (like switching to/from local)
    if interpreter.sandbox:
        while True:
            if not interpreter.e2b_api_key:
                display_markdown_message("""---
                > E2B API key not found

                To use `sandbox` please provide an E2B API key (https://e2b.dev/docs).

                ---
                """)

                response = input("E2B API key: ")

                display_markdown_message("""

                **Tip:** To save this key for later, run `export E2B_API_KEY=your_api_key` on Mac/Linux or `setx E2B_API_KEY your_api_key` on Windows.

                ---""")

                interpreter.e2B_api_key = response
                time.sleep(2)

            # API key is set, we're good to go
            break
