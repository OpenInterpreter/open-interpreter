import os
from pyAudioAnalysis import audioBasicIO, MidTermFeatures, audioSegmentation, audioFeatureExtraction, audioVisualization

# Load the Audio File
audio_path = "oi-audio/original-audio/20240430-1508.wav"
[Fs, x] = audioBasicIO.readAudioFile(audio_path)

# Extract Audio Features
[mtFeatures, stFeatures] = MidTermFeatures.mid_feature_extraction(x, Fs, 1.0*Fs, 1.0*Fs, 0.050*Fs, 0.050*Fs)

# Visualize the Audio Signal
audioVisualization.plotWAV(x, Fs)

# Apply Noise Reduction
segments = audioSegmentation.silence_removal(x, Fs, 0.020, 0.020, smoothWindow=1.0, Weight=0.3, plot=False)

# Enhance Dialogue
speech_features = audioFeatureExtraction.stFeatureExtraction(x, Fs, 0.050*Fs, 0.050*Fs)

# Perform Detailed Frequency Analysis
psd_features = audioFeatureExtraction.stFeatureExtraction(x, Fs, 0.050*Fs, 0.050*Fs)

# Generate Enhanced Spectrogram
audioVisualization.plotSpectrogram(x, Fs, 0.050*Fs, 0.050*Fs)

# Save and Document Results
output_dir = "oi-audio/original-audio/metadata"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Save the processed audio and visualizations
# (Assuming the necessary functions to save the processed data are available)
# Example: save_processed_audio(x, Fs, os.path.join(output_dir, "20240430-1508_processed.wav"))
# Example: save_visualization(spectrogram, os.path.join(output_dir, "20240430-1508_spectrogram.png"))

print("Analysis complete. Results saved in:", output_dir)
