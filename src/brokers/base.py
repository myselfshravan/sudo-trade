from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Protocol, runtime_checkable
from datetime import datetime


class BrokerRole(Flag):
    """A broker can serve as data source, executor, or both."""
    DATA = auto()
    EXECUTION = auto()
    BOTH = DATA | EXECUTION


@dataclass
class Quote:
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    exchange: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Order:
    symbol: str
    side: str  # BUY | SELL
    quantity: int
    order_type: str  # MARKET | LIMIT | SL | SL-M
    price: float | None = None
    trigger_price: float | None = None
    product: str = "CNC"  # CNC | MIS | NRML
    exchange: str = "NSE"
    tag: str = ""


@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    pnl: float
    product: str = ""
    exchange: str = ""


@runtime_checkable
class Broker(Protocol):
    """Broker plugin protocol.

    A broker can be assigned roles independently:
    - DATA: provides market quotes, historical data
    - EXECUTION: places and manages orders
    - BOTH: does everything

    Multiple brokers can run simultaneously with different roles.
    E.g., Groww for data + Kite for execution.
    """
    name: str
    role: BrokerRole

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    # Data role
    async def get_quote(self, symbol: str) -> Quote: ...
    async def get_quotes(self, symbols: list[str]) -> list[Quote]: ...
    async def get_historical(
        self, symbol: str, interval: str, from_date: str, to_date: str
    ) -> list[dict]: ...

    # Execution role
    async def place_order(self, order: Order) -> str: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def get_orders(self) -> list[dict]: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_holdings(self) -> list[dict]: ...
