import asyncio
import signal

from src.core.config import Config
from src.core.events import EventBus
from src.core.registry import Plugin, PluginRegistry


class Engine:
    """The orchestrator. Manages plugin lifecycle and event flow.

    The engine doesn't know what plugins do — it just starts them,
    connects them via the event bus, and shuts them down cleanly.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.events = EventBus()
        self.registry = PluginRegistry()
        self._running = False

    def add(self, category: str, plugin: Plugin) -> "Engine":
        self.registry.register(category, plugin)
        return self

    async def start(self) -> None:
        self._running = True
        await self.events.emit("engine:starting")

        for category in self.registry.categories():
            for plugin in self.registry.get_all(category):
                await plugin.start()
                await self.events.emit("plugin:started", name=plugin.name, category=category)

        await self.events.emit("engine:started")

    async def stop(self) -> None:
        await self.events.emit("engine:stopping")

        for category in reversed(self.registry.categories()):
            for plugin in self.registry.get_all(category):
                await plugin.stop()
                await self.events.emit("plugin:stopped", name=plugin.name, category=category)

        self._running = False
        await self.events.emit("engine:stopped")

    async def run(self) -> None:
        """Start the engine and block until interrupted."""
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await self.start()
        await stop_event.wait()
        await self.stop()

    @property
    def is_running(self) -> bool:
        return self._running
