#!/usr/bin/env python3
"""
Full-screen image display app for different states.
Press number keys 1-7 to switch between different face states.
"""

import pygame
import sys
import time
import tempfile
import os
import numpy as np
from scipy.io import wavfile
from load_face import load_face
from wakeword import WakewordListener
from asr_whispercpp import transcribe_file

# Initialize Pygame
pygame.init()

# Get the display info and set up full-screen
info = pygame.display.get_surface()
if info is None:
    # If no surface yet, get the desktop size
    display_info = pygame.display.Info()
    SCREEN_WIDTH = display_info.current_w
    SCREEN_HEIGHT = display_info.current_h
else:
    SCREEN_WIDTH = info.get_width()
    SCREEN_HEIGHT = info.get_height()

# Create full-screen display
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Tammy - Face Display")

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

# Create a blank black surface as default
current_image = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
current_image.fill((0, 0, 0))

# helper to show a face state on screen

def show_state(state_name: str):
    """Load and display a face for the given state."""
    img = load_face(state_name, SCREEN_WIDTH, SCREEN_HEIGHT)
    if img:
        screen.fill((0, 0, 0))
        x = (SCREEN_WIDTH - img.get_width()) // 2
        y = (SCREEN_HEIGHT - img.get_height()) // 2
        screen.blit(img, (x, y))
        pygame.display.flip()
    else:
        print(f"Unable to show state '{state_name}'")

# start in warmup and immediately begin listening
current_state = 'warmup'
show_state(current_state)

# create wakeword listener; by default it loads built-in models
# create wakeword listener with 2-second window to capture longer phrases
listener = WakewordListener()
listener.start()

# once the mic is active, switch to idle
current_state = 'idle'
show_state(current_state)


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
                show_state(state_folder)
                current_state = state_folder
                print(f"Displayed {state_folder}")
            
            # ESC key to exit
            elif event.key == pygame.K_ESCAPE:
                running = False

    # wakeword detection poll
    if listener.got_wakeword():
        print("Wakeword detected!")
        current_state = 'capturing'
        show_state(current_state)
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
            current_state = 'thinking'
            show_state(current_state)

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
        current_state = 'idle'
        show_state(current_state)

    clock.tick(30)  # 30 FPS



pygame.quit()
sys.exit()
