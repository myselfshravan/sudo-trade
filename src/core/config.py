import os
from pathlib import Path
from typing import Any


class Config:
    """Configuration loader. Reads from environment, .env files, and overrides.

    Keeps it simple — just a dict with dot-notation access and env var loading.
    """

    def __init__(self, overrides: dict[str, Any] | None = None):
        self._data: dict[str, Any] = {}
        self._load_env_file()
        self._load_environ()
        if overrides:
            self._data.update(overrides)

    def _load_env_file(self, path: str = ".env") -> None:
        env_path = Path(path)
        if not env_path.exists():
            return
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                self._data[key.strip()] = value.strip()

    def _load_environ(self) -> None:
        for key, value in os.environ.items():
            if key.startswith("SUDO_TRADE_"):
                clean_key = key.removeprefix("SUDO_TRADE_")
                self._data[clean_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def require(self, key: str) -> Any:
        value = self._data.get(key)
        if value is None:
            raise ValueError(f"Required config key missing: {key}")
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def all(self) -> dict[str, Any]:
        return dict(self._data)
