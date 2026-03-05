"""
LLM service with streaming (Groq, OpenAI-compatible).
"""

import os
import asyncio
from typing import Optional, Callable, Awaitable, List, Dict

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from ..log import ServiceLogger

log = ServiceLogger("LLM")

SYSTEM_PROMPT = """You are a friendly, curious, and playful companion for a five-year-old child. Your voice is warm and conversational. Because you are speaking aloud, keep your answers very short—usually only two or three sentences. Never use lists, bullet points, or special formatting like bold text or hashtags. Just speak naturally.

Your goal is to be a "thinking partner." When the child says something, don't just agree. Ask a gentle, "Why do you think that?" or "What would happen if everyone did that?" to help them explore their ideas. If they say something that doesn't quite make sense, ask a curious question to help them figure it out on their own rather than correcting them.

If the child mentions a big topic like sharing, bravery, honesty, or science, ask if they would like to hear a tiny story about someone from history who lived through that. Keep these stories grounded in real facts but told in a magical, engaging way that inspires them to be kind and brave.

Always end your turn with an inviting question that makes them want to keep talking to you. Keep the energy high, use silly (but clear) words occasionally, and always be encouraging."""


class LLMService:
    """
    OpenAI streaming LLM service.
    
    Manages conversation history and streams tokens via callback.
    """
    
    def __init__(
        self,
        on_token: Callable[[str], Awaitable[None]],
        on_done: Callable[[], Awaitable[None]],
    ):
        self._on_token = on_token
        self._on_done = on_done

        model_env = os.getenv("LLM_MODEL", "").strip()
        provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
        openai_key = os.getenv("OPENAI_API_KEY", "")
        groq_key = os.getenv("GROQ_API_KEY", "")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

        if provider == "anthropic" or (provider == "auto" and anthropic_key):
            if not anthropic_key:
                raise ValueError("LLM provider is anthropic, but ANTHROPIC_API_KEY is missing")
            self._client = AsyncAnthropic(api_key=anthropic_key)
            self._model = model_env or "claude-3-5-haiku-latest"
            self._provider = "anthropic"
        elif provider == "groq" or (provider == "auto" and groq_key):
            if not groq_key:
                raise ValueError("LLM provider is groq, but GROQ_API_KEY is missing")
            self._client = AsyncOpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
            self._model = model_env or "llama-3.3-70b-versatile"
            self._provider = "groq"
        else:
            if not openai_key:
                raise ValueError("LLM provider is openai, but OPENAI_API_KEY is missing")
            self._client = AsyncOpenAI(api_key=openai_key)
            self._model = model_env or "gpt-4o-mini"
            self._provider = "openai"

        log.info(f"Provider: {self._provider}, model: {self._model}")
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
        self._history: List[Dict[str, str]] = []
    
    @property
    def is_active(self) -> bool:
        return self._running and self._task is not None
    
    @property
    def history(self) -> List[Dict[str, str]]:
        return self._history.copy()
    
    def clear_history(self) -> None:
        self._history = []
    
    async def start(self, user_message: str) -> None:
        """Start generating a response."""
        if self._running:
            await self.cancel()
        
        self._history.append({"role": "user", "content": user_message})
        
        self._running = True
        self._task = asyncio.create_task(self._generate())
        log.connected()
    
    async def cancel(self) -> None:
        """Cancel ongoing generation."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        log.cancelled()
    
    async def _generate(self) -> None:
        """Generate response and stream tokens."""
        assistant_response = ""
        
        try:
            if self._provider == "anthropic":
                messages = self._history.copy()
                stream = await self._client.messages.create(
                    model=self._model,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7,
                    stream=True,
                )

                async for event in stream:
                    if not self._running:
                        break

                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        token = event.delta.text
                        assistant_response += token
                        await self._on_token(token)
            else:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT}
                ] + self._history

                stream = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    max_tokens=500,
                    temperature=0.7,
                )

                async for chunk in stream:
                    if not self._running:
                        break

                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        token = delta.content
                        assistant_response += token
                        await self._on_token(token)
            
            if self._running and assistant_response:
                self._history.append({"role": "assistant", "content": assistant_response})
                await self._on_done()
        
        except asyncio.CancelledError:
            if assistant_response:
                self._history.append({"role": "assistant", "content": assistant_response + "..."})
            raise
        
        except Exception as e:
            log.error("Generation failed", e)
            await self._on_done()
        
        finally:
            self._running = False
            self._task = None
