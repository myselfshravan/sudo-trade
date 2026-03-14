"""Run backtests from the command line.

Usage:
    uv run python -m scripts.backtest_cli --data data/reference/sample_RELIANCE.csv --strategy ma_crossover
    uv run python -m scripts.backtest_cli --data data/reference/sample_RELIANCE.csv --strategy ma_crossover --capital 200000
    uv run python -m scripts.backtest_cli --data data/reference/sample_RELIANCE.csv --strategy ma_crossover --short 10 --long 30
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from src.backtesting import (
    BacktestConfig,
    Backtester,
    CSVDataLoader,
    JSONDataLoader,
    print_report,
)
from src.backtesting.sample_strategy import MovingAverageCrossover
from src.core import EventBus, setup_logger

STRATEGIES = {
    "ma_crossover": MovingAverageCrossover,
}


async def main() -> None:
    parser = argparse.ArgumentParser(description="sudo-trade Backtester")
    parser.add_argument("--data", required=True, help="Path to CSV/JSON data file or directory")
    parser.add_argument("--strategy", default="ma_crossover", choices=list(STRATEGIES.keys()))
    parser.add_argument("--symbol", default=None, help="Symbol (defaults to filename)")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--commission", type=float, default=0.03, help="Commission %")
    parser.add_argument("--slippage", type=float, default=0.05, help="Slippage %")
    parser.add_argument("--short", type=int, default=5, help="Short MA window")
    parser.add_argument("--long", type=int, default=20, help="Long MA window")
    parser.add_argument("--quantity", type=int, default=10, help="Shares per trade")
    parser.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default=None, help="Save results JSON to path")

    args = parser.parse_args()

    setup_logger(level="INFO", json_output=False)
    events = EventBus()

    symbols = [args.symbol] if args.symbol else []
    start_date = datetime.strptime(args.start, "%Y-%m-%d") if args.start else None
    end_date = datetime.strptime(args.end, "%Y-%m-%d") if args.end else None

    config = BacktestConfig(
        data_source=args.data,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.capital,
        commission_pct=args.commission,
        slippage_pct=args.slippage,
    )

    data_path = Path(args.data)
    if data_path.suffix == ".json":
        loader = JSONDataLoader()
    else:
        loader = CSVDataLoader()

    strategy_cls = STRATEGIES[args.strategy]
    strategy = strategy_cls(
        events=events,
        short_window=args.short,
        long_window=args.long,
        quantity=args.quantity,
    )

    backtester = Backtester(config=config, events=events, data_loader=loader)

    await strategy.start()
    result = await backtester.run()
    result.strategy_name = strategy.name
    await strategy.stop()

    print_report(result)

    if result.trades:
        print("  Recent trades:")
        for t in result.trades[-10:]:
            sign = "+" if t.pnl >= 0 else ""
            print(
                f"    {t.entry_time.strftime('%Y-%m-%d')} → {t.exit_time.strftime('%Y-%m-%d')}"
                f"  {t.side:<4}  {t.symbol:<10}  {t.quantity:>4}  "
                f"₹{t.entry_price:>10,.2f} → ₹{t.exit_price:>10,.2f}  "
                f"P&L: {sign}₹{t.pnl:,.2f}"
            )
        print()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result.to_dict(), indent=2))
        print(f"  Results saved to {args.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
