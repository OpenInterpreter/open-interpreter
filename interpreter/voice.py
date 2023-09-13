import time
import threading
from mutagen.mp3 import MP3
from gtts import gTTS
import speech_recognition as SR
import pygame
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"


class SpeechAssistant:
    def __init__(self, wakeup_word="interpreter"):
        self.wakeup_word = wakeup_word
        self.speech_recognizer = SR.Recognizer()

    def tts_and_play_audio(self, text):
        language = 'en'
        speech = gTTS(text=text, lang=language, slow=False, tld='com.au')
        speech.save("speech.mp3")
        self.play_audio("speech.mp3")
        os.remove("speech.mp3")

    def play_audio(self, file_path):
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        audio = MP3(file_path)
        time.sleep(audio.info.length)
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        # Delete the file after playing it

    def start_speech_recognition(self):
        while True:
             print("Listening for wakeup word...")
             with SR.Microphone() as mic:
                   try:
                        self.speech_recognizer.adjust_for_ambient_noise(
                            mic, duration=0.4)
                        audio = self.speech_recognizer.listen(mic)
                        text = self.speech_recognizer.recognize_google(
                            audio, language="en-US")
                        text = str(text).lower()
                        if self.wakeup_word in text:
                            print("Wakeup word", self.wakeup_word, "detected!")
                            print("You said:", text)
                            return text
                   except SR.UnknownValueError:
                        pass
                   except Exception as e:
                        print("Error:", str(e))


if __name__ == "__main__":
    assistant = SpeechAssistant(wakeup_word="interpreter")
    assistant.start_speech_recognition()
