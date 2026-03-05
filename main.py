#!/usr/bin/env python3
"""
Full-screen image display app for different states.
Press number keys 1-7 to switch between different face states.
"""

import sys
import tempfile
import os
import numpy as np
from scipy.io import wavfile
from wakeword import WakewordListener
from asr_whispercpp import transcribe_file
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import asyncio


from shuo.conversation import run_conversation_local
from shuo.log import setup_logging, Logger, get_logger


setup_logging()



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
 
asyncio.run(run_conversation_local())

