import speech_recognition as SR
import pyttsx3

class SpeechAssistant:
    def __init__(self, wakeup_word="interpreter"):
        self.wakeup_word = wakeup_word
        self.speech_recognizer = SR.Recognizer()
        # if os is windows use sapi5 else use nsss for mac os and espeak for linux
        self.engine = pyttsx3.init()

    def tts_and_play_audio(self, text):
        # stop if it is already speaking
        if self.engine._inLoop:
            print("inloop")
            self.engine.endLoop()
            self.engine.stop()
        self.engine.say(text)
        self.engine.runAndWait()

    def start_speech_recognition(self):
        while True:
            print("Listening for wakeup word...")
            with SR.Microphone() as mic:
                try:
                    self.speech_recognizer.adjust_for_ambient_noise(
                        mic, duration=0.4)
                    audio = self.speech_recognizer.listen(mic)

                    result = self.speech_recognizer.recognize_whisper(
                        audio, "base")
                    text = result
                    if self.wakeup_word in text:
                        print("Wakeup word", self.wakeup_word, "detected!")
                        print("You said:", text)
                        return text
                except SR.UnknownValueError:
                    pass
                except Exception as e:
                    print("Error:", str(e))
                finally:
                    pass


if __name__ == "__main__":
    assistant = SpeechAssistant(wakeup_word="interpreter")
    assistant.start_speech_recognition()
