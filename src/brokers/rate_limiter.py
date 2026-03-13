import asyncio
import time
from collections import deque


class RateLimiter:
    """Token-bucket rate limiter with per-second and per-minute limits."""

    def __init__(self, per_second: int, per_minute: int):
        self._per_second = per_second
        self._per_minute = per_minute
        self._second_window: deque[float] = deque()
        self._minute_window: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._cleanup(now)

                if (
                    len(self._second_window) < self._per_second
                    and len(self._minute_window) < self._per_minute
                ):
                    self._second_window.append(now)
                    self._minute_window.append(now)
                    return

            await asyncio.sleep(0.05)

    def _cleanup(self, now: float) -> None:
        while self._second_window and now - self._second_window[0] > 1.0:
            self._second_window.popleft()
        while self._minute_window and now - self._minute_window[0] > 60.0:
            self._minute_window.popleft()


class GrowwRateLimits:
    """Groww API rate limits grouped by type."""

    def __init__(self):
        self.orders = RateLimiter(per_second=15, per_minute=250)
        self.live_data = RateLimiter(per_second=10, per_minute=300)
        self.non_trading = RateLimiter(per_second=20, per_minute=500)
