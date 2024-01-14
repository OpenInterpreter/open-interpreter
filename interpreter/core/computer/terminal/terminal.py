from ..utils.recipient_utils import parse_for_recipient
from .languages.applescript import AppleScript
from .languages.html import HTML
from .languages.javascript import JavaScript
from .languages.powershell import PowerShell
from .languages.python import Python
from .languages.r import R
from .languages.react import React
from .languages.shell import Shell

# Should this be renamed to OS or System?


class Terminal:
    def __init__(self):
        self.languages = [
            Python,
            Shell,
            JavaScript,
            HTML,
            AppleScript,
            R,
            PowerShell,
            React,
        ]
        self._active_languages = {}

    def get_language(self, language):
        for lang in self.languages:
            if language.lower() == lang.name.lower() or (
                hasattr(lang, "aliases") and language in lang.aliases
            ):
                return lang
        return None

    def run(self, language, code, stream=False, display=False):
        # If stream == False, *pull* from the stream.
        if stream == False:
            output_messages = []
            for chunk in self._streaming_chat(language, code, stream=True):
                if chunk.get("format") != "active_line":
                    # Should we append this to the last message, or make a new one?
                    if (
                        output_messages != []
                        and output_messages[-1].get("type") == chunk["type"]
                        and output_messages[-1].get("format") == chunk["format"]
                    ):
                        output_messages[-1]["content"] += chunk["content"]
                    else:
                        output_messages.append(chunk)
            return output_messages

        # This actually streams it:

        if language not in self._active_languages:
            self._active_languages[language] = self.get_language(language)()
        try:
            for chunk in self._active_languages[language].run(code):
                # self.format_to_recipient can format some messages as having a certain recipient.
                # Here we add that to the LMC messages:
                if chunk["type"] == "console" and chunk.get("format") == "output":
                    recipient, content = parse_for_recipient(chunk["content"])
                    if recipient:
                        chunk["recipient"] = recipient
                        chunk["content"] = content

                    # Sometimes, we want to hide the traceback to preserve tokens.
                    # (is this a good idea?)
                    if "@@@HIDE_TRACEBACK@@@" in content:
                        chunk["content"] = (
                            "Stopping execution.\n\n"
                            + content.split("@@@HIDE_TRACEBACK@@@")[-1].strip()
                        )

                yield chunk

                # Print it also if display = True
                if (
                    display
                    and chunk.get("format") != "active_line"
                    and chunk.get("content")
                ):
                    print(chunk["content"])

        except GeneratorExit:
            self.stop()

    def stop(self):
        for language in self._active_languages.values():
            language.stop()

    def terminate(self):
        for language_name in list(self._active_languages.keys()):
            language = self._active_languages[language_name]
            if (
                language
            ):  # Not sure why this is None sometimes. We should look into this
                language.terminate()
            del self._active_languages[language_name]
