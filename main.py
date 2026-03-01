#!/usr/bin/env python3
"""
Full-screen image display app for different states.
Press number keys 1-7 to switch between different face states.
"""

import pygame
import sys
from load_face import load_face

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

# Load the first state (capturing) by default
first_state = load_face('capturing', SCREEN_WIDTH, SCREEN_HEIGHT)
if first_state:
    # Center the image on the screen
    x = (SCREEN_WIDTH - first_state.get_width()) // 2
    y = (SCREEN_HEIGHT - first_state.get_height()) // 2
    screen.blit(first_state, (x, y))
else:
    # Draw a message if image not found
    font = pygame.font.Font(None, 48)
    text = font.render("Press 1-7 to display faces", True, (255, 255, 255))
    screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 
                      SCREEN_HEIGHT // 2 - text.get_height() // 2))

pygame.display.flip()

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
                
                image = load_face(state_folder, SCREEN_WIDTH, SCREEN_HEIGHT)
                if image:
                    # Clear screen with black
                    screen.fill((0, 0, 0))
                    
                    # Center the image on the screen
                    x = (SCREEN_WIDTH - image.get_width()) // 2
                    y = (SCREEN_HEIGHT - image.get_height()) // 2
                    screen.blit(image, (x, y))
                    
                    pygame.display.flip()
                    print(f"Displayed {state_folder}")
                else:
                    print(f"Failed to load {state_folder}")
            
            # ESC key to exit
            elif event.key == pygame.K_ESCAPE:
                running = False
    
    clock.tick(30)  # 30 FPS

pygame.quit()
sys.exit()
