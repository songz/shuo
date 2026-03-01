"""
Face loader module for randomly selecting and loading face images.
"""

import os
import random
import pygame


def load_face(state_folder, screen_width=1920, screen_height=1080):
    """
    Load a random image from the specified face state folder.
    
    Args:
        state_folder (str): The name of the folder (e.g., 'capturing', 'error', 'idle')
        screen_width (int): Width of the screen for scaling
        screen_height (int): Height of the screen for scaling
    
    Returns:
        pygame.Surface: The scaled image ready to display, or None if loading fails
    """
    faces_dir = os.path.join(os.path.dirname(__file__), 'faces')
    folder_path = os.path.join(faces_dir, state_folder)
    
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{state_folder}' not found at {folder_path}")
        return None
    
    # Find all PNG files in the folder
    png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]
    
    if not png_files:
        print(f"Error: No PNG images found in {folder_path}")
        return None
    
    # Pick a random image
    random_image = random.choice(png_files)
    image_path = os.path.join(folder_path, random_image)
    
    try:
        image = pygame.image.load(image_path)
        image.convert()
        
        # Calculate scaling to fill the screen while maintaining aspect ratio
        image_width, image_height = image.get_size()
        
        # Scale to fill the screen
        width_ratio = screen_width / image_width
        height_ratio = screen_height / image_height
        scale_factor = max(width_ratio, height_ratio)
        
        new_width = int(image_width * scale_factor)
        new_height = int(image_height * scale_factor)
        image = pygame.transform.scale(image, (new_width, new_height))
        
        print(f"Loaded: {state_folder}/{random_image}")
        return image
    
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return None
