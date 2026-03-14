from datetime import datetime

from src.backtesting.base import BacktestTrade


class FillSimulator:
    """Simulates order fills with slippage and commission."""

    def __init__(self, slippage_pct: float = 0.0, commission_pct: float = 0.0):
        self.slippage_pct = slippage_pct
        self.commission_pct = commission_pct

    def fill_price(self, base_price: float, side: str) -> float:
        if side == "BUY":
            return base_price * (1 + self.slippage_pct / 100)
        return base_price * (1 - self.slippage_pct / 100)

    def commission(self, price: float, quantity: int) -> float:
        return price * quantity * self.commission_pct / 100


class PositionTracker:
    """Tracks open positions and generates trades on close."""

    def __init__(self):
        self._positions: dict[str, list[dict]] = {}

    def open_position(
        self, symbol: str, side: str, quantity: int, price: float, timestamp: datetime
    ) -> None:
        if symbol not in self._positions:
            self._positions[symbol] = []
        self._positions[symbol].append(
            {
                "side": side,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
            }
        )

    def close_position(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        fees: float = 0.0,
    ) -> BacktestTrade | None:
        positions = self._positions.get(symbol, [])
        if not positions:
            return None

        entry = positions.pop(0)
        if not positions:
            del self._positions[symbol]

        qty = entry["quantity"]
        entry_price = entry["price"]

        if entry["side"] == "BUY":
            pnl = (price - entry_price) * qty - fees
        else:
            pnl = (entry_price - price) * qty - fees

        return BacktestTrade(
            symbol=symbol,
            side=entry["side"],
            quantity=qty,
            entry_price=entry_price,
            exit_price=price,
            entry_time=entry["timestamp"],
            exit_time=timestamp,
            pnl=pnl,
            fees=fees,
        )

    def has_position(self, symbol: str) -> bool:
        return bool(self._positions.get(symbol))

    def get_position_side(self, symbol: str) -> str | None:
        positions = self._positions.get(symbol, [])
        return positions[0]["side"] if positions else None

    def open_symbols(self) -> list[str]:
        return list(self._positions.keys())

    def position_value(self, symbol: str, current_price: float) -> float:
        positions = self._positions.get(symbol, [])
        if not positions:
            return 0.0
        entry = positions[0]
        qty = entry["quantity"]
        if entry["side"] == "BUY":
            return (current_price - entry["price"]) * qty
        return (entry["price"] - current_price) * qty
