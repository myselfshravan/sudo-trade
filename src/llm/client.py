"""OpenAI-compatible LLM client using aiohttp. No openai SDK dependency."""

from typing import Any

import aiohttp

from src.core.config import Config
from src.core.logger import get_logger
from src.llm.base import LLMResponse, Message

log = get_logger()


class OpenAIClient:
    """LLM plugin using any OpenAI-compatible API.

    Works with Claude, GPT, Gemini, local models — anything that speaks
    the OpenAI chat completions schema.
    """

    name = "openai_compat"

    def __init__(self, config: Config):
        self._config = config
        self._base_url = config.get("AI_BASE_URL", "https://api.openai.com/v1")
        self._api_key = config.get("OPENAI_API_KEY") or config.get("ANTHROPIC_API_KEY", "")
        self.model = config.get("AI_MODEL", "gpt-4")
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )
        log.info(f"llm client started: {self.model} @ {self._base_url}")

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def complete(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        url = f"{self._base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        async with self._session.post(url, json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"LLM API error {resp.status}: {error_text[:500]}")

            data = await resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            raw=data,
        )

    async def analyze(self, prompt: str, **kwargs: Any) -> str:
        messages = [Message(role="user", content=prompt)]
        response = await self.complete(messages, **kwargs)
        return response.content
