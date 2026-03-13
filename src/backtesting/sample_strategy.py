"""Moving Average Crossover — a simple strategy to prove the backtester works.

This exact class works on both live GrowwBroker ticks and backtester replay.
It subscribes to `market:tick`, maintains a rolling price window,
and emits `trade:signal` when short MA crosses long MA.
"""

from collections import defaultdict, deque
from datetime import datetime

from src.analysis.base import Signal, SignalType
from src.strategy.base import TradeAction, TradeSignal
from src.core.events import EventBus


class MovingAverageCrossover:
    name = "ma_crossover"

    def __init__(
        self,
        events: EventBus,
        short_window: int = 5,
        long_window: int = 20,
        quantity: int = 1,
    ):
        self._events = events
        self._short_window = short_window
        self._long_window = long_window
        self._quantity = quantity
        self._prices: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=long_window + 1)
        )
        self._in_position: dict[str, bool] = defaultdict(bool)

    async def start(self) -> None:
        self._events.on("market:tick", self._on_tick)

    async def stop(self) -> None:
        self._events.off("market:tick", self._on_tick)

    async def evaluate(self, signals: list[Signal]) -> list[TradeSignal]:
        return []

    async def _on_tick(
        self, symbol: str, price: float, timestamp: datetime, **_
    ) -> None:
        prices = self._prices[symbol]
        prices.append(price)

        if len(prices) < self._long_window:
            return

        price_list = list(prices)
        short_ma = sum(price_list[-self._short_window :]) / self._short_window
        long_ma = sum(price_list[-self._long_window :]) / self._long_window

        prev_prices = price_list[:-1]
        if len(prev_prices) < self._long_window:
            return

        prev_short = sum(prev_prices[-self._short_window :]) / self._short_window
        prev_long = sum(prev_prices[-self._long_window :]) / self._long_window

        # Golden cross: short MA crosses above long MA → BUY
        if prev_short <= prev_long and short_ma > long_ma and not self._in_position[symbol]:
            signal = TradeSignal(
                action=TradeAction.BUY,
                symbol=symbol,
                quantity=self._quantity,
                confidence=0.7,
                reasoning=f"Golden cross: SMA{self._short_window}={short_ma:.2f} > SMA{self._long_window}={long_ma:.2f}",
                style="swing",
                timestamp=timestamp,
            )
            self._in_position[symbol] = True
            await self._events.emit("trade:signal", signal=signal)

        # Death cross: short MA crosses below long MA → SELL
        elif prev_short >= prev_long and short_ma < long_ma and self._in_position[symbol]:
            signal = TradeSignal(
                action=TradeAction.SELL,
                symbol=symbol,
                quantity=self._quantity,
                confidence=0.7,
                reasoning=f"Death cross: SMA{self._short_window}={short_ma:.2f} < SMA{self._long_window}={long_ma:.2f}",
                style="swing",
                timestamp=timestamp,
            )
            self._in_position[symbol] = False
            await self._events.emit("trade:signal", signal=signal)
