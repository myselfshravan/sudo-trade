from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from src.strategy.base import TradeSignal


@dataclass
class TradeResult:
    signal: TradeSignal
    success: bool
    order_id: str = ""
    broker: str = ""
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Executor(Protocol):
    """Execution plugin. Takes trade signals, routes to brokers.

    Paper executor logs trades without hitting real APIs.
    Live executor routes to the appropriate broker based on role config.
    """

    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def execute(self, signal: TradeSignal) -> TradeResult: ...
    async def execute_batch(self, signals: list[TradeSignal]) -> list[TradeResult]: ...
