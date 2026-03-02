"""
Wakeword detection helper using openwakeword and sounddevice.
"""

import threading
import queue
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

    def __init__(self, model_paths=None, samplerate=None, blocksize=None,
                 threshold: float = 0.5, debug: bool = False,
                 window_seconds: float | None = None):
        """Create a listener.

        "window_seconds" controls how much audio (in seconds) is fed to the
        model at once.  It defaults to 0.08 (80 ms) for a quick response, but
        you may set it to ~2.0 for a longer wake phrase.  If both
        ``blocksize`` and ``window_seconds`` are provided, ``window_seconds``
        takes precedence.
        """
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

        # compute blocksize from window_seconds when given; otherwise keep
        # existing behaviour.
        if window_seconds is not None:
            self.blocksize = int(window_seconds * self.samplerate)
        elif blocksize is None:
            # blocksize defaults to 80ms of audio (used by openwakeword)
            self.blocksize = int(0.08 * self.samplerate)
        else:
            self.blocksize = blocksize

        self.event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.threshold = threshold
        self.debug = debug
        # RMS floor to help prevent triggering on near-silent noise
        self.min_rms = 0.02

        # prepare model list
        if model_paths is None:
            model_paths = openwakeword.get_pretrained_model_paths()
        elif isinstance(model_paths, str):
            model_paths = [model_paths]

        # debug info about chosen sample rate and blocksize
        if self.debug:
            print(f"[wakeword debug] samplerate={self.samplerate}, blocksize={self.blocksize}")

        # instantiate openwakeword model with provided paths
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
                    # require both model score and a minimum energy
                    if max_score >= self.threshold and rms >= self.min_rms:
                        if self.debug:
                            print(f"[wakeword debug] detection score={max_score}")
                        self.event_queue.put(True)

        try:
            self.stream = sd.InputStream(channels=1,
                                         samplerate=self.samplerate,
                                         blocksize=self.blocksize,
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
