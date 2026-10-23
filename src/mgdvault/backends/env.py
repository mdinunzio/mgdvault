"""A read-only vault backed by environment variables.

Handy in CI, containers and other places where secrets are injected as
environment variables and no file or OS keyring is desirable.
"""

from __future__ import annotations

import os
from typing import Mapping, MutableMapping

from mgdvault.base import Vault
from mgdvault.exceptions import ReadOnlyVaultError
from mgdvault.settings import ENV_SECRET_PREFIX


def key_to_env_var(key: str, prefix: str = ENV_SECRET_PREFIX) -> str:
    """Translate a secret key into the environment variable that holds it.

    ``/`` becomes ``__`` and ``-`` / ``.`` become ``_``; the result is
    upper-cased and prefixed. ``mgdio/google/personal`` therefore maps to
    ``MGDVAULT_SECRET_MGDIO__GOOGLE__PERSONAL``.

    Args:
        key: A secret key.
        prefix: The variable prefix.

    Returns:
        The environment variable name.
    """
    body = key.replace("/", "__").replace("-", "_").replace(".", "_").upper()
    return f"{prefix}{body}"


def env_var_to_key(name: str, prefix: str = ENV_SECRET_PREFIX) -> str:
    """Best-effort inverse of :func:`key_to_env_var`.

    The mapping is lossy (``-`` and ``.`` are indistinguishable from ``_``
    after translation), so listing keys from an :class:`EnvVault` returns
    lower-case keys with underscores.

    Args:
        name: An environment variable name starting with ``prefix``.
        prefix: The variable prefix.

    Returns:
        The reconstructed key.
    """
    return name[len(prefix) :].lower().replace("__", "/")


class EnvVault(Vault):
    """Read-only vault that resolves secrets from environment variables.

    Args:
        prefix: Variable prefix, default ``MGDVAULT_SECRET_``.
        environ: Mapping to read from; defaults to :data:`os.environ`.
    """

    backend_name = "env"
    read_only = True

    def __init__(
        self,
        prefix: str = ENV_SECRET_PREFIX,
        environ: Mapping[str, str] | MutableMapping[str, str] | None = None,
    ) -> None:
        """Create the vault."""
        self.prefix = prefix
        self._environ = environ if environ is not None else os.environ

    def _get(self, key: str) -> str | None:
        return self._environ.get(key_to_env_var(key, self.prefix))

    def _set(self, key: str, value: str) -> None:
        raise ReadOnlyVaultError(
            f"EnvVault is read-only; export {key_to_env_var(key, self.prefix)} "
            "in the environment instead."
        )

    def _delete(self, key: str) -> bool:
        raise ReadOnlyVaultError("EnvVault is read-only.")

    def _list(self) -> list[str]:
        return [
            env_var_to_key(name, self.prefix)
            for name in self._environ
            if name.startswith(self.prefix) and len(name) > len(self.prefix)
        ]

    def describe_location(self) -> str:
        """Describe the variable prefix being read."""
        return f"environment variables prefixed {self.prefix!r}"
