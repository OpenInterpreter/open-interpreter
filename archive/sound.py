import pygame.mixer

# Initialize pygame mixer with smaller buffer for keyboard-like sounds
pygame.mixer.init(44100, -16, 1, 512)


def generate_typing_sound(duration, base_freq, volume):
    sample_rate = 44100
    num_samples = int(duration * sample_rate / 1000)

    # Generate a more complex waveform that sounds like a soft key press
    buffer = bytearray()
    for i in range(num_samples):
        # Create attack-decay envelope
        progress = i / num_samples
        if progress < 0.1:  # Quick attack
            envelope = progress * 10
        else:  # Longer decay
            envelope = (1 - progress) ** 0.5

        # Combine multiple frequencies for richer sound
        value = int(
            2048
            * envelope
            * volume
            * (
                0.7 * math.sin(2 * math.pi * base_freq * i / sample_rate)
                + 0.2  # Base frequency
                * math.sin(2 * math.pi * (base_freq * 1.5) * i / sample_rate)
                + 0.1  # Overtone
                * math.sin(
                    2 * math.pi * (base_freq * 2) * i / sample_rate
                )  # Higher overtone
            )
        )

        buffer.extend(value.to_bytes(2, byteorder="little", signed=True))

    return pygame.mixer.Sound(buffer=bytes(buffer))


import math
import random

# Pre-generate a few variations of typing sounds
typing_sounds = []
for _ in range(30):
    duration = random.randint(30, 50)  # Shorter duration for crisp typing sound
    base_freq = random.randint(100, 8000)  # Higher frequencies for key-like sound
    volume = random.uniform(0.3, 0.4)  # Lower volume for softer sound
    sound = generate_typing_sound(duration, base_freq, volume)
    typing_sounds.append(sound)

# Play random variations of the typing sounds
for i in range(100):
    sound = random.choice(typing_sounds)
    sound.play()
    time.sleep(random.uniform(0.01, 0.03))  # More natural typing rhythm
