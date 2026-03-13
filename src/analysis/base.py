from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable, Any


class SignalType(Enum):
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"
    NEWS = "news"
    SOCIAL = "social"
    CUSTOM = "custom"


@dataclass
class Signal:
    """A single analysis signal that feeds into the strategy engine."""
    type: SignalType
    symbol: str
    value: float  # -1.0 (bearish) to 1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    source: str
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Analyzer(Protocol):
    """Analysis plugin. Takes raw data, produces trading signals.

    Each analyzer focuses on one signal type:
    - Sentiment analyzer: text → sentiment signal
    - Technical analyzer: price data → technical signal
    - Social analyzer: social media → social signal
    """
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def analyze(self, data: Any) -> list[Signal]: ...
