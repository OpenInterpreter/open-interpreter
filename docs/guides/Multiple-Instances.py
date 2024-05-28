import whisper
import soundfile as sf
import re
from nltk.sentiment import SentimentIntensityAnalyzer
import os

# List of keywords to detect (you can expand this list)
moan_keywords = ['moan', 'ah', 'oh', 'uh', 'Carlos', 'Collin']
profanity_keywords = ['fuck', 'shit', 'bitch', 'asshole', 'pussy']

def remove_duplicate_phrases(text):
    sentences = text.split('. ')
    cleaned_sentences = []
    for i, sentence in enumerate(sentences):
        if i == 0 or sentence != sentences[i - 1]:
            cleaned_sentences.append(sentence)
    cleaned_text = '. '.join(cleaned_sentences)
    return cleaned_text

def highlight_keywords(text, keywords, highlight_color='red'):
    for keyword in keywords:
        text = re.sub(f'\\b{keyword}\\b', f'\033[1;31m{keyword}\033[0m', text, flags=re.IGNORECASE)
    return text

def transcribe_and_analyze(audio_path, model, sia):
    try:
        # Load the audio file
        data, samplerate = sf.read(audio_path, dtype='float32')

        # Check the duration of the audio file
        duration = len(data) / samplerate
        if duration > 3600:  # Limit to 1 hour for this example
            raise ValueError("Audio file is too long to process")

        print(f"Audio file loaded successfully. Duration: {duration:.2f} seconds")

        # Transcribe the audio file
        result = model.transcribe(audio_path)
        text = result['text']

        if not text.strip():
            raise ValueError("Transcription resulted in empty text")

        # Clean the transcribed text to remove duplicate phrases
        cleaned_text = remove_duplicate_phrases(text)

        # Highlight moans and profanity
        highlighted_text = highlight_keywords(cleaned_text, moan_keywords + profanity_keywords)

        # Perform sentiment analysis on the cleaned transcribed text
        sentiment = sia.polarity_scores(cleaned_text)

        return highlighted_text, sentiment
    except Exception as e:
        print(f"Error processing the audio file: {e}")
        return None, None

# Load the larger Whisper model once
model = whisper.load_model('large')

# Initialize VADER (Valence Aware Dictionary and sEntiment Reasoner)
sia = SentimentIntensityAnalyzer()

# Path to the audio file
audio_file = r'D:\carlo\Edits\1_1463825_20240501-000937-remastered.wav'

# Ensure the file exists
if not os.path.isfile(audio_file):
    print(f"Audio file does not exist: {audio_file}")
else:
    # Transcribe and analyze the audio file
    transcribed_text, sentiment = transcribe_and_analyze(audio_file, model, sia)

    if transcribed_text and sentiment:
        # Print the transcribed and highlighted text
        print(f'Transcribed Text:\n{transcribed_text}')

        # Print the sentiment analysis results
        print(f'Sentiment Analysis:\n{sentiment}')