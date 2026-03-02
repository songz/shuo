"""
Wakeword detection helper using openwakeword and sounddevice.
"""

import threading
import queue
import os
import sounddevice as sd
import numpy as np
import openwakeword


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
        model_path = os.path.join(os.path.dirname(__file__), "wakeword.onnx")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Custom wakeword model not found at {model_path}. "
                "Please place your trained wakeword.onnx in the project root."
            )
        
        # determine samplerate from sounddevice default if not provided
        if samplerate is None:
            # check sd.default first
            if sd.default.samplerate is not None:
                samplerate = int(sd.default.samplerate)
            else:
                # fallback to querying default input device
                try:
                    dev = sd.query_devices(None, 'input')
                    samplerate = int(dev['default_samplerate'])
                except Exception:
                    samplerate = 16000
        self.samplerate = int(samplerate)

        # window_seconds now directly defines how many samples we buffer
        self.blocksize = int(window_seconds * self.samplerate)

        self.event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.threshold = threshold
        self.debug = debug
        # RMS floor to help prevent triggering on near-silent noise
        self.min_rms = 0.02

        # prepare model list with custom wakeword
        model_paths = [model_path]

        # debug info about chosen sample rate and window size
        if self.debug:
            print(f"[wakeword debug] samplerate={self.samplerate}, window_samples={self.blocksize}")

        # instantiate openwakeword model with custom wakeword.onnx
        self.model = openwakeword.Model(wakeword_model_paths=model_paths)

        # buffer for accumulating samples (monophonic float32)
        self.audio_buffer = np.zeros(0, dtype=np.float32)

        # stream object placeholder
        self.stream = None

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

        def audio_callback(indata, frames, time, status):
            if self._stop_event.is_set():
                raise sd.CallbackStop
            # convert to mono float32 and append to buffer
            mono = np.mean(indata, axis=1).astype(np.float32)
            self.audio_buffer = np.concatenate((self.audio_buffer, mono))

            # run prediction when we have at least one block
            while len(self.audio_buffer) >= self.blocksize:
                chunk = self.audio_buffer[: self.blocksize]
                self.audio_buffer = self.audio_buffer[self.blocksize :]

                # compute RMS regardless of debug setting
                rms = np.sqrt(np.mean(chunk ** 2))
                if self.debug:
                    snippet = ",".join(f"{x:.3f}" for x in chunk[:5])
                    print(f"[wakeword debug] block RMS={rms:.6f}, first5=[{snippet}]... (len={len(chunk)})")

                scores = self.model.predict(chunk)
                # scores is a dict of {model_name: score}
                if scores:
                    max_score = max(scores.values())
                    max_model = max(scores, key=scores.get)
                    # require both model score and a minimum energy
                    if max_score >= self.threshold and rms >= self.min_rms:
                        if self.debug:
                            print(f"[wakeword debug] detection: model={max_model}, score={max_score:.7f}")
                        self.event_queue.put(True)

        try:
            # we request no particular blocksize from sounddevice; our own
            # buffering logic uses ``self.blocksize`` samples per window.
            self.stream = sd.InputStream(channels=1,
                                         samplerate=self.samplerate,
                                         callback=audio_callback)
            self.stream.start()
            # keep thread alive until stopped
            while not self._stop_event.is_set():
                sd.sleep(100)
        except Exception as e:
            print(f"Wakeword listener error: {e}")
            self._stop_event.set()

    def got_wakeword(self):
        """Return True if a wakeword event is waiting (non-blocking)."""
        try:
            return self.event_queue.get_nowait()
        except queue.Empty:
            return False
