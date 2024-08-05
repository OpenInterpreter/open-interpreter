import sys

"""Return input from keyboard or speech recognition."""


class SpeechRecognizer:
    """Handle speech recognition using google. You must enable the API in the google cloud console."""

    """Join chroma-dev group when logged into gmail: https://groups.google.com/a/chromium.org/g/chromium-dev"""
    """Create project. Go to APIs and services -> Library. Search for speech. Enable Speech API."""
    """Go to API manager -> Credentials and create an API key."""

    def __init__(self, wake_word="jarvis"):
        self.speech_mode = False
        self.imported = False
        self.wake_word = wake_word

    def speak(self, val=None) -> bool:
        """Set speech mode. Called with no argument, return current value. Called with an argument, sets value."""
        if val == None:
            return self.speech_mode
        self.speech_mode = val
        return self.speech_mode

    def import_library(self) -> bool:
        """Check if the required libraries are installed, if not, load them and return loaded status."""
        if self.imported:
            return True
        try:
            import speech_recognition as sr

            self.sr = sr
            self.r = sr.Recognizer()
            self.mic = sr.Microphone()
            self.imported = True
            return True
        except ImportError:
            print(
                "Please install the SpeechRecognition and pyaudio libraries by executing the following commands:"
            )
            if sys.platform == "darwin":
                print("brew install portaudio")
            print("pip install SpeechRecognition pyaudio")
            return False

    def listen_for_speech(self) -> str:
        """Listens for speech and returns the transcribed text."""
        with self.mic as source:
            print("Listening...")
            # This might be good. More testing needed. Might work better without it.
            self.r.adjust_for_ambient_noise(source)
            audio = self.r.listen(source)

        try:
            text = self.r.recognize_google(audio)
            text = (
                text[text.find(" ") + 1 :] if " " in text else text
            )  # Get rid of activation word
            print(f"You said: {text}")
            return text
        except self.sr.UnknownValueError:
            print("Could not understand audio")
            return ""
        except self.sr.RequestError as e:
            print(
                f"Could not request results from Google Speech Recognition service; {e}"
            )
            return ""


recognizer = SpeechRecognizer()


def cli_input(prompt: str = "") -> str:
    """Return user input from keyboard or speech."""
    global recognizer
    start_marker = '"""'
    end_marker = '"""'

    while True:
        if recognizer.speak():
            print(prompt)
            text = recognizer.listen_for_speech()
            if text == "exit":
                print("Exiting speech recognition mode.")
                recognizer.speak(False)
            elif text:
                return text
        else:
            message = input(prompt)
            # Speech recognition trigger
            if message == ">":
                if recognizer.import_library():
                    recognizer.speak(True)
                    continue
                recognizer.import_library()
                recognizer.speak(True)
                continue  # Go back to the beginning of the loop for speech input

            # Multi-line input mode
            if start_marker in message:
                lines = [message]
                while True:
                    line = input()
                    lines.append(line)
                    if end_marker in line:
                        break
                return "\n".join(lines)

            # Single-line input mode
            return message


if __name__ == "__main__":
    while True:
        user_input = cli_input("Enter text or '>' for speech input: ")
        print(f"You entered: {user_input}")
