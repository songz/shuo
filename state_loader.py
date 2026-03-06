"""State renderer for loading and displaying face images."""

import os
import random
import time
import pygame


class StateLoader:
    _screen = None
    _current_state = None
    is_speaking = False
    _state_images = []
    _image_index = 0
    _last_advance_time = 0.0
    _frame_interval_seconds = random.uniform(0.0, 1.0)

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
    def _get_state_image_paths(state_folder):
        """Return sorted PNG image paths for a state folder."""
        faces_dir = os.path.join(os.path.dirname(__file__), 'faces')
        folder_path = os.path.join(faces_dir, state_folder)

        if not os.path.exists(folder_path):
            print(f"Error: Folder '{state_folder}' not found at {folder_path}")
            return []

        png_files = sorted(f for f in os.listdir(folder_path) if f.lower().endswith('.png'))
        if not png_files:
            print(f"Error: No PNG images found in {folder_path}")
            return []

        return [os.path.join(folder_path, file_name) for file_name in png_files]

    @staticmethod
    def _load_scaled_image(image_path, screen_width, screen_height):
        """
        Load and scale an image to fill the screen while preserving aspect ratio.

        Args:
            image_path (str): Full path to image
            screen_width (int): Width of the screen for scaling
            screen_height (int): Height of the screen for scaling

        Returns:
            pygame.Surface: The scaled image ready to display, or None if loading fails
        """
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

            return image

        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            return None

    @classmethod
    def _render_current_image(cls):
        screen = cls._ensure_screen()
        screen_width, screen_height = screen.get_size()

        if not cls._state_images:
            print(f"Unable to show state '{cls._current_state}'")
            return False

        image_path = cls._state_images[cls._image_index]
        img = cls._load_scaled_image(image_path, screen_width, screen_height)
        if not img:
            print(f"Unable to show state '{cls._current_state}'")
            return False

        screen.fill((0, 0, 0))
        x = (screen_width - img.get_width()) // 2
        y = (screen_height - img.get_height()) // 2
        screen.blit(img, (x, y))
        pygame.display.flip()
        cls._frame_interval_seconds = random.uniform(0.3, 1.0)
        return True

    @classmethod
    def get_current_state(cls):
        return cls._current_state

    @classmethod
    def load_state(cls, state_name):
        """Load and display a face for the given state name."""
        if state_name == 'thinking' and cls.is_speaking:
            state_name = 'speaking'

        if state_name == 'listening':
            cls.is_speaking = False
        elif state_name == 'speaking':
            cls.is_speaking = True

        now = time.monotonic()

        if state_name != cls._current_state:
            cls._current_state = state_name
            cls._state_images = cls._get_state_image_paths(state_name)
            cls._image_index = 0
            cls._last_advance_time = now
            return cls._render_current_image()

        if len(cls._state_images) <= 1:
            return True

        if now - cls._last_advance_time >= cls._frame_interval_seconds:
            cls._image_index = (cls._image_index + 1) % len(cls._state_images)
            cls._last_advance_time = now
            return cls._render_current_image()

        return True
