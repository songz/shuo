"""
Helper to call a local `whisper.cpp` binary to transcribe WAV files.

Expectations:
- A built binary at `./whisper.cpp/main` (or you can set `WHISPER_BIN` env)
- A GGML model at `./models/ggml-small.en.bin` (or set `WHISPER_MODEL` env)

The function `transcribe_file` runs the binary and returns the captured stdout
as a string.
"""

import os
import shlex
import subprocess

# prefer the newer whisper-cli binary in common build locations
DEFAULT_BIN = os.environ.get("WHISPER_BIN", "./whisper.cpp/build/bin/whisper-cli")
# prefer ggml-base model from whisper.cpp/models by default when available
DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "./whisper.cpp/models/ggml-base.en.bin")

# common alternate locations (project-relative)
ALT_BINS = [
    os.path.join("whisper.cpp", "build", "bin", "whisper-cli"),
    os.path.join("whisper.cpp", "build", "bin", "main"),
    os.path.join("whisper.cpp", "build", "main"),
    os.path.join("whisper.cpp", "main"),
]

ALT_MODELS = [
    os.path.join("whisper.cpp", "models", "ggml-base.en.bin"),
    os.path.join("whisper.cpp", "models", "ggml-small.en.bin"),
    os.path.join("whisper.cpp", "ggml", "ggml-small.en.bin"),
    os.path.join("models", "ggml-base.en.bin"),
    os.path.join("models", "ggml-small.en.bin"),
]


def transcribe_file(wav_path: str, model_path: str | None = None, extra_args: list | None = None) -> str:
    """Transcribe `wav_path` using whisper.cpp binary and return transcript text.

    If `model_path` is None the default `DEFAULT_MODEL` is used. `extra_args`
    allows passing additional command-line flags to `main`.
    """
    if model_path is None:
        model_path = DEFAULT_MODEL

    # choose binary
    # locate binary: env override -> default -> alt locations
    bin_path = os.environ.get("WHISPER_BIN", DEFAULT_BIN)
    if not os.path.exists(bin_path):
        # try common alternate paths relative to project
        for p in ALT_BINS:
            candidate = os.path.join(os.path.dirname(__file__), p)
            if os.path.exists(candidate):
                bin_path = candidate
                break

    if not os.path.exists(bin_path):
        raise FileNotFoundError(
            f"whisper.cpp binary not found at {bin_path}. Build whisper.cpp and place binary there or set WHISPER_BIN."
        )

    # locate model: provided path -> default -> alternate locations
    if not os.path.exists(model_path):
        for p in ALT_MODELS:
            candidate = os.path.join(os.path.dirname(__file__), p)
            if os.path.exists(candidate):
                model_path = candidate
                break

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"GGML model not found at {model_path}. Place a model there or set WHISPER_MODEL."
        )

    cmd = [bin_path, "-m", model_path, "-f", wav_path]
    if extra_args:
        cmd += extra_args

    # run and capture stdout
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # if the process failed, include both stdout and stderr for debugging
    if proc.returncode != 0:
        raise RuntimeError(
            f"whisper.cpp failed (rc={proc.returncode}). stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )

    return proc.stdout
