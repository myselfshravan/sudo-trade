from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class RawData:
    """Generic data envelope from any provider."""

    source: str
    content: str
    url: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """Data provider plugin. Scrapes, fetches, or streams data from any source.

    Each provider handles one source type: news API, Reddit, X, RSS, etc.
    Providers emit raw data — analysis plugins interpret it.
    """

    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def fetch(self, query: str | None = None) -> list[RawData]: ...
    async def stream(self) -> None:
        """Optional: push data via event bus in real-time."""
        ...
