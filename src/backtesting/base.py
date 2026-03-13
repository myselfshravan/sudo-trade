from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class BacktestConfig:
    data_source: str
    symbols: list[str]
    start_date: datetime | None = None
    end_date: datetime | None = None
    initial_capital: float = 100_000.0
    commission_pct: float = 0.0
    slippage_pct: float = 0.0
    interval: str = "1d"


@dataclass
class BacktestTrade:
    symbol: str
    side: str  # BUY | SELL
    quantity: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    fees: float = 0.0


@dataclass
class BacktestResult:
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    trades: list[BacktestTrade] = field(default_factory=list)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat(),
                    "pnl": t.pnl,
                    "fees": t.fees,
                }
                for t in self.trades
            ],
        }


def print_report(result: BacktestResult) -> None:
    pnl_pct = (result.total_pnl / result.initial_capital * 100) if result.initial_capital else 0
    sign = "+" if result.total_pnl >= 0 else ""

    print(f"\n  {'═' * 50}")
    print(f"  Backtest Report: {result.strategy_name}")
    print(f"  {'═' * 50}")
    print(f"  Period:       {result.start_date.strftime('%Y-%m-%d')} → {result.end_date.strftime('%Y-%m-%d')}")
    print(f"  Initial:      ₹{result.initial_capital:,.0f}")
    print(f"  Final:        ₹{result.final_capital:,.0f}")
    print(f"  Total P&L:    ₹{result.total_pnl:,.0f} ({sign}{pnl_pct:.1f}%)")
    print(f"  Trades:       {result.total_trades} (Win: {result.winning_trades}, Loss: {result.losing_trades})")
    print(f"  Win Rate:     {result.win_rate:.1f}%")
    print(f"  Max Drawdown: {result.max_drawdown:.1f}%")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  {'═' * 50}\n")
