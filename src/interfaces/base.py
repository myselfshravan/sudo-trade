from typing import Protocol, runtime_checkable


@runtime_checkable
class Interface(Protocol):
    """Interface plugin. How the outside world talks to sudo-trade.

    Could be a CLI, an API server, a websocket, an OS-level agent —
    the engine doesn't care. Each interface wraps the engine and exposes
    it in whatever way makes sense.
    """
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
