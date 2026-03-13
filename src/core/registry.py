from typing import Any, TypeVar, Protocol, runtime_checkable


T = TypeVar("T")


@runtime_checkable
class Plugin(Protocol):
    """Every plugin must have a name."""
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class PluginRegistry:
    """Central registry for all plugins. Plugins register by category.

    Categories: broker, provider, analyzer, llm, strategy, executor, interface
    Each category can hold multiple plugins (e.g., multiple brokers running simultaneously).
    """

    def __init__(self):
        self._plugins: dict[str, dict[str, Plugin]] = {}

    def register(self, category: str, plugin: Plugin) -> None:
        if category not in self._plugins:
            self._plugins[category] = {}
        self._plugins[category][plugin.name] = plugin

    def get(self, category: str, name: str) -> Plugin | None:
        return self._plugins.get(category, {}).get(name)

    def get_all(self, category: str) -> list[Plugin]:
        return list(self._plugins.get(category, {}).values())

    def categories(self) -> list[str]:
        return list(self._plugins.keys())

    def unregister(self, category: str, name: str) -> None:
        if category in self._plugins:
            self._plugins[category].pop(name, None)

    def summary(self) -> dict[str, list[str]]:
        return {
            category: list(plugins.keys())
            for category, plugins in self._plugins.items()
        }
