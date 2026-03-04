"""State renderer for loading and displaying face images."""

import os
import random
import pygame


class StateLoader:
    _screen = None

    @classmethod
    def _ensure_screen(cls):
        if cls._screen is not None:
            return cls._screen

        surface = pygame.display.get_surface()
        if surface is None:
            cls._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.display.set_caption("Tammy - Face Display")
        else:
            cls._screen = surface

        return cls._screen

    @staticmethod
    def _load_state_image(state_folder, screen_width, screen_height):
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

        png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]

        if not png_files:
            print(f"Error: No PNG images found in {folder_path}")
            return None

        random_image = random.choice(png_files)
        image_path = os.path.join(folder_path, random_image)

        try:
            image = pygame.image.load(image_path)
            image.convert()

            image_width, image_height = image.get_size()
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

    @classmethod
    def load_state(cls, state_name):
        """Load and display a face for the given state name."""
        screen = cls._ensure_screen()
        screen_width, screen_height = screen.get_size()
        img = cls._load_state_image(state_name, screen_width, screen_height)
        if not img:
            print(f"Unable to show state '{state_name}'")
            return False

        screen.fill((0, 0, 0))
        x = (screen_width - img.get_width()) // 2
        y = (screen_height - img.get_height()) // 2
        screen.blit(img, (x, y))
        pygame.display.flip()
        return True
