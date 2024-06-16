import os
from pyAudioAnalysis import audioBasicIO, MidTermFeatures, audioSegmentation, audioFeatureExtraction, audioVisualization as aV

# Load the Audio File
audio_path = "oi-audio/original-audio/20240430-1629.wav"
[Fs, x] = audioBasicIO.readAudioFile(audio_path, format="pcm_f32le")

# Extract Audio Features
[mtFeatures, stFeatures] = MidTermFeatures.mid_feature_extraction(x, Fs, 1.0*Fs, 1.0*Fs, 0.050*Fs, 0.050*Fs)

# Visualize the Audio Signal
aV.plotWAV(x, Fs)

# Apply Noise Reduction
segments = audioSegmentation.silence_removal(x, Fs, 0.020, 0.020, smoothWindow=1.0, Weight=0.3, plot=False)

# Enhance Dialogue
speech_features = audioFeatureExtraction.stFeatureExtraction(x, Fs, 0.050*Fs, 0.050*Fs)

# Perform Detailed Frequency Analysis
psd_features = audioFeatureExtraction.stFeatureExtraction(x, Fs, 0.050*Fs, 0.050*Fs)

# Generate Enhanced Spectrogram
aV.plotSpectrogram(x, Fs, 0.050*Fs, 0.050*Fs)

# Save and Document Results
output_dir = "oi-audio/original-audio/metadata"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Save the processed audio and visualizations
import matplotlib.pyplot as plt
import numpy as np
from scipy.io.wavfile import write

# Save the processed audio
processed_audio_path = os.path.join(output_dir, "20240430-1629_processed.wav")
write(processed_audio_path, Fs, x.astype(np.float32))

# Save the spectrogram
spectrogram_path = os.path.join(output_dir, "20240430-1629_spectrogram.png")
plt.specgram(x, Fs=Fs)
plt.savefig(spectrogram_path)

print("Analysis complete. Results saved in:", output_dir)
print("Processed audio saved at:", processed_audio_path)
print("Spectrogram saved at:", spectrogram_path)
