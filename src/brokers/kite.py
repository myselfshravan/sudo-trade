"""Kite Connect broker integration. Stub — implement when API keys are ready."""

from src.brokers.base import Broker, BrokerRole, Quote, Order, Position


class KiteBroker:
    name = "kite"

    def __init__(self, role: BrokerRole = BrokerRole.BOTH, **kwargs):
        self.role = role
        self._api_key = kwargs.get("api_key", "")
        self._api_secret = kwargs.get("api_secret", "")
        self._access_token = kwargs.get("access_token", "")
        self._client = None

    async def start(self) -> None:
        pass  # TODO: init KiteConnect client, validate session

    async def stop(self) -> None:
        pass

    async def get_quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        raise NotImplementedError

    async def get_historical(self, symbol: str, interval: str, from_date: str, to_date: str) -> list[dict]:
        raise NotImplementedError

    async def place_order(self, order: Order) -> str:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    async def get_orders(self) -> list[dict]:
        raise NotImplementedError

    async def get_positions(self) -> list[Position]:
        raise NotImplementedError

    async def get_holdings(self) -> list[dict]:
        raise NotImplementedError
