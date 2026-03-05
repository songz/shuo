"""
The main event loop for shuo.

This is the explicit, readable loop that drives the entire system:

    while connected:
        event = receive()                               # I/O (from queue)
        state, actions = process_event(state, event)    # PURE
        for action in actions:
            dispatch(action)                            # I/O

Events come from:
- Deepgram Flux (turn events)
- Agent (playback complete)
"""

import asyncio
from typing import Optional

from wakeword import WakewordListener

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
from .log import Logger, ServiceLogger

from state_loader import StateLoader

import pygame
# Initialize Pygame
pygame.init()

STATES = {
    pygame.K_1: 'capturing',
    pygame.K_2: 'error',
    pygame.K_3: 'idle',
    pygame.K_4: 'listening',
    pygame.K_5: 'speaking',
    pygame.K_6: 'thinking',
    pygame.K_7: 'warmup',
}
# start in warmup and immediately begin listening
StateLoader.load_state('warmup')
listener = WakewordListener(debug=True)

# once the mic is active, switch to idle
StateLoader.load_state('idle')
clock = pygame.time.Clock()


log = ServiceLogger("Conversation")

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
    convo_ongoing = False
    listener_started = False

    state = AppState()

    async def start_convo() -> None:
        nonlocal convo_ongoing
        if convo_ongoing:
            return

        await flux.start()
        await tts_pool.start()
        await local_audio.start()
        await event_queue.put(StreamStartEvent(stream_sid="local"))
        convo_ongoing = True

    async def stop_convo() -> None:
        nonlocal convo_ongoing
        if not convo_ongoing:
            return

        if agent:
            await agent.cleanup()

        await local_audio.stop()
        await tts_pool.stop()
        await flux.stop()
        convo_ongoing = False

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.FINGERDOWN or (
                    event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                ):
                    current_state = StateLoader.get_current_state()
                    if current_state == 'idle':
                        print("Touch toggle -> listening")
                    elif current_state == 'listening':
                        print("Touch toggle -> idle")
            current_state = StateLoader.get_current_state()
            if current_state == "idle":
                if not listener_started:
                    listener.start()
                    listener_started = True
                    log.info("Wakeword listener started")
                    continue
            if listener.got_wakeword():
                log.info(f"Wakeword detected, starting conversation")
                StateLoader.load_state('listening')
                listener.stop()
                await start_convo()
                continue

            if not convo_ongoing:
                await asyncio.sleep(.1)
                clock.tick(30)  # 30 FPS
                continue

            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.03)
            except asyncio.TimeoutError:
                clock.tick(30)  # 30 FPS
                continue

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
            clock.tick(30) # 30 FPS
    finally:
        await stop_convo()
        tracer.save("local")
