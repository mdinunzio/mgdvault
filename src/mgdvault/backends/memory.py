"""An in-process dictionary vault, mainly for tests."""

from __future__ import annotations

from typing import Mapping

from mgdvault.base import Vault


class MemoryVault(Vault):
    """Vault that keeps secrets in a plain dictionary.

    Nothing is persisted; the contents vanish with the process. Useful as a
    test double: ``mgdvault.set_default_vault(MemoryVault({...}))`` lets a
    test suite run without a database or OS keyring.

    Args:
        initial: Optional mapping of keys to values to seed the vault with.
    """

    backend_name = "memory"

    def __init__(self, initial: Mapping[str, str] | None = None) -> None:
        """Create the vault, optionally seeded with ``initial``."""
        self._data: dict[str, str] = {}
        if initial:
            for key, value in initial.items():
                self.set(key, value)

    def _get(self, key: str) -> str | None:
        return self._data.get(key)

    def _set(self, key: str, value: str) -> None:
        self._data[key] = value

    def _delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    def _list(self) -> list[str]:
        return list(self._data)

    def describe_location(self) -> str:
        """Return ``"in-memory vault"``."""
        return "in-memory vault"
