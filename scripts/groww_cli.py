"""Groww broker CLI — verify data provider is working.

Usage:
    uv run python -m scripts.groww_cli quote RELIANCE
    uv run python -m scripts.groww_cli quotes RELIANCE INFY TCS
    uv run python -m scripts.groww_cli holdings
    uv run python -m scripts.groww_cli positions
    uv run python -m scripts.groww_cli historical RELIANCE --interval 1d --days 30
    uv run python -m scripts.groww_cli stream RELIANCE INFY
"""

import argparse
import asyncio
from datetime import datetime, timedelta

from src.brokers.base import BrokerRole
from src.brokers.groww import GrowwBroker
from src.core import Config, EventBus, setup_logger


def format_price(price: float) -> str:
    return f"₹{price:,.2f}"


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    lines = []
    header = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header)
    lines.append("  ".join("─" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


async def cmd_quote(broker: GrowwBroker, args: argparse.Namespace) -> None:
    quote = await broker.get_quote(args.symbol)
    ohlc = quote.extra.get("ohlc", {})
    print(f"\n  {quote.symbol} @ {quote.exchange}")
    print(f"  Price:    {format_price(quote.price)}")
    print(f"  Volume:   {quote.volume:,}")
    print(f"  Open:     {format_price(ohlc.get('open', 0))}")
    print(f"  High:     {format_price(ohlc.get('high', 0))}")
    print(f"  Low:      {format_price(ohlc.get('low', 0))}")
    print(f"  Close:    {format_price(ohlc.get('close', 0))}")
    print(f"  Change:   {quote.extra.get('day_change_perc', 0):.2f}%")
    print(f"  52W High: {format_price(quote.extra.get('week_52_high', 0))}")
    print(f"  52W Low:  {format_price(quote.extra.get('week_52_low', 0))}")
    print()


async def cmd_quotes(broker: GrowwBroker, args: argparse.Namespace) -> None:
    quotes = await broker.get_quotes(args.symbols)
    rows = [[q.symbol, format_price(q.price)] for q in quotes]
    print()
    print(format_table(["Symbol", "LTP"], rows))
    print()


async def cmd_holdings(broker: GrowwBroker, args: argparse.Namespace) -> None:
    holdings = await broker.get_holdings()
    rows = []
    for h in holdings:
        rows.append(
            [
                h.get("trading_symbol", ""),
                str(h.get("quantity", 0)),
                format_price(h.get("average_price", 0)),
                h.get("isin", ""),
            ]
        )
    print()
    print(format_table(["Symbol", "Qty", "Avg Price", "ISIN"], rows))
    print()


async def cmd_positions(broker: GrowwBroker, args: argparse.Namespace) -> None:
    positions = await broker.get_positions()
    rows = []
    for p in positions:
        rows.append(
            [
                p.symbol,
                str(p.quantity),
                format_price(p.average_price),
                format_price(p.pnl),
                p.product,
            ]
        )
    print()
    print(format_table(["Symbol", "Qty", "Avg Price", "P&L", "Product"], rows))
    print()


async def cmd_historical(broker: GrowwBroker, args: argparse.Namespace) -> None:
    end = datetime.now()
    start = end - timedelta(days=args.days)

    candles = await broker.get_historical(
        symbol=args.symbol,
        interval=args.interval,
        from_date=start.strftime("%Y-%m-%d"),
        to_date=end.strftime("%Y-%m-%d"),
    )

    rows = []
    for c in candles[-20:]:
        ts = datetime.fromtimestamp(c["timestamp"]).strftime("%Y-%m-%d %H:%M")
        rows.append(
            [
                ts,
                format_price(c["open"]),
                format_price(c["high"]),
                format_price(c["low"]),
                format_price(c["close"]),
                f"{c['volume']:,}",
            ]
        )

    print(
        f"\n  {args.symbol} — {args.interval} (last {min(20, len(candles))} of {len(candles)} candles)"
    )
    print()
    print(format_table(["Time", "Open", "High", "Low", "Close", "Volume"], rows))
    print()


async def cmd_stream(broker: GrowwBroker, args: argparse.Namespace) -> None:
    async def on_tick(symbol: str, price: float, timestamp: datetime, **_):
        ts = timestamp.strftime("%H:%M:%S")
        print(f"  {ts}  {symbol:<15}  {format_price(price)}")

    broker._events.on("market:tick", on_tick)
    await broker.subscribe(args.symbols)

    print(f"\n  Streaming {', '.join(args.symbols)} — Ctrl+C to stop\n")
    print(f"  {'Time':<10}  {'Symbol':<15}  {'Price'}")
    print(f"  {'─' * 10}  {'─' * 15}  {'─' * 15}")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await broker.unsubscribe(args.symbols)


async def main() -> None:
    parser = argparse.ArgumentParser(description="sudo-trade Groww CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_quote = sub.add_parser("quote", help="Get full quote for a symbol")
    p_quote.add_argument("symbol")

    p_quotes = sub.add_parser("quotes", help="Get LTP for multiple symbols")
    p_quotes.add_argument("symbols", nargs="+")

    sub.add_parser("holdings", help="Show portfolio holdings")
    sub.add_parser("positions", help="Show open positions")

    p_hist = sub.add_parser("historical", help="Get historical candle data")
    p_hist.add_argument("symbol")
    p_hist.add_argument("--interval", default="1d", help="1m, 5m, 1h, 1d, 1w")
    p_hist.add_argument("--days", type=int, default=30)

    p_stream = sub.add_parser("stream", help="Stream live ticks via WebSocket")
    p_stream.add_argument("symbols", nargs="+")

    args = parser.parse_args()

    setup_logger(level="WARNING", json_output=False)
    config = Config()
    events = EventBus()
    broker = GrowwBroker(events=events, config=config, role=BrokerRole.BOTH)

    await broker.start()

    commands = {
        "quote": cmd_quote,
        "quotes": cmd_quotes,
        "holdings": cmd_holdings,
        "positions": cmd_positions,
        "historical": cmd_historical,
        "stream": cmd_stream,
    }

    try:
        await commands[args.command](broker, args)
    except KeyboardInterrupt:
        pass
    finally:
        await broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
