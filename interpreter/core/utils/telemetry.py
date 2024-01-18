"""
Sends anonymous telemetry to posthog. This helps us know how people are using OI / what needs our focus.

Disable this by running `interpreter --disable_telemetry` or `interpreter.anonymized_telemetry = False` or setting the `ANONYMIZED_TELEMETRY` os var to `false`.

based on ChromaDB's telemetry: https://github.com/chroma-core/chroma/tree/main/chromadb/telemetry/product
"""

import contextlib
import os
import uuid

import pkg_resources
from posthog import Posthog

posthog = Posthog(
    "phc_6cmXy4MEbLfNGezqGjuUTY8abLu0sAwtGzZFpQW97lc", host="https://app.posthog.com"
)


def get_or_create_uuid():
    try:
        uuid_file_path = os.path.join(
            os.path.expanduser("~"), ".cache", "open-interpreter", "telemetry_user_id"
        )
        os.makedirs(
            os.path.dirname(uuid_file_path), exist_ok=True
        )  # Ensure the directory exists

        if os.path.exists(uuid_file_path):
            with open(uuid_file_path, "r") as file:
                return file.read()
        else:
            new_uuid = str(uuid.uuid4())
            with open(uuid_file_path, "w") as file:
                file.write(new_uuid)
            return new_uuid
    except:
        # Non blocking
        return "idk"


user_id = get_or_create_uuid()


def send_telemetry(event_name, properties=None):
    try:
        if properties == None:
            properties = {}
        properties["oi_version"] = pkg_resources.get_distribution(
            "open-interpreter"
        ).version
        with open(os.devnull, "w") as f, contextlib.redirect_stdout(
            f
        ), contextlib.redirect_stderr(f):
            posthog.capture(user_id, event_name, properties)
    except:
        # Non blocking
        pass
