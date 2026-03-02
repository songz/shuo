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
- sounddevice (for microphone capture)
- openwakeword (for wake‑word detection)

The `requirements.txt` file already includes these libraries.
## Notes

### whisper.cpp setup

This project relies on a local build of [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
for speech‑to‑text.  The repository itself is **not** included; add it as a
submodule or clone it elsewhere and build the binary.

A typical setup looks like:

```bash
# clone (outside the Tammy project, or in a sibling folder)
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
mkdir build && cd build
cmake .. && make -j
```

The resulting executable (`whisper-cli` or `main` depending on version) is
expected under `whisper.cpp/build/bin/` relative to this project, and models
should be placed in `whisper.cpp/models/` (or pointed to via
`WHISPER_MODEL` environment variable).

The `whisper.cpp/` directory is listed in `.gitignore` so your repo won't
accidentally include the entire source tree or the built files.


- On Raspberry Pi, you may need to install additional system dependencies:
  ```bash
  sudo apt-get install python3-pygame
  ```
- Images should be in PNG format for best results
- The app displays images centered on the screen with black letterboxing/pillarboxing if needed

### Wakeword setup

The project uses [openwakeword](https://pypi.org/project/openwakeword/) for
wake‑word detection.  By default the library loads its pretrained models
internally, but you can place your own ONNX file in the workspace (e.g. `wakeword.onnx`
) and instantiate the listener with that path:

```python
listener = WakewordListener(model_paths="wakeword.onnx")
```

Alternatively call `openwakeword.get_pretrained_model_paths()` or
`openwakeword.utils.download_models()` to fetch the standard models.

After detection the face will switch between `idle`, `capturing`, etc.  The
main loop in `main.py` already polls for wakeword events and updates the
state.
 
When you start the app with debugging enabled (`WakewordListener(debug=True)`),
the console will print per-block RMS values and a small sample of the audio
buffer.  That lets you verify the microphone is working and provides a crude
way to "see" what you're saying.  You can adjust the `threshold` and
`min_rms` parameters on the listener to control when wakeword events fire.

    By default the detector works on a very short window (about 0.08 s).
    If your chosen wake phrase stretches over a couple of seconds you can
    instead specify `window_seconds` when creating the listener, for example::

        listener = WakewordListener(window_seconds=2.0, threshold=0.9)

    That makes the model consume a larger buffer at once; waking will be
    slightly slower but more reliable for multi‑word phrases.
# Convo

I want to eventually build an app where the face is waiting for user to call him, like alexa, and then it streams user's message to an AI model like gemini or openAI, then it should stream back response, and the loadface state should reflect what the state is, whether it's waiting for user to say the wakeup word, or listening to what the user is saying, or waiting for api response (thinking), or speaking out the text (speaking state)

I want to take it step by step, so next step is to start the app at warmup state, and then start listening to the mic. When mic is listening, it should be idle face. When the mic gets triggered with a word "hello tammy" then it should go into the capturing state. I thinking of using openwakeword, for triggering the mic, but please suggest better approach if you have one..