import asyncio
import math
from datetime import datetime
from typing import Any

from src.backtesting.base import BacktestConfig, BacktestResult, BacktestTrade, Candle
from src.backtesting.data_loader import DataLoader
from src.backtesting.simulator import FillSimulator, PositionTracker
from src.core.events import EventBus
from src.core.logger import get_logger

log = get_logger()


class Backtester:
    """Replays historical data through the EventBus.

    Strategies see the same `market:tick` and `market:quote` events
    as live trading. They emit `trade:signal` events which the
    backtester intercepts and fills against historical prices.
    """

    name = "backtester"

    def __init__(
        self,
        config: BacktestConfig,
        events: EventBus,
        data_loader: DataLoader,
    ):
        self._config = config
        self._events = events
        self._data_loader = data_loader
        self._simulator = FillSimulator(
            slippage_pct=config.slippage_pct,
            commission_pct=config.commission_pct,
        )
        self._tracker = PositionTracker()
        self._capital = config.initial_capital
        self._trades: list[BacktestTrade] = []
        self._equity_curve: list[tuple[datetime, float]] = []
        self._pending_signals: list[dict] = []
        self._current_candle: dict[str, Candle] = {}

    async def start(self) -> None:
        self._events.on("trade:signal", self._on_trade_signal)

    async def stop(self) -> None:
        self._events.off("trade:signal", self._on_trade_signal)

    async def run(self) -> BacktestResult:
        await self.start()

        data = await self._data_loader.load(self._config)
        if not data:
            raise ValueError("No data loaded for backtest")

        timeline = self._build_timeline(data)
        log.info(f"backtester: {len(timeline)} ticks to replay")

        for timestamp, symbol, candle in timeline:
            self._current_candle[symbol] = candle

            await self._events.emit(
                "market:tick",
                symbol=symbol,
                price=candle.close,
                timestamp=timestamp,
            )

            await self._events.emit(
                "market:quote",
                symbol=symbol,
                price=candle.close,
                volume=candle.volume,
                timestamp=timestamp,
                exchange="BACKTEST",
                ohlc={
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                },
                extra={},
            )

            await asyncio.sleep(0)

            self._process_pending_signals(timestamp)

            unrealized = sum(
                self._tracker.position_value(sym, self._current_candle[sym].close)
                for sym in self._tracker.open_symbols()
                if sym in self._current_candle
            )
            self._equity_curve.append((timestamp, self._capital + unrealized))

        self._close_remaining_positions(timeline[-1][0] if timeline else datetime.now())

        result = self._calculate_result(timeline)

        await self._events.emit("backtest:completed", result=result)
        await self.stop()

        return result

    async def _on_trade_signal(self, signal: Any = None, **kwargs: Any) -> None:
        if signal is not None:
            self._pending_signals.append({"signal": signal})

    def _process_pending_signals(self, timestamp: datetime) -> None:
        for item in self._pending_signals:
            signal = item["signal"]
            candle = self._current_candle.get(signal.symbol)
            if not candle:
                continue

            if signal.action.value in ("buy", "short"):
                fill_side = "BUY" if signal.action.value == "buy" else "SELL"
                fill_price = self._simulator.fill_price(candle.close, fill_side)
                cost = fill_price * signal.quantity
                fees = self._simulator.commission(fill_price, signal.quantity)

                if fill_side == "BUY" and cost + fees > self._capital:
                    continue

                self._capital -= (cost + fees) if fill_side == "BUY" else -fees
                self._tracker.open_position(
                    signal.symbol, fill_side, signal.quantity, fill_price, timestamp
                )

            elif signal.action.value in ("sell", "cover"):
                if not self._tracker.has_position(signal.symbol):
                    continue

                fill_side = "SELL" if signal.action.value == "sell" else "BUY"
                fill_price = self._simulator.fill_price(candle.close, fill_side)
                fees = self._simulator.commission(fill_price, signal.quantity)

                trade = self._tracker.close_position(signal.symbol, fill_price, timestamp, fees)
                if trade:
                    self._trades.append(trade)
                    self._capital += fill_price * signal.quantity - fees

        self._pending_signals.clear()

    def _close_remaining_positions(self, final_timestamp: datetime) -> None:
        for symbol in list(self._tracker.open_symbols()):
            candle = self._current_candle.get(symbol)
            if not candle:
                continue
            price = candle.close
            fees = self._simulator.commission(price, 1)
            trade = self._tracker.close_position(symbol, price, final_timestamp, fees)
            if trade:
                self._trades.append(trade)
                self._capital += price * trade.quantity - fees

    def _build_timeline(self, data: dict[str, list[Candle]]) -> list[tuple[datetime, str, Candle]]:
        timeline = []
        for symbol, candles in data.items():
            for candle in candles:
                timeline.append((candle.timestamp, symbol, candle))
        timeline.sort(key=lambda x: x[0])
        return timeline

    def _calculate_result(self, timeline: list[tuple[datetime, str, Candle]]) -> BacktestResult:
        winning = [t for t in self._trades if t.pnl > 0]
        losing = [t for t in self._trades if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in self._trades)

        start_date = timeline[0][0] if timeline else datetime.now()
        end_date = timeline[-1][0] if timeline else datetime.now()

        return BacktestResult(
            strategy_name="",
            start_date=start_date,
            end_date=end_date,
            initial_capital=self._config.initial_capital,
            final_capital=self._capital,
            trades=self._trades,
            total_trades=len(self._trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=(len(winning) / len(self._trades) * 100) if self._trades else 0,
            total_pnl=total_pnl,
            max_drawdown=self._calculate_drawdown(),
            sharpe_ratio=self._calculate_sharpe(),
            equity_curve=self._equity_curve,
        )

    def _calculate_drawdown(self) -> float:
        if not self._equity_curve:
            return 0.0
        peak = self._equity_curve[0][1]
        max_dd = 0.0
        for _, equity in self._equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd

    def _calculate_sharpe(self, risk_free_rate: float = 0.05) -> float:
        if len(self._equity_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self._equity_curve)):
            prev = self._equity_curve[i - 1][1]
            curr = self._equity_curve[i][1]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance) if variance > 0 else 0

        if std == 0:
            return 0.0

        daily_rf = risk_free_rate / 252
        annualized = math.sqrt(252) * (mean_return - daily_rf) / std
        return annualized
