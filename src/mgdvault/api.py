"""The default vault and the module-level convenience functions.

Most applications never instantiate a :class:`~mgdvault.base.Vault`. They
set a couple of environment variables and call :func:`get` / :func:`set`.
The default vault is built lazily from ``os.environ`` on first use, so the
application decides if and when a ``.env`` file is loaded.

Resolution rules (see :mod:`mgdvault.settings` for the variable names):

* ``MGDVAULT_BACKEND`` unset or ``keepass``: a
  :class:`~mgdvault.backends.KeePassVault` at ``MGDVAULT_PATH`` (default:
  the per-user data directory), unlocked by ``MGDVAULT_PASSWORD`` and/or
  ``MGDVAULT_KEYFILE``. The database is created if missing.
* ``keyring``: a :class:`~mgdvault.backends.KeyringVault` in the OS
  credential manager, service ``MGDVAULT_KEYRING_SERVICE`` or ``mgdvault``.
* ``env``: a read-only :class:`~mgdvault.backends.EnvVault`.
* ``memory``: an empty :class:`~mgdvault.backends.MemoryVault`.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Mapping

from mgdvault import settings
from mgdvault.backends import EnvVault, KeePassVault, KeyringVault, MemoryVault
from mgdvault.base import MISSING, Vault
from mgdvault.exceptions import VaultConfigurationError

_default: Vault | None = None
_default_lock = threading.RLock()


def vault_from_env(environ: Mapping[str, str] | None = None) -> Vault:
    """Build a vault from environment variables without caching it.

    Args:
        environ: Mapping to read; defaults to :data:`os.environ`.

    Returns:
        A new vault instance.

    Raises:
        VaultConfigurationError: If the configuration is incomplete or names
            an unknown backend.
    """
    env = os.environ if environ is None else environ
    backend = env.get(settings.ENV_BACKEND, settings.DEFAULT_BACKEND).strip().lower()

    if backend == "keepass":
        password = env.get(settings.ENV_PASSWORD) or None
        keyfile = env.get(settings.ENV_KEYFILE) or None
        if not password and not keyfile:
            raise VaultConfigurationError(
                f"{settings.ENV_PASSWORD} is not set. Export it (or put it in a "
                ".env file your application loads) to unlock the KeePass vault, "
                f"or set {settings.ENV_BACKEND}=keyring to use the OS credential "
                "manager instead."
            )
        path = env.get(settings.ENV_PATH) or settings.default_db_path()
        raw_timeout = env.get(settings.ENV_LOCK_TIMEOUT)
        try:
            lock_timeout = (
                float(raw_timeout) if raw_timeout else settings.DEFAULT_LOCK_TIMEOUT
            )
        except ValueError as exc:
            raise VaultConfigurationError(
                f"{settings.ENV_LOCK_TIMEOUT} must be a number of seconds, "
                f"got {raw_timeout!r}."
            ) from exc
        return KeePassVault(
            path, password=password, keyfile=keyfile, lock_timeout=lock_timeout
        )

    if backend == "keyring":
        service = env.get(settings.ENV_KEYRING_SERVICE) or (
            settings.DEFAULT_KEYRING_SERVICE
        )
        return KeyringVault(service=service)

    if backend == "env":
        return EnvVault(environ=env)

    if backend == "memory":
        return MemoryVault()

    raise VaultConfigurationError(
        f"Unknown {settings.ENV_BACKEND}={backend!r}. Expected one of: "
        + ", ".join(settings.BACKENDS)
        + "."
    )


def default_vault() -> Vault:
    """Return the process-wide default vault, creating it on first call.

    Returns:
        The default vault.

    Raises:
        VaultConfigurationError: If the environment does not describe a
            usable vault.
    """
    global _default
    with _default_lock:
        if _default is None:
            _default = vault_from_env()
        return _default


def set_default_vault(vault: Vault | None) -> None:
    """Replace the default vault used by the module-level functions.

    Pass an explicit vault to bypass environment resolution, for example a
    :class:`~mgdvault.backends.MemoryVault` in tests, or ``None`` to force
    re-resolution from the environment on next use.

    Args:
        vault: The vault to use, or ``None`` to reset.
    """
    global _default
    with _default_lock:
        if _default is not None and _default is not vault:
            _default.close()
        _default = vault


def reset_default_vault() -> None:
    """Forget the default vault so the environment is read again."""
    set_default_vault(None)


# -- functional API --------------------------------------------------------


def get(key: str, default: Any = MISSING) -> Any:
    """Return the secret at ``key`` from the default vault.

    Args:
        key: Secret key such as ``"mgdio/ynab/token"``.
        default: Returned when the key is absent; without it a missing key
            raises :class:`~mgdvault.exceptions.SecretNotFoundError`.

    Returns:
        The stored string, or ``default``.
    """
    return default_vault().get(key, default)


def set(key: str, value: str) -> None:  # noqa: A001 - intentional API name
    """Store ``value`` at ``key`` in the default vault.

    Args:
        key: Secret key.
        value: The secret string.
    """
    default_vault().set(key, value)


def delete(key: str, missing_ok: bool = True) -> bool:
    """Remove the secret at ``key`` from the default vault.

    Args:
        key: Secret key.
        missing_ok: When False, raise if the key is absent.

    Returns:
        True if a secret was removed.
    """
    return default_vault().delete(key, missing_ok=missing_ok)


def exists(key: str) -> bool:
    """Return whether ``key`` is stored in the default vault.

    Args:
        key: Secret key.

    Returns:
        True if present.
    """
    return default_vault().exists(key)


def list_keys(prefix: str | None = None) -> list[str]:
    """Return the sorted keys in the default vault, optionally under ``prefix``.

    Args:
        prefix: Namespace to restrict to, e.g. ``"mgdio"``.

    Returns:
        Sorted list of keys.
    """
    return default_vault().list_keys(prefix)


def get_json(key: str, default: Any = MISSING) -> Any:
    """Return the JSON-decoded secret at ``key`` from the default vault.

    Args:
        key: Secret key.
        default: Returned when the key is absent.

    Returns:
        The decoded value, or ``default``.
    """
    return default_vault().get_json(key, default)


def update(key: str, fn: Callable[[str | None], str | None]) -> str | None:
    """Atomically read-modify-write the secret at ``key`` in the default vault.

    See :meth:`mgdvault.Vault.update`. Use this, not ``get`` then ``set``,
    when several processes may refresh the same token::

        mgdvault.update("myapp/whoop/token", lambda cur: refresh(cur))

    Args:
        key: Secret key.
        fn: Maps the current value (``None`` if absent) to the new value;
            ``None`` deletes.

    Returns:
        The value now stored, or ``None``.
    """
    return default_vault().update(key, fn)


def set_json(key: str, value: Any) -> None:
    """Store ``value`` as JSON at ``key`` in the default vault.

    Args:
        key: Secret key.
        value: Any JSON-serialisable object.
    """
    default_vault().set_json(key, value)
