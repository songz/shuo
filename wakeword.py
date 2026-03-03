"""
Wakeword detection helper using openwakeword and sounddevice.
"""

import threading
import queue
import os
import time
import tempfile
import sounddevice as sd
import numpy as np
from scipy.io import wavfile
import openwakeword
import scipy.signal 

# Configuration
CHUNK_SIZE = 1280*2
SAMPLE_RATE = 16000  # Hz
#WAKEWORD_MODEL = os.path.join(os.path.dirname(__file__), "hey_rhasspy_v0.1.onnx")
WAKEWORD_MODEL = os.path.join(os.path.dirname(__file__), "wakeword.onnx")


class WakewordListener:
    """Listen to the microphone and emit an event when the wake word is heard.

    A minimal wrapper around ``openwakeword.Model`` that runs the wakeword
    model in a background thread.  ``event_queue`` is populated with ``True``
    each time the detector returns a score above the optional ``threshold``.

    The constructor accepts a list of ONNX model paths; if none are provided the
    built-in pretrained models are loaded (via
    ``openwakeword.get_pretrained_model_paths()``).  You may drop a custom
    ``wakeword.onnx`` file in your project and pass its path here.

    If ``debug`` is set to ``True`` the raw audio RMS value for each block is
    printed so you can verify the microphone is capturing sound.
    """

    def __init__(self, samplerate=None,
                 threshold: float = 0.5, debug: bool = False,
                 window_seconds: float = 0.08):
        """Create a listener.

        ``window_seconds`` controls how much audio (in seconds) is fed to the
        model at once.  A 0.08‑second window is the default because it lets the
        detector respond very quickly.  If your wake phrase is longer than
        the window you should increase this value accordingly (e.g. 1–2
        seconds).  ``window_seconds`` now *is* the only way to influence the
        internal buffer size; the old ``blocksize`` parameter has been
        removed.

        Note that using a fixed, non‑overlapping window means audio that
        straddles the boundary between two chunks could be split and never
        be seen in its entirety.  For simple setups the easiest fix is to
        make ``window_seconds`` at least as long as the longest expected
        phrase.  If you need both long phrases and fast reactions you can
        later add overlapping windows (the callback could keep the last N
        seconds and run ``predict`` on it every 80 ms, for example).
        """
        # locate wakeword.onnx in the project root
        self.model = openwakeword.Model(wakeword_model_paths=[WAKEWORD_MODEL])
        print(f"Loaded wake word model: {WAKEWORD_MODEL}")

        device_info = sd.query_devices(kind='input')
        native_rate = int(device_info['default_samplerate'])
        self.use_resampling = (native_rate != SAMPLE_RATE)
        
        self.input_rate = native_rate if self.use_resampling else SAMPLE_RATE
        self.sample_rate = self.input_rate
        self.input_chunk_size = int(CHUNK_SIZE * (self.input_rate / SAMPLE_RATE)) if self.use_resampling else CHUNK_SIZE

        self.stream = None
        self.event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.threshold = threshold

    def start(self):
        """Begin listening in a separate thread."""
        self._stop_event.clear()
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def stop(self):
        """Stop listening and close the audio stream."""
        self._stop_event.set()
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()

    def _run(self):
        """Internal thread responsible for opening the audio stream and
        running the wakeword model on 80 ms chunks.
        """

        def audio_callback(indata, frames, time_info, status):
            if self._stop_event.is_set():
                raise sd.CallbackStop
            # Convert audio to mono float32
            audio_data = indata[:, 0].astype(np.int16)
            if self.use_resampling:
                audio_data = scipy.signal.resample(audio_data, CHUNK_SIZE).astype(np.int16)
            # Pass audio to detector
            scores = self.model.predict(audio_data)
            if scores:
                max_score = max(scores.values())
                # require both model score and a minimum energy
                if max_score >= self.threshold:
                    self.event_queue.put(True)
        try:
            self.stream = sd.InputStream(
                samplerate=self.input_rate,
                blocksize=self.input_chunk_size,
                channels=1,
                dtype="int16",
                callback=audio_callback
            )
            self.stream.start()
            # keep thread alive until stopped
            while not self._stop_event.is_set():
                sd.sleep(100)
        except Exception as e:
            print(f"Wakeword listener error: {e}")
            self._stop_event.set()

    def got_wakeword(self):
        """
        Check if a wakeword detection event is available without blocking.
        
        Attempts to retrieve and remove a wakeword event from the internal event queue
        in a non-blocking manner. If an event is available, it is returned immediately.
        If the queue is empty, returns False without waiting.
        
        Returns:
            bool or object: The wakeword event if one is pending in the queue, 
                           False if the queue is empty.
        
        Note:
            This method is non-blocking, meaning it will not pause execution waiting
            for an event to arrive. Use this for polling-based event detection.
        """
        """Return True if a wakeword event is waiting (non-blocking)."""
        try:
            return self.event_queue.get_nowait()
        except queue.Empty:
            return False
