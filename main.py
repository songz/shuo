#!/usr/bin/env python3
"""
Full-screen image display app for different states.
Press number keys 1-7 to switch between different face states.
"""

import pygame
import sys
import tempfile
import os
import numpy as np
from scipy.io import wavfile
from state_loader import StateLoader
from wakeword import WakewordListener
from asr_whispercpp import transcribe_file

# Initialize Pygame
pygame.init()

# Define the state folders and their key mappings
STATES = {
    pygame.K_1: 'capturing',
    pygame.K_2: 'error',
    pygame.K_3: 'idle',
    pygame.K_4: 'listening',
    pygame.K_5: 'speaking',
    pygame.K_6: 'thinking',
    pygame.K_7: 'warmup',
}

# start in warmup and immediately begin listening
StateLoader.load_state('warmup')

# create wakeword listener; by default it loads built-in models
# create wakeword listener with 2-second window to capture longer phrases
listener = WakewordListener()
listener.start()

# once the mic is active, switch to idle
StateLoader.load_state('idle')


# Main loop
clock = pygame.time.Clock()
running = True

print("Full-screen image display app started")
print("Press number keys 1-7 to switch between states:")
print("  1 = Capturing")
print("  2 = Error")
print("  3 = Idle")
print("  4 = Listening")
print("  5 = Speaking")
print("  6 = Thinking")
print("  7 = Warmup")
print("Touch screen toggles Idle <-> Listening")
print("Press ESC or close window to exit")

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            # Check if it's a number key (1-7)
            if event.key in STATES:
                state_folder = STATES[event.key]
                print(f"Loading {state_folder}...")
                StateLoader.load_state(state_folder)
                print(f"Displayed {state_folder}")
            
            # ESC key to exit
            elif event.key == pygame.K_ESCAPE:
                running = False
        elif event.type == pygame.FINGERDOWN or (
            event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        ):
            current_state = StateLoader.get_current_state()
            if current_state == 'idle':
                StateLoader.load_state('listening')
                print("Touch toggle -> listening")
            elif current_state == 'listening':
                StateLoader.load_state('idle')
                print("Touch toggle -> idle")

    # wakeword detection poll
    if listener.got_wakeword():
        print("Wakeword detected!")
        StateLoader.load_state('capturing')
        # Stop wakeword listener so we can record from the mic
        listener.stop()

        # record additional audio (user speech) for a short duration
        RECORD_SECONDS = 4.0
        sr = listener.sample_rate
        print(f"Recording {RECORD_SECONDS}s at {sr}Hz for ASR...")
        try:
            import sounddevice as sd
            recording = sd.rec(int(RECORD_SECONDS * sr), samplerate=sr, channels=1, dtype='float32')
            sd.wait()
            # save to temporary WAV
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tf:
                wav_path = tf.name
            # convert float32 to int16
            wav_int16 = (recording.flatten() * 32767).astype(np.int16)
            wavfile.write(wav_path, sr, wav_int16)

            # show thinking face while transcribing
            StateLoader.load_state('thinking')

            try:
                transcript = transcribe_file(wav_path)
                print('ASR transcript:')
                print(transcript)
            except Exception as e:
                print(f"ASR error: {e}")
            finally:
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

        except Exception as e:
            print(f"Recording error: {e}")

        # restart listener and go back to idle
        listener.start()
        StateLoader.load_state('idle')

    # keep current state animated
    current_state = StateLoader.get_current_state()
    if current_state is not None:
        StateLoader.load_state(current_state)

    clock.tick(30)  # 30 FPS



pygame.quit()
sys.exit()
