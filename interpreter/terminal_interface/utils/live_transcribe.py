import pyaudio
import numpy as np
import whisper
import time
import threading

class LiveTranscriber:
    def __init__(self, model_name="base", rate=16000, chunk=1024, buffer_seconds=5, silence_threshold=500, silence_duration=3):
        self.model = whisper.load_model(model_name)
        self.rate = rate
        self.chunk = chunk
        self.buffer_seconds = buffer_seconds
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.buffer = []
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.buffer_lock = threading.Lock()
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=self.rate,
                                  input=True,
                                  frames_per_buffer=self.chunk)
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.transcribing_thread = threading.Thread(target=self.transcribe_audio)
        self.transcription_generator = self._transcription_generator()

    def start(self):
        self.recording_thread.start()
        self.transcribing_thread.start()

    def stop(self):
        self.stop_event.set()
        self.recording_thread.join()
        self.transcribing_thread.join()
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        print("Stopped successfully.")

    def record_audio(self):
        print("Recording...")
        try:
            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue

                data = self.stream.read(self.chunk, exception_on_overflow=False)
                with self.buffer_lock:
                    self.buffer.append(data)

                if len(self.buffer) > int(self.rate / self.chunk * self.buffer_seconds):
                    with self.buffer_lock:
                        self.buffer = self.buffer[-int(self.rate / self.chunk * self.buffer_seconds):]

        except Exception as e:
            print(f"Recording error: {e}")
        finally:
            self.stop_event.set()

    def transcribe_audio(self):
        try:
            for transcription in self.transcription_generator:
                yield transcription
                #print("Transcription:", transcription)
        except Exception as e:
            print(f"Transcription error: {e}")
        finally:
            self.stop_event.set()

    def _transcription_generator(self):
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.1)
                continue

            time.sleep(self.buffer_seconds)
            with self.buffer_lock:
                if self.buffer:
                    audio_data = np.frombuffer(b''.join(self.buffer), dtype=np.int16).astype(np.float32) / 32768.0
                    self.buffer = []

            if len(audio_data) > 0:
                result = self.model.transcribe(audio_data)
                if result["text"].strip():
                    yield result["text"]

    def toggle_pause_resume(self):
        if self.pause_event.is_set():
            print("Resuming transcription.")
            self.pause_event.clear()
        else:
            print("Pausing transcription.")
            self.pause_event.set()
    
    def pause(self):
        print("Pausing transcription.")
        self.pause_event.set()
    
    def resume(self):
        print("Resuming transcription.")
        self.pause_event.clear()

if __name__ == "__main__":
    live_transcriber = LiveTranscriber()
    live_transcriber.start()

    for text in live_transcriber._transcription_generator():
        print(text)

    # Manual pause and resume control
    #live_transcriber.manual_pause_resume()  # Toggle pause/resume

