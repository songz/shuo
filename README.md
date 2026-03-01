# Tammy Face Display App

A full-screen image display application that cycles through different emotional states.

## Features

- Full-screen display of face images
- Quick switching between 7 different emotional states using number keys
- Images automatically scale to fill the screen while maintaining aspect ratio
- Easy-to-use keyboard controls

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python3 main.py
```

### Controls

Press number keys to switch between states:

- **1** = Capturing 😊
- **2** = Error 😕
- **3** = Idle 😐
- **4** = Listening 👂
- **5** = Speaking 🗣️
- **6** = Thinking 🤔
- **7** = Warmup 🌡️
- **ESC** = Exit the application

## Project Structure

```
Tammy/
├── main.py                 # Main application file
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── faces/                 # Image assets
    ├── capturing/         # Capturing state images
    ├── error/             # Error state images
    ├── idle/              # Idle state images
    ├── listening/         # Listening state images
    ├── speaking/          # Speaking state images
    ├── thinking/          # Thinking state images
    └── warmup/            # Warmup state images
```

## Requirements

- Python 3.7+
- Pygame 2.5.2+

## Notes

- On Raspberry Pi, you may need to install additional system dependencies:
  ```bash
  sudo apt-get install python3-pygame
  ```
- Images should be in PNG format for best results
- The app displays images centered on the screen with black letterboxing/pillarboxing if needed
