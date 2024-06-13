import pyaudio
import numpy as np
import whisper
import time
import threading

# Load Whisper model
model = whisper.load_model("base.en")

# Parameters for recording
CHUNK = 256  # Buffer size
FORMAT = pyaudio.paInt16  # Audio format
CHANNELS = 1  # Number of audio channels
RATE = 16000  # Sample rate
BUFFER_SECONDS = 5  # Duration of audio to buffer for each transcription
SILENCE_THRESHOLD = 500  # Threshold for considering silence
SILENCE_DURATION = 3  # Duration of silence to trigger pause

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open a stream
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

# Thread-safe buffer for audio data
buffer = []
pause_event = threading.Event()  # Event to control pausing
buffer_lock = threading.Lock()

def record_audio():
    global buffer
    print("Recording...")
    silence_start = None
    try:
        while True:
            if pause_event.is_set():
                time.sleep(0.1)
                continue

            data = stream.read(CHUNK)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            with buffer_lock:
                buffer.append(data)

            # Detect silence
            if np.max(audio_chunk) < SILENCE_THRESHOLD:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= SILENCE_DURATION:
                    print("Silence detected, pausing transcription.")
                    pause_event.set()
            else:
                silence_start = None

            # Limit buffer size to BUFFER_SECONDS of audio
            if len(buffer) > int(RATE / CHUNK * BUFFER_SECONDS):
                with buffer_lock:
                    buffer = buffer[-int(RATE / CHUNK * BUFFER_SECONDS):]

    except KeyboardInterrupt:
        print("Stopping...")

def transcribe_audio():
    global buffer
    while True:
        if pause_event.is_set():
            time.sleep(0.1)
            continue

        time.sleep(BUFFER_SECONDS)
        with buffer_lock:
            if buffer:
                audio_data = np.frombuffer(b''.join(buffer), dtype=np.int16).astype(np.float32) / 32768.0
                buffer = []

        if len(audio_data) > 0:
            result = model.transcribe(audio_data)
            yield result["text"]

def manual_pause_resume():
    if pause_event.is_set():
        print("Resuming transcription.")
        pause_event.clear()
    else:
        print("Pausing transcription.")
        pause_event.set()

# Start recording and transcribing threads
recording_thread = threading.Thread(target=record_audio)
recording_thread.start()

def main():
    transcription_generator = transcribe_audio()
    while True:
        try:
            transcription = next(transcription_generator)
            print("Transcription:", transcription)
        except StopIteration:
            break
        except KeyboardInterrupt:
            print("Exiting...")
            break

    # Close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == "__main__":
    main()

# Example manual pause/resume usage
try:
    while True:
        command = input("Enter 'pause' to pause, 'resume' to resume: ")
        if command == 'pause' or command == 'resume':
            manual_pause_resume()
except KeyboardInterrupt:
    print("Exiting...")

# Join threads to main thread
recording_thread.join()
