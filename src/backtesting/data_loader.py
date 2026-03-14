import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.backtesting.base import BacktestConfig, Candle


@runtime_checkable
class DataLoader(Protocol):
    async def load(self, config: BacktestConfig) -> dict[str, list[Candle]]:
        """Load candles grouped by symbol."""
        ...


class CSVDataLoader:
    """Load OHLCV data from CSV files.

    Expected columns: timestamp/date, open, high, low, close, volume
    Auto-detects common date formats.
    """

    async def load(self, config: BacktestConfig) -> dict[str, list[Candle]]:
        path = Path(config.data_source)

        if path.is_dir():
            return await self._load_directory(path, config)
        return await self._load_file(path, config)

    async def _load_directory(self, path: Path, config: BacktestConfig) -> dict[str, list[Candle]]:
        result = {}
        for csv_file in sorted(path.glob("*.csv")):
            symbol = csv_file.stem.upper()
            if config.symbols and symbol not in [s.upper() for s in config.symbols]:
                continue
            candles = self._parse_csv(csv_file)
            candles = self._filter_dates(candles, config)
            if candles:
                result[symbol] = candles
        return result

    async def _load_file(self, path: Path, config: BacktestConfig) -> dict[str, list[Candle]]:
        symbol = config.symbols[0] if config.symbols else path.stem.upper()
        candles = self._parse_csv(path)
        candles = self._filter_dates(candles, config)
        return {symbol: candles} if candles else {}

    def _parse_csv(self, path: Path) -> list[Candle]:
        candles = []
        text = path.read_text()
        reader = csv.DictReader(text.splitlines())

        for row in reader:
            ts = self._parse_timestamp(row)
            if ts is None:
                continue

            candles.append(
                Candle(
                    timestamp=ts,
                    open=float(row.get("open", row.get("Open", 0))),
                    high=float(row.get("high", row.get("High", 0))),
                    low=float(row.get("low", row.get("Low", 0))),
                    close=float(row.get("close", row.get("Close", 0))),
                    volume=int(float(row.get("volume", row.get("Volume", 0)))),
                )
            )

        candles.sort(key=lambda c: c.timestamp)
        return candles

    def _parse_timestamp(self, row: dict) -> datetime | None:
        raw = row.get("timestamp") or row.get("date") or row.get("Date") or row.get("Timestamp")
        if raw is None:
            return None

        raw = raw.strip()

        # Epoch seconds
        try:
            val = float(raw)
            if val > 1e12:
                return datetime.fromtimestamp(val / 1000)
            return datetime.fromtimestamp(val)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

        return None

    def _filter_dates(self, candles: list[Candle], config: BacktestConfig) -> list[Candle]:
        filtered = candles
        if config.start_date:
            filtered = [c for c in filtered if c.timestamp >= config.start_date]
        if config.end_date:
            filtered = [c for c in filtered if c.timestamp <= config.end_date]
        return filtered


class JSONDataLoader:
    """Load OHLCV data from JSON files.

    Expected: array of objects with timestamp, open, high, low, close, volume.
    """

    async def load(self, config: BacktestConfig) -> dict[str, list[Candle]]:
        path = Path(config.data_source)
        data = json.loads(path.read_text())

        symbol = config.symbols[0] if config.symbols else path.stem.upper()
        candles = []

        for item in data:
            ts = item.get("timestamp") or item.get("date")
            if isinstance(ts, (int, float)):
                ts = datetime.fromtimestamp(ts if ts < 1e12 else ts / 1000)
            elif isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            else:
                continue

            candles.append(
                Candle(
                    timestamp=ts,
                    open=float(item.get("open", 0)),
                    high=float(item.get("high", 0)),
                    low=float(item.get("low", 0)),
                    close=float(item.get("close", 0)),
                    volume=int(item.get("volume", 0)),
                )
            )

        candles.sort(key=lambda c: c.timestamp)

        if config.start_date:
            candles = [c for c in candles if c.timestamp >= config.start_date]
        if config.end_date:
            candles = [c for c in candles if c.timestamp <= config.end_date]

        return {symbol: candles} if candles else {}
