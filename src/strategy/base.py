from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable, Any

from src.analysis.base import Signal


class TradeAction(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    SHORT = "short"
    COVER = "cover"


@dataclass
class TradeSignal:
    """The strategy engine's final verdict — what to trade and why."""
    action: TradeAction
    symbol: str
    quantity: int
    confidence: float  # 0.0 to 1.0
    reasoning: str
    style: str = ""  # intraday | swing | positional
    product: str = "CNC"  # CNC | MIS | NRML
    exchange: str = "NSE"
    price_target: float | None = None
    stop_loss: float | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    signals_used: list[Signal] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Strategy(Protocol):
    """Strategy plugin. Consumes signals, produces trade decisions.

    The AI picks the style — intraday, swing, positional, equities, F&O.
    Multiple strategies can run in parallel, each with its own logic.
    """
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def evaluate(self, signals: list[Signal]) -> list[TradeSignal]: ...
