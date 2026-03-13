import asyncio
import pytest
from datetime import datetime

from src.core.events import EventBus
from src.backtesting.base import BacktestConfig, Candle, print_report
from src.backtesting.engine import Backtester
from src.backtesting.data_loader import CSVDataLoader
from src.backtesting.simulator import FillSimulator, PositionTracker
from src.backtesting.sample_strategy import MovingAverageCrossover
from src.strategy.base import TradeAction, TradeSignal


class SyntheticLoader:
    """Generates a V-shaped price pattern for predictable testing."""

    async def load(self, config: BacktestConfig) -> dict[str, list[Candle]]:
        # Price: 100 → 80 (down) → 120 (up) → 100 (down)
        prices = (
            [100 - i * 2 for i in range(10)]    # 100 → 82 (downtrend)
            + [82 + i * 4 for i in range(10)]    # 82 → 118 (uptrend)
            + [118 - i * 2 for i in range(10)]   # 118 → 100 (downtrend)
        )

        candles = []
        for i, price in enumerate(prices):
            candles.append(Candle(
                timestamp=datetime(2024, 1, 1 + i),
                open=price - 1,
                high=price + 2,
                low=price - 2,
                close=price,
                volume=100000,
            ))

        return {"TEST": candles}


class TestFillSimulator:
    def test_fill_price_buy_with_slippage(self):
        sim = FillSimulator(slippage_pct=0.1, commission_pct=0.03)
        price = sim.fill_price(100.0, "BUY")
        assert price > 100.0
        assert abs(price - 100.1) < 0.01

    def test_fill_price_sell_with_slippage(self):
        sim = FillSimulator(slippage_pct=0.1, commission_pct=0.03)
        price = sim.fill_price(100.0, "SELL")
        assert price < 100.0

    def test_commission(self):
        sim = FillSimulator(commission_pct=0.03)
        fee = sim.commission(100.0, 10)
        assert abs(fee - 0.30) < 0.01


class TestPositionTracker:
    def test_open_and_close(self):
        tracker = PositionTracker()
        now = datetime.now()

        tracker.open_position("TEST", "BUY", 10, 100.0, now)
        assert tracker.has_position("TEST")

        trade = tracker.close_position("TEST", 110.0, now)
        assert trade is not None
        assert trade.pnl == 100.0  # (110 - 100) * 10
        assert not tracker.has_position("TEST")

    def test_close_empty(self):
        tracker = PositionTracker()
        result = tracker.close_position("NONE", 100.0, datetime.now())
        assert result is None

    def test_short_position(self):
        tracker = PositionTracker()
        now = datetime.now()

        tracker.open_position("TEST", "SELL", 10, 100.0, now)
        trade = tracker.close_position("TEST", 90.0, now)
        assert trade is not None
        assert trade.pnl == 100.0  # (100 - 90) * 10


class TestBacktester:
    @pytest.mark.asyncio
    async def test_runs_with_synthetic_data(self):
        events = EventBus()
        config = BacktestConfig(
            data_source="synthetic",
            symbols=["TEST"],
            initial_capital=100_000,
        )

        strategy = MovingAverageCrossover(
            events=events, short_window=3, long_window=5, quantity=10
        )

        backtester = Backtester(
            config=config, events=events, data_loader=SyntheticLoader()
        )

        await strategy.start()
        result = await backtester.run()
        result.strategy_name = "ma_crossover"
        await strategy.stop()

        assert result.initial_capital == 100_000
        assert result.total_trades >= 0
        assert len(result.equity_curve) == 30  # 30 candles

    @pytest.mark.asyncio
    async def test_strategy_receives_ticks(self):
        events = EventBus()
        received_ticks = []

        async def on_tick(symbol: str, price: float, timestamp: datetime, **_):
            received_ticks.append((symbol, price))

        events.on("market:tick", on_tick)

        config = BacktestConfig(data_source="synthetic", symbols=["TEST"])
        backtester = Backtester(
            config=config, events=events, data_loader=SyntheticLoader()
        )

        await backtester.run()
        assert len(received_ticks) == 30
        assert all(sym == "TEST" for sym, _ in received_ticks)

    @pytest.mark.asyncio
    async def test_csv_loader_with_sample_data(self):
        loader = CSVDataLoader()
        config = BacktestConfig(
            data_source="data/reference/sample_RELIANCE.csv",
            symbols=["SAMPLE_RELIANCE"],
        )
        data = await loader.load(config)
        assert len(data) > 0
        symbol = list(data.keys())[0]
        assert len(data[symbol]) > 100

    @pytest.mark.asyncio
    async def test_full_backtest_with_csv(self):
        events = EventBus()
        config = BacktestConfig(
            data_source="data/reference/sample_RELIANCE.csv",
            symbols=[],
            initial_capital=500_000,
            commission_pct=0.03,
            slippage_pct=0.05,
        )

        strategy = MovingAverageCrossover(
            events=events, short_window=5, long_window=20, quantity=10
        )

        backtester = Backtester(
            config=config, events=events, data_loader=CSVDataLoader()
        )

        await strategy.start()
        result = await backtester.run()
        result.strategy_name = "ma_crossover"
        await strategy.stop()

        assert result.total_trades > 0
        assert result.win_rate >= 0
        assert result.max_drawdown >= 0
        assert len(result.equity_curve) > 100

    @pytest.mark.asyncio
    async def test_backtest_completed_event(self):
        events = EventBus()
        completed = []

        async def on_complete(result=None, **_):
            completed.append(result)

        events.on("backtest:completed", on_complete)

        config = BacktestConfig(data_source="synthetic", symbols=["TEST"])
        strategy = MovingAverageCrossover(
            events=events, short_window=3, long_window=5, quantity=10
        )

        backtester = Backtester(
            config=config, events=events, data_loader=SyntheticLoader()
        )

        await strategy.start()
        await backtester.run()
        await strategy.stop()

        assert len(completed) == 1
        assert completed[0] is not None
