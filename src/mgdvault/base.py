"""The abstract :class:`Vault` interface shared by every backend.

Backends implement four private primitives (``_get``, ``_set``, ``_delete``
and ``_list``). The public methods on :class:`Vault` add key validation,
``default`` handling, JSON helpers and consistent error types on top.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterator

from mgdvault.exceptions import SecretNotFoundError
from mgdvault.keys import matches_prefix, validate_key


class _Missing:
    """Sentinel type for "no default supplied"."""

    def __repr__(self) -> str:
        return "<MISSING>"


MISSING: Any = _Missing()
"""Sentinel meaning "no default was passed"."""


class Vault(ABC):
    """Abstract secret store mapping string keys to string values.

    Keys are slash-separated paths such as ``mgdio/google/personal``; see
    :mod:`mgdvault.keys` for the rules. Values are always ``str``. Use
    :meth:`set_json` / :meth:`get_json` for structured payloads such as
    OAuth token bundles.

    Subclasses must implement :meth:`_get`, :meth:`_set`, :meth:`_delete`
    and :meth:`_list`, and should set :attr:`backend_name`.
    """

    backend_name: str = "abstract"
    """Short identifier of the backend, e.g. ``"keepass"``."""

    read_only: bool = False
    """True when :meth:`set` and :meth:`delete` are not supported."""

    # -- primitives -------------------------------------------------------

    @abstractmethod
    def _get(self, key: str) -> str | None:
        """Return the value stored at ``key`` or ``None`` if absent."""

    @abstractmethod
    def _set(self, key: str, value: str) -> None:
        """Store ``value`` at ``key``, replacing any existing value."""

    @abstractmethod
    def _delete(self, key: str) -> bool:
        """Remove ``key``. Return True if it existed."""

    @abstractmethod
    def _list(self) -> list[str]:
        """Return every key in the vault (unordered)."""

    # -- public API -------------------------------------------------------

    def get(self, key: str, default: Any = MISSING) -> Any:
        """Return the secret stored at ``key``.

        Args:
            key: The secret key.
            default: Value to return when the key is absent. When omitted a
                missing key raises instead of returning ``None``, because a
                silently missing credential is usually a bug.

        Returns:
            The stored string, or ``default`` if the key is absent and a
            default was given.

        Raises:
            SecretNotFoundError: If the key is absent and no default given.
            InvalidKeyError: If the key violates the naming rules.
        """
        validate_key(key)
        value = self._get(key)
        if value is None:
            if default is MISSING:
                raise SecretNotFoundError(key, self.describe_location())
            return default
        return value

    def set(self, key: str, value: str) -> None:
        """Store ``value`` at ``key``, overwriting any existing value.

        Args:
            key: The secret key.
            value: The secret. Must be a ``str``; use :meth:`set_json` for
                structured data.

        Raises:
            TypeError: If ``value`` is not a ``str``.
            InvalidKeyError: If the key violates the naming rules.
            ReadOnlyVaultError: If the backend does not support writes.
        """
        validate_key(key)
        if not isinstance(value, str):
            raise TypeError(
                f"Secret values must be str, got {type(value).__name__}. "
                "Use set_json() for structured data."
            )
        self._set(key, value)

    def delete(self, key: str, missing_ok: bool = True) -> bool:
        """Remove the secret at ``key``.

        Args:
            key: The secret key.
            missing_ok: When False, raise if the key does not exist.

        Returns:
            True if a secret was removed, False if there was none.

        Raises:
            SecretNotFoundError: If ``missing_ok`` is False and no such key.
            ReadOnlyVaultError: If the backend does not support writes.
        """
        validate_key(key)
        removed = self._delete(key)
        if not removed and not missing_ok:
            raise SecretNotFoundError(key, self.describe_location())
        return removed

    def update(self, key: str, fn: Callable[[str | None], str | None]) -> str | None:
        """Atomically read, transform and write back the secret at ``key``.

        ``fn`` receives the current value (``None`` if absent) and returns
        the new value. Returning ``None`` deletes the key; returning the
        current value unchanged performs no write. Backends with shared
        storage hold their write lock for the whole operation, so this is
        the correct way to refresh an OAuth token bundle that several
        processes might refresh concurrently. A plain ``get`` followed by
        ``set`` is a race.

        Args:
            key: The secret key.
            fn: Callback mapping the current value to the new one.

        Returns:
            The value now stored, or ``None`` if the key was deleted or absent.

        Raises:
            TypeError: If ``fn`` returns something other than ``str``/``None``.
            ReadOnlyVaultError: If the backend does not support writes.
        """
        validate_key(key)
        return self._update(key, fn)

    def _update(self, key: str, fn: Callable[[str | None], str | None]) -> str | None:
        """Default read-modify-write; backends with locks override this."""
        current = self._get(key)
        new = fn(current)
        if new is None:
            if current is not None:
                self._delete(key)
            return None
        if not isinstance(new, str):
            raise TypeError(
                f"update() callback must return str or None, got "
                f"{type(new).__name__}."
            )
        if new != current:
            self._set(key, new)
        return new

    def exists(self, key: str) -> bool:
        """Return whether a secret is stored at ``key``.

        Args:
            key: The secret key.

        Returns:
            True if the key exists.
        """
        validate_key(key)
        return self._get(key) is not None

    def list_keys(self, prefix: str | None = None) -> list[str]:
        """Return the sorted keys in the vault, optionally under a namespace.

        Args:
            prefix: Restrict results to this key and the keys below it, e.g.
                ``"mgdio"`` matches ``"mgdio/google/personal"``.

        Returns:
            Sorted list of matching keys.
        """
        if prefix:
            validate_key(prefix.rstrip("/"))
        return sorted(k for k in self._list() if matches_prefix(k, prefix))

    def get_json(self, key: str, default: Any = MISSING) -> Any:
        """Return the secret at ``key`` decoded from JSON.

        Convenient for token bundles such as Google OAuth credentials, which
        libraries typically serialise to JSON.

        Args:
            key: The secret key.
            default: Returned (undecoded) when the key is absent.

        Returns:
            The decoded JSON value, or ``default``.

        Raises:
            SecretNotFoundError: If the key is absent and no default given.
            json.JSONDecodeError: If the stored value is not valid JSON.
        """
        raw = self.get(key, default=MISSING if default is MISSING else None)
        if raw is None:
            return default
        return json.loads(raw)

    def set_json(self, key: str, value: Any) -> None:
        """Serialise ``value`` to JSON and store it at ``key``.

        Args:
            key: The secret key.
            value: Any JSON-serialisable object.
        """
        self.set(key, json.dumps(value, separators=(",", ":"), sort_keys=True))

    def describe_location(self) -> str:
        """Return a short, secret-free description of where data lives.

        Used in error messages and by the ``mgdvault info`` command.

        Returns:
            For example ``"KeePass database at /path/vault.kdbx"``.
        """
        return f"{self.backend_name} vault"

    def close(self) -> None:
        """Release any cached resources. Safe to call more than once."""

    def __contains__(self, key: object) -> bool:
        """Support ``key in vault``."""
        return isinstance(key, str) and self.exists(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the sorted keys."""
        return iter(self.list_keys())

    def __len__(self) -> int:
        """Return the number of secrets in the vault."""
        return len(self._list())

    def __repr__(self) -> str:
        """Return a secret-free representation."""
        return f"<{type(self).__name__} {self.describe_location()}>"
