import asyncio
import time
from datetime import datetime, timedelta

import pyotp
from growwapi import GrowwAPI, GrowwFeed

from src.brokers.base import Broker, BrokerRole, Quote, Order, Position
from src.brokers.instruments import InstrumentMap
from src.brokers.rate_limiter import GrowwRateLimits
from src.core.events import EventBus
from src.core.config import Config
from src.core.logger import get_logger

log = get_logger()

# Historical data: max duration per request by interval
INTERVAL_MAX_DAYS = {
    1: 7,
    5: 15,
    10: 30,
    60: 150,
    240: 365,
    1440: 1080,
    10080: 3650,
}


class GrowwBroker:
    name = "groww"

    def __init__(
        self,
        events: EventBus,
        config: Config,
        role: BrokerRole = BrokerRole.BOTH,
    ):
        self.role = role
        self._events = events
        self._config = config
        self._api: GrowwAPI | None = None
        self._feed: GrowwFeed | None = None
        self._instruments = InstrumentMap()
        self._rate_limits = GrowwRateLimits()
        self._feed_task: asyncio.Task | None = None
        self._subscriptions: set[str] = set()

    async def start(self) -> None:
        log.info("groww broker starting", extra={"role": str(self.role)})

        await self._instruments.load()
        log.info("instruments loaded")

        access_token = self._authenticate()
        self._api = GrowwAPI(access_token)
        log.info("groww authenticated")

        # Feed is lazily initialized in subscribe() to avoid nested event loop issues
        # GrowwFeed uses NATS which creates its own event loop on init

    async def stop(self) -> None:
        if self._feed_task and not self._feed_task.done():
            self._feed_task.cancel()
            try:
                await self._feed_task
            except asyncio.CancelledError:
                pass
        self._api = None
        self._feed = None
        log.info("groww broker stopped")

    def _authenticate(self) -> str:
        api_key = self._config.require("GROWW_API_KEY")

        totp_secret = self._config.get("GROWW_TOTP_SECRET")
        if totp_secret and self._is_valid_base32(totp_secret):
            totp = pyotp.TOTP(totp_secret).now()
            return GrowwAPI.get_access_token(api_key=api_key, totp=totp)

        secret = self._config.get("GROWW_API_SECRET")
        if secret:
            return GrowwAPI.get_access_token(api_key=api_key, secret=secret)

        raise ValueError("Either GROWW_TOTP_SECRET (base32) or GROWW_API_SECRET required")

    @staticmethod
    def _is_valid_base32(s: str) -> bool:
        return len(s) < 200 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in s.upper())

    # ── Data methods ──

    async def get_quote(self, symbol: str) -> Quote:
        await self._rate_limits.live_data.acquire()

        info = self._instruments.by_symbol(symbol)
        if not info:
            raise ValueError(f"Unknown symbol: {symbol}")

        resp = self._api.get_quote(
            exchange=info.exchange,
            segment=info.segment,
            trading_symbol=info.trading_symbol,
        )

        quote = Quote(
            symbol=info.trading_symbol,
            price=float(resp.get("last_price", 0)),
            volume=int(resp.get("volume", 0)),
            timestamp=datetime.now(),
            exchange=info.exchange,
            extra={
                "ohlc": resp.get("ohlc", {}),
                "day_change": resp.get("day_change", 0),
                "day_change_perc": resp.get("day_change_perc", 0),
                "bid_price": resp.get("bid_price", 0),
                "offer_price": resp.get("offer_price", 0),
                "week_52_high": resp.get("week_52_high", 0),
                "week_52_low": resp.get("week_52_low", 0),
                "open_interest": resp.get("open_interest", 0),
                "depth": resp.get("depth", {}),
                "upper_circuit": resp.get("upper_circuit_limit", 0),
                "lower_circuit": resp.get("lower_circuit_limit", 0),
            },
        )

        await self._events.emit(
            "market:quote",
            symbol=quote.symbol,
            price=quote.price,
            volume=quote.volume,
            timestamp=quote.timestamp,
            exchange=quote.exchange,
            ohlc=resp.get("ohlc", {}),
            extra=quote.extra,
        )

        return quote

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        await self._rate_limits.live_data.acquire()

        exchange_symbols = []
        for sym in symbols:
            info = self._instruments.by_symbol(sym)
            if info:
                exchange_symbols.append(f"{info.exchange}_{info.trading_symbol}")

        if not exchange_symbols:
            return []

        quotes = []
        for i in range(0, len(exchange_symbols), 50):
            batch = tuple(exchange_symbols[i : i + 50])
            if i > 0:
                await self._rate_limits.live_data.acquire()

            resp = self._api.get_ltp(
                segment=GrowwAPI.SEGMENT_CASH,
                exchange_trading_symbols=batch,
            )

            now = datetime.now()
            for key, price in resp.items():
                sym = key.split("_", 1)[1] if "_" in key else key
                quotes.append(Quote(
                    symbol=sym,
                    price=float(price),
                    volume=0,
                    timestamp=now,
                    exchange="NSE",
                ))

        return quotes

    async def get_historical(
        self, symbol: str, interval: str, from_date: str, to_date: str
    ) -> list[dict]:
        info = self._instruments.by_symbol(symbol)
        if not info:
            raise ValueError(f"Unknown symbol: {symbol}")

        interval_minutes = self._parse_interval(interval)
        max_days = INTERVAL_MAX_DAYS.get(interval_minutes, 30)

        start = self._parse_date(from_date)
        end = self._parse_date(to_date)

        all_candles = []
        chunk_start = start

        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=max_days), end)

            await self._rate_limits.live_data.acquire()
            resp = self._api.get_historical_candle_data(
                trading_symbol=info.trading_symbol,
                exchange=info.exchange,
                segment=info.segment,
                start_time=chunk_start.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=chunk_end.strftime("%Y-%m-%d %H:%M:%S"),
                interval_in_minutes=interval_minutes,
            )

            candles = resp.get("candles", [])
            for c in candles:
                all_candles.append({
                    "timestamp": c[0],
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5],
                })

            chunk_start = chunk_end

        await self._events.emit(
            "market:historical",
            symbol=symbol,
            interval=interval,
            candles=all_candles,
        )

        return all_candles

    async def get_holdings(self) -> list[dict]:
        await self._rate_limits.non_trading.acquire()
        resp = self._api.get_holdings_for_user()
        holdings = resp.get("holdings", [])

        await self._events.emit("portfolio:holdings", holdings=holdings)
        return holdings

    async def get_positions(self) -> list[Position]:
        await self._rate_limits.non_trading.acquire()
        resp = self._api.get_positions_for_user()

        positions = []
        for p in resp.get("positions", []):
            credit_qty = int(p.get("credit_quantity", 0))
            debit_qty = int(p.get("debit_quantity", 0))
            positions.append(Position(
                symbol=p.get("trading_symbol", ""),
                quantity=credit_qty - debit_qty,
                average_price=float(p.get("net_price", 0)),
                pnl=float(p.get("realised_pnl", 0)),
                product=p.get("product", ""),
                exchange=p.get("exchange", ""),
            ))

        await self._events.emit("portfolio:positions", positions=positions)
        return positions

    # ── Execution methods ──

    async def place_order(self, order: Order) -> str:
        await self._rate_limits.orders.acquire()

        resp = self._api.place_order(
            trading_symbol=order.symbol,
            quantity=order.quantity,
            validity=GrowwAPI.VALIDITY_DAY,
            exchange=order.exchange,
            segment=GrowwAPI.SEGMENT_CASH,
            product=GrowwAPI.PRODUCT_CNC,
            order_type=GrowwAPI.ORDER_TYPE_LIMIT if order.price else "MARKET",
            transaction_type=order.side,
            price=order.price or 0,
            trigger_price=order.trigger_price or 0,
        )

        order_id = str(resp.get("growwOrderId", resp.get("order_id", "")))
        log.info(f"order placed: {order_id}", extra={"symbol": order.symbol})
        return order_id

    async def cancel_order(self, order_id: str) -> bool:
        await self._rate_limits.orders.acquire()
        raise NotImplementedError("cancel_order not yet implemented for Groww")

    async def get_orders(self) -> list[dict]:
        await self._rate_limits.non_trading.acquire()
        raise NotImplementedError("get_orders not yet implemented for Groww")

    # ── WebSocket streaming ──

    async def subscribe(self, symbols: list[str]) -> None:
        if BrokerRole.DATA not in self.role:
            raise RuntimeError("Broker role must include DATA for streaming.")

        if not self._feed:
            self._feed = await asyncio.to_thread(GrowwFeed, self._api)

        instruments = []
        for sym in symbols:
            info = self._instruments.by_symbol(sym)
            if info:
                instruments.append({
                    "exchange": info.exchange,
                    "segment": info.segment,
                    "exchange_token": info.exchange_token,
                })
                self._subscriptions.add(sym)

        if not instruments:
            return

        self._feed.subscribe_ltp(instruments, on_data_received=self._on_ltp_data)

        if self._feed_task is None or self._feed_task.done():
            self._feed_task = asyncio.create_task(
                asyncio.to_thread(self._feed.consume)
            )

    async def unsubscribe(self, symbols: list[str]) -> None:
        if not self._feed:
            return

        instruments = []
        for sym in symbols:
            info = self._instruments.by_symbol(sym)
            if info:
                instruments.append({
                    "exchange": info.exchange,
                    "segment": info.segment,
                    "exchange_token": info.exchange_token,
                })
                self._subscriptions.discard(sym)

        if instruments:
            self._feed.unsubscribe_ltp(instruments)

    def _on_ltp_data(self, meta: dict) -> None:
        """Callback from GrowwFeed (runs in feed thread). Bridge to EventBus."""
        ltp_data = self._feed.get_ltp() if self._feed else {}

        for exchange, segments in ltp_data.get("ltp", {}).items():
            for segment, tokens in segments.items():
                for token, tick in tokens.items():
                    info = self._instruments.by_token(token, exchange, segment)
                    symbol = info.trading_symbol if info else token

                    self._events.emit_nowait(
                        "market:tick",
                        symbol=symbol,
                        price=float(tick.get("ltp", 0)),
                        timestamp=datetime.fromtimestamp(
                            tick.get("tsInMillis", 0) / 1000
                        ),
                    )

    # ── Helpers ──

    @staticmethod
    def _parse_interval(interval: str) -> int:
        mapping = {
            "1m": 1, "5m": 5, "10m": 10, "1h": 60, "4h": 240,
            "1d": 1440, "1w": 10080,
            "minute": 1, "5minute": 5, "10minute": 10, "hour": 60,
            "day": 1440, "week": 10080,
        }
        if interval in mapping:
            return mapping[interval]
        try:
            return int(interval)
        except ValueError:
            raise ValueError(f"Unknown interval: {interval}")

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")

    @property
    def instruments(self) -> InstrumentMap:
        return self._instruments
