import speech_recognition as sr
import time

speech_mode = False


class SpeechRecognizer:
    def __init__(self, wake_word="jarvis"):
        self.r = sr.Recognizer()
        self.mic = sr.Microphone()
        self.wake_word = wake_word

    def listen_for_speech(self):
        """Listens for speech and returns the transcribed text."""
        with self.mic as source:
            print("Listening...")
            #            self.r.adjust_for_ambient_noise(source)
            audio = self.r.listen(source)

        try:
            text = self.r.recognize_google(audio)
            text = text[text.find(" ") + 1 :] if " " in text else text # Get rid of activation word
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            print("Could not understand audio")
            return ""
        except sr.RequestError as e:
            print(
                f"Could not request results from Google Speech Recognition service; {e}"
            )
            return ""


def cli_input(prompt: str = "") -> str:
    global speech_mode

    start_marker = '"""'
    end_marker = '"""'

    while True:
        if speech_mode:
            recognizer = SpeechRecognizer()
            text = recognizer.listen_for_speech()
            if text == "exit":
                print("Exiting speech recognition mode.")
                speech_mode = False
            elif text:
                return text
        else:
            message = input(prompt)
            # Speech recognition trigger
            if message == ">":
                speech_mode = True
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
