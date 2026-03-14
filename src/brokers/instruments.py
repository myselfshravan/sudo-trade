import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp

INSTRUMENTS_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"


@dataclass
class InstrumentInfo:
    exchange: str
    segment: str
    exchange_token: str
    trading_symbol: str
    isin: str


class InstrumentMap:
    def __init__(self, cache_dir: str = "data/reference"):
        self._cache_dir = Path(cache_dir)
        self._cache_file = self._cache_dir / "instruments.csv"
        self._by_symbol: dict[str, list[InstrumentInfo]] = {}
        self._by_token: dict[str, InstrumentInfo] = {}
        self._loaded = False

    async def load(self) -> None:
        if self._needs_refresh():
            await self._download()
        self._parse_csv()
        self._loaded = True

    def _needs_refresh(self) -> bool:
        if not self._cache_file.exists():
            return True
        mtime = datetime.fromtimestamp(self._cache_file.stat().st_mtime)
        return datetime.now() - mtime > timedelta(days=1)

    async def _download(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        async with aiohttp.ClientSession() as session, session.get(INSTRUMENTS_URL) as resp:
            resp.raise_for_status()
            content = await resp.text()
            self._cache_file.write_text(content)

    def _parse_csv(self) -> None:
        self._by_symbol.clear()
        self._by_token.clear()

        text = self._cache_file.read_text()
        reader = csv.DictReader(io.StringIO(text))

        for row in reader:
            info = InstrumentInfo(
                exchange=row.get("exchange", ""),
                segment=row.get("segment", ""),
                exchange_token=row.get("exchange_token", ""),
                trading_symbol=row.get("trading_symbol", ""),
                isin=row.get("isin", ""),
            )
            key = f"{info.exchange}_{info.segment}_{info.trading_symbol}"
            self._by_symbol.setdefault(key, []).append(info)
            self._by_symbol.setdefault(info.trading_symbol, []).append(info)

            if info.exchange_token:
                token_key = f"{info.exchange}_{info.segment}_{info.exchange_token}"
                self._by_token[token_key] = info

    def by_symbol(
        self, trading_symbol: str, exchange: str = "NSE", segment: str = "CASH"
    ) -> InstrumentInfo | None:
        key = f"{exchange}_{segment}_{trading_symbol}"
        results = self._by_symbol.get(key, [])
        return results[0] if results else None

    def by_token(
        self, exchange_token: str, exchange: str = "NSE", segment: str = "CASH"
    ) -> InstrumentInfo | None:
        key = f"{exchange}_{segment}_{exchange_token}"
        return self._by_token.get(key)

    def search(self, query: str) -> list[InstrumentInfo]:
        query_upper = query.upper()
        seen = set()
        results = []
        for key, infos in self._by_symbol.items():
            if query_upper in key.upper():
                for info in infos:
                    uid = f"{info.exchange}_{info.segment}_{info.exchange_token}"
                    if uid not in seen:
                        seen.add(uid)
                        results.append(info)
        return results[:50]

    @property
    def loaded(self) -> bool:
        return self._loaded
