"""
Local audio transport (microphone + speaker) for non-Twilio mode.

Captures microphone PCM at 8kHz mono, encodes to μ-law for Flux,
and plays ElevenLabs μ-law audio on local speakers.
"""

import asyncio
import base64
import threading
from typing import Awaitable, Callable, Optional

import numpy as np
from scipy.signal import resample
import sounddevice as sd

from ..log import ServiceLogger

log = ServiceLogger("LocalAudio")

_ULAW_BIAS = 0x84
_ULAW_CLIP = 32635


def _linear16_to_ulaw(sample: int) -> int:
    """Convert one 16-bit PCM sample to 8-bit μ-law."""
    sign = 0
    value = int(sample)
    if value < 0:
        sign = 0x80
        value = -value

    if value > _ULAW_CLIP:
        value = _ULAW_CLIP

    value += _ULAW_BIAS

    exponent = 7
    exp_mask = 0x4000
    while exponent > 0 and (value & exp_mask) == 0:
        exponent -= 1
        exp_mask >>= 1

    mantissa = (value >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF


def pcm16_bytes_to_ulaw(pcm16_bytes: bytes) -> bytes:
    """Convert little-endian int16 PCM bytes to μ-law bytes."""
    pcm = np.frombuffer(pcm16_bytes, dtype=np.int16)
    encoded = bytearray(len(pcm))
    for index, sample in enumerate(pcm):
        encoded[index] = _linear16_to_ulaw(int(sample))
    return bytes(encoded)


def _ulaw_to_linear16(ulaw_byte: int) -> int:
    """Convert one 8-bit μ-law byte to 16-bit PCM sample."""
    value = (~ulaw_byte) & 0xFF
    sign = value & 0x80
    exponent = (value >> 4) & 0x07
    mantissa = value & 0x0F

    sample = ((mantissa << 3) + _ULAW_BIAS) << exponent
    sample -= _ULAW_BIAS
    if sign:
        sample = -sample
    return sample


_ULAW_DECODE_TABLE = np.array([_ulaw_to_linear16(i) for i in range(256)], dtype=np.int16)


def ulaw_bytes_to_pcm16(ulaw_bytes: bytes) -> bytes:
    """Convert μ-law bytes to little-endian int16 PCM bytes."""
    ulaw = np.frombuffer(ulaw_bytes, dtype=np.uint8)
    pcm = _ULAW_DECODE_TABLE[ulaw]
    return pcm.tobytes()


class LocalAudioIO:
    """Microphone input + speaker output for local conversation mode."""

    def __init__(
        self,
        on_mic_audio: Callable[[bytes], Awaitable[None]],
        sample_rate: int = 8000,
        frame_ms: int = 20,
    ):
        self._on_mic_audio = on_mic_audio
        self._sample_rate = sample_rate
        self._frame_samples = int(sample_rate * frame_ms / 1000)
        self._input_sample_rate = sample_rate

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.OutputStream] = None
        self._output_enabled = True
        self._running = False

        self._playback_buffer = bytearray()
        self._buffer_lock = threading.Lock()

    async def start(self) -> None:
        """Start microphone capture and speaker playback."""
        if self._running:
            return

        self._loop = asyncio.get_running_loop()

        try:
            input_info = sd.query_devices(kind="input")
            default_rate = int(input_info.get("default_samplerate", self._sample_rate))
            if default_rate > 0:
                self._input_sample_rate = default_rate
        except Exception:
            self._input_sample_rate = self._sample_rate

        input_frame_samples = int(self._input_sample_rate * 20 / 1000)

        output_device_index = None
        default_input, default_output = sd.default.device
        if isinstance(default_output, int) and default_output >= 0:
            output_device_index = default_output
        else:
            devices = sd.query_devices()
            for index, device in enumerate(devices):
                if int(device.get("max_output_channels", 0)) > 0:
                    output_device_index = index
                    break

        if output_device_index is None:
            self._output_enabled = False
            log.info("No output audio device available; running in input-only mode")
        else:
            self._output_enabled = True

        self._input_stream = sd.InputStream(
            samplerate=self._input_sample_rate,
            channels=1,
            dtype="int16",
            blocksize=input_frame_samples,
            callback=self._on_input,
        )
        if self._output_enabled and output_device_index is not None:
            self._output_stream = sd.OutputStream(
                device=output_device_index,
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self._frame_samples,
                callback=self._on_output,
            )
        else:
            self._output_stream = None

        self._input_stream.start()
        if self._output_stream:
            self._output_stream.start()
        self._running = True
        log.connected()

    async def stop(self) -> None:
        """Stop and close audio streams."""
        self._running = False

        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()
            self._input_stream = None

        if self._output_stream:
            self._output_stream.stop()
            self._output_stream.close()
            self._output_stream = None

        self.clear_playback()
        log.disconnected()

    async def play_ulaw_base64(self, audio_base64: str) -> None:
        """Queue ElevenLabs μ-law base64 chunk for local speaker playback."""
        if not audio_base64 or not self._output_enabled:
            return

        ulaw_bytes = base64.b64decode(audio_base64)
        pcm_bytes = ulaw_bytes_to_pcm16(ulaw_bytes)

        with self._buffer_lock:
            self._playback_buffer.extend(pcm_bytes)

    def clear_playback(self) -> None:
        """Clear pending speaker audio immediately."""
        with self._buffer_lock:
            self._playback_buffer.clear()

    def pending_audio_bytes(self) -> int:
        """Return number of PCM bytes still queued for local speaker output."""
        with self._buffer_lock:
            return len(self._playback_buffer)

    def _on_input(self, indata, frames, time_info, status) -> None:
        """sounddevice callback: encode mic PCM to μ-law and forward to Flux."""
        if status:
            log.info(f"Mic status: {status}")

        if not self._running or not self._loop:
            return

        pcm = indata[:, 0].astype(np.int16, copy=False)
        if self._input_sample_rate != self._sample_rate:
            out_len = max(1, int(len(pcm) * self._sample_rate / self._input_sample_rate))
            pcm = np.clip(np.round(resample(pcm.astype(np.float32), out_len)), -32768, 32767).astype(np.int16)

        pcm_bytes = pcm.tobytes()
        ulaw_bytes = pcm16_bytes_to_ulaw(pcm_bytes)
        asyncio.run_coroutine_threadsafe(self._on_mic_audio(ulaw_bytes), self._loop)

    def _on_output(self, outdata, frames, time_info, status) -> None:
        """sounddevice callback: stream queued PCM to local speakers."""
        if status:
            log.info(f"Speaker status: {status}")

        needed = frames * 2  # int16 mono
        with self._buffer_lock:
            if len(self._playback_buffer) >= needed:
                chunk = bytes(self._playback_buffer[:needed])
                del self._playback_buffer[:needed]
            else:
                chunk = bytes(self._playback_buffer)
                self._playback_buffer.clear()

        if len(chunk) < needed:
            chunk += b"\x00" * (needed - len(chunk))

        outdata[:] = np.frombuffer(chunk, dtype=np.int16).reshape(-1, 1)
