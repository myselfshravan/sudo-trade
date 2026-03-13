import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine


EventHandler = Callable[..., Coroutine[Any, Any, Any]]


class EventBus:
    """Async event bus for decoupled plugin communication.

    Plugins emit and listen to events without knowing about each other.
    The engine wires everything together.
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[tuple[str, dict[str, Any]]] = []

    def on(self, event: str, handler: EventHandler) -> None:
        self._handlers[event].append(handler)

    def off(self, event: str, handler: EventHandler) -> None:
        self._handlers[event].remove(handler)

    async def emit(self, event: str, **data: Any) -> list[Any]:
        self._history.append((event, data))
        tasks = [handler(**data) for handler in self._handlers.get(event, [])]
        if not tasks:
            return []
        return await asyncio.gather(*tasks, return_exceptions=True)

    def emit_nowait(self, event: str, **data: Any) -> None:
        """Schedule emit from sync context (e.g., WebSocket callbacks)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event, **data))
        except RuntimeError:
            pass

    def listeners(self, event: str) -> list[EventHandler]:
        return list(self._handlers.get(event, []))

    @property
    def history(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._history)
