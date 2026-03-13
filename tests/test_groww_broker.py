import asyncio
import csv
import io
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.brokers.instruments import InstrumentMap, InstrumentInfo
from src.brokers.rate_limiter import RateLimiter, GrowwRateLimits
from src.brokers.groww import GrowwBroker
from src.brokers.base import BrokerRole, Quote
from src.core.events import EventBus
from src.core.config import Config


SAMPLE_CSV = """exchange,segment,exchange_token,trading_symbol,isin
NSE,CASH,2885,RELIANCE,INE002A01018
NSE,CASH,1594,INFY,INE009A01021
NSE,FNO,35241,NIFTY25MARFUT,NIFTY25MARFUT
BSE,CASH,500325,RELIANCE,INE002A01018
"""


class TestInstrumentMap:
    def setup_method(self):
        self.map = InstrumentMap(cache_dir="/tmp/test_instruments")

    def _write_sample_csv(self):
        path = Path("/tmp/test_instruments/instruments.csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SAMPLE_CSV)

    def test_parse_csv(self):
        self._write_sample_csv()
        self.map._parse_csv()

        info = self.map.by_symbol("RELIANCE", "NSE", "CASH")
        assert info is not None
        assert info.exchange_token == "2885"
        assert info.isin == "INE002A01018"

    def test_by_symbol_not_found(self):
        self._write_sample_csv()
        self.map._parse_csv()

        assert self.map.by_symbol("DOESNOTEXIST") is None

    def test_by_token(self):
        self._write_sample_csv()
        self.map._parse_csv()

        info = self.map.by_token("2885", "NSE", "CASH")
        assert info is not None
        assert info.trading_symbol == "RELIANCE"

    def test_search(self):
        self._write_sample_csv()
        self.map._parse_csv()

        results = self.map.search("RELIANCE")
        assert len(results) >= 1
        symbols = [r.trading_symbol for r in results]
        assert "RELIANCE" in symbols

    def test_search_partial(self):
        self._write_sample_csv()
        self.map._parse_csv()

        results = self.map.search("INF")
        assert any(r.trading_symbol == "INFY" for r in results)


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = RateLimiter(per_second=5, per_minute=100)
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_rate_limits_class(self):
        limits = GrowwRateLimits()
        assert limits.orders is not None
        assert limits.live_data is not None
        assert limits.non_trading is not None


class TestGrowwBrokerMapping:
    def test_parse_interval(self):
        assert GrowwBroker._parse_interval("1m") == 1
        assert GrowwBroker._parse_interval("5m") == 5
        assert GrowwBroker._parse_interval("1h") == 60
        assert GrowwBroker._parse_interval("1d") == 1440
        assert GrowwBroker._parse_interval("1w") == 10080

    def test_parse_date(self):
        dt = GrowwBroker._parse_date("2025-01-15")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15

        dt = GrowwBroker._parse_date("2025-01-15 09:30:00")
        assert dt.hour == 9
        assert dt.minute == 30


class TestEventBus:
    @pytest.mark.asyncio
    async def test_emit_nowait(self):
        bus = EventBus()
        received = []

        async def handler(symbol: str, price: float, **_):
            received.append((symbol, price))

        bus.on("market:tick", handler)
        bus.emit_nowait("market:tick", symbol="RELIANCE", price=2500.0)

        await asyncio.sleep(0.1)
        assert len(received) == 1
        assert received[0] == ("RELIANCE", 2500.0)
