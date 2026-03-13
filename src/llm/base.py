from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, Any


@dataclass
class Message:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


@runtime_checkable
class LLM(Protocol):
    """LLM plugin protocol. OpenAI-compatible schema by default.

    Claude Opus for heavy thinking, but the interface supports any model.
    Swap, chain, or run multiple models in parallel.
    """
    name: str
    model: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def complete(self, messages: list[Message], **kwargs: Any) -> LLMResponse: ...

    async def analyze(self, prompt: str, **kwargs: Any) -> str:
        """Convenience: single prompt in, text out."""
        ...
