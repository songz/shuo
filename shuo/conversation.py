"""
The main event loop for shuo.

This is the explicit, readable loop that drives the entire system:

    while connected:
        event = receive()                               # I/O (from queue)
        state, actions = process_event(state, event)    # PURE
        for action in actions:
            dispatch(action)                            # I/O

Events come from:
- Twilio WebSocket (audio packets)
- Deepgram Flux (turn events)
- Agent (playback complete)
"""

import asyncio
import pygame
from typing import Optional

from .types import (
    AppState,
    Phase,
    Event, StreamStartEvent, MediaEvent,
    FluxStartOfTurnEvent, FluxEndOfTurnEvent, AgentTurnDoneEvent,
    FeedFluxAction, StartAgentTurnAction, ResetAgentTurnAction,
)
from .state import process_event
from .services.flux import FluxService
from .services.tts_pool import TTSPool
from .services.local_audio import LocalAudioIO
from .agent import Agent
from .tracer import Tracer
from .log import Logger

from state_loader import StateLoader


async def run_conversation_local() -> None:
    """
    Main event loop for local microphone/speaker mode.

    Reuses the same state machine and agent pipeline as Twilio mode,
    but sources audio from local mic and plays audio on local speakers.
    """
    event_log = Logger(verbose=False)
    event_queue: asyncio.Queue[Event] = asyncio.Queue()
    tracer = Tracer()

    agent: Optional[Agent] = None
    tts_pool = TTSPool(pool_size=1, ttl=8.0)
    
    pygame.init()
    StateLoader.load_state('idle')

    async def on_flux_end_of_turn(transcript: str) -> None:
        await event_queue.put(FluxEndOfTurnEvent(transcript=transcript))

    async def on_flux_start_of_turn() -> None:
        await event_queue.put(FluxStartOfTurnEvent())

    async def on_mic_audio(audio_bytes: bytes) -> None:
        await event_queue.put(MediaEvent(audio_bytes=audio_bytes))

    flux = FluxService(
        on_end_of_turn=on_flux_end_of_turn,
        on_start_of_turn=on_flux_start_of_turn,
    )
    local_audio = LocalAudioIO(on_mic_audio=on_mic_audio)

    state = AppState()

    try:
        await flux.start()
        await tts_pool.start()
        await local_audio.start()

        await event_queue.put(StreamStartEvent(stream_sid="local"))

        while True:
            event = await event_queue.get()
            event_log.event(event)

            if isinstance(event, StreamStartEvent):
                agent = Agent(
                    websocket=None,
                    stream_sid="local",
                    on_done=lambda: event_queue.put_nowait(AgentTurnDoneEvent()),
                    tts_pool=tts_pool,
                    tracer=tracer,
                    local_audio=local_audio,
                )

            old_phase = state.phase
            state, actions = process_event(state, event)
            event_log.transition(old_phase, state.phase)

            if state.phase == Phase.LISTENING:
                StateLoader.load_state('listening')
            elif state.phase == Phase.RESPONDING:
                StateLoader.load_state('speaking')


            for action in actions:
                event_log.action(action)
                if isinstance(action, FeedFluxAction):
                    if state.phase == Phase.LISTENING:
                        await flux.send(action.audio_bytes)

                elif isinstance(action, StartAgentTurnAction):
                    if agent:
                        await agent.start_turn(action.transcript)

                elif isinstance(action, ResetAgentTurnAction):
                    if agent:
                        await agent.cancel_turn()

    finally:
        if agent:
            await agent.cleanup()

        await local_audio.stop()
        await tts_pool.stop()
        await flux.stop()

        tracer.save("local")

    pygame.quit()
