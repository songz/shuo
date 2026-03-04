"""
Audio player for streaming audio to Twilio.

Manages its own independent playback loop that drips audio
chunks at the correct rate, regardless of other activity.
"""

import json
import asyncio
import time
from typing import List, Optional, Callable

from fastapi import WebSocket

from .local_audio import LocalAudioIO

from ..log import ServiceLogger

log = ServiceLogger("Player")

LOCAL_TAIL_TIMEOUT_S = 1.0


class AudioPlayer:
    """
    Streams audio to Twilio at the correct rate.
    
    Features:
    - Independent playback loop (not affected by incoming messages)
    - Can be topped up with audio chunks dynamically (for streaming TTS)
    - Instant stop and clear on interrupt
    - Callback when playback completes
    """
    
    def __init__(
        self,
        websocket: Optional[WebSocket],
        stream_sid: Optional[str],
        local_audio: Optional[LocalAudioIO] = None,
        on_done: Optional[Callable[[], None]] = None,
    ):
        self._websocket = websocket
        self._stream_sid = stream_sid
        self._local_audio = local_audio
        self._on_done = on_done
        
        self._chunks: List[str] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._index = 0
        self._tts_done = False
        self._last_chunk_at = 0.0
    
    @property
    def is_playing(self) -> bool:
        return self._running and self._task is not None and not self._task.done()
    
    async def start(self) -> None:
        """Start the playback loop."""
        if self.is_playing:
            await self.stop_and_clear()
        
        self._chunks = []
        self._index = 0
        self._running = True
        self._tts_done = False
        self._last_chunk_at = time.monotonic()
        
        self._task = asyncio.create_task(self._playback_loop())
    
    async def send_chunk(self, chunk: str) -> None:
        """Add an audio chunk to the playback queue."""
        if not self._running:
            await self.start()
        
        self._chunks.append(chunk)
        self._last_chunk_at = time.monotonic()
    
    def mark_tts_done(self) -> None:
        """Signal that TTS is complete - no more chunks coming."""
        self._tts_done = True
    
    async def play(self, chunks: List[str]) -> None:
        """Start playing a fixed list of audio chunks (legacy mode)."""
        if self.is_playing:
            await self.stop_and_clear()
        
        self._chunks = list(chunks)
        self._index = 0
        self._running = True
        self._tts_done = True
        self._last_chunk_at = time.monotonic()
        
        self._task = asyncio.create_task(self._playback_loop())
    
    async def stop_and_clear(self) -> None:
        """Stop playback immediately and clear Twilio's buffer."""
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self._task = None
        self._chunks = []
        self._index = 0
        self._tts_done = False
        self._last_chunk_at = 0.0
        
        await self._send_clear()
    
    async def wait_until_done(self) -> None:
        """Wait for playback to complete (or be interrupted)."""
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _playback_loop(self) -> None:
        """Independent loop that drips audio at ~20ms intervals."""
        try:
            while self._running:
                if self._index < len(self._chunks):
                    chunk = self._chunks[self._index]
                    await self._send_audio(chunk)
                    self._index += 1

                    if self._local_audio is not None:
                        await asyncio.sleep(0)
                    else:
                        await asyncio.sleep(0.020)
                    
                elif self._tts_done:
                    if self._local_audio is not None and self._local_audio.pending_audio_bytes() > 0:
                        await asyncio.sleep(0.010)
                        continue
                    break
                else:
                    if self._local_audio is not None:
                        pending = self._local_audio.pending_audio_bytes()
                        idle_s = time.monotonic() - self._last_chunk_at
                        if pending == 0 and idle_s >= LOCAL_TAIL_TIMEOUT_S:
                            log.info("Local tail timeout reached; completing turn")
                            break
                    await asyncio.sleep(0.010)
            
            if self._running:
                self._running = False
                if self._on_done:
                    self._on_done()
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("Playback failed", e)
            self._running = False
    
    async def _send_audio(self, payload: str) -> None:
        """Send a single audio chunk to Twilio."""
        if self._local_audio is not None:
            await self._local_audio.play_ulaw_base64(payload)
            return

        if not self._websocket or not self._stream_sid:
            return

        message = {
            "event": "media",
            "streamSid": self._stream_sid,
            "media": {
                "payload": payload
            }
        }
        await self._websocket.send_text(json.dumps(message))
    
    async def _send_clear(self) -> None:
        """Send clear message to Twilio to flush audio buffer."""
        if self._local_audio is not None:
            self._local_audio.clear_playback()
            return

        if not self._websocket or not self._stream_sid:
            return

        message = {
            "event": "clear",
            "streamSid": self._stream_sid
        }
        await self._websocket.send_text(json.dumps(message))
