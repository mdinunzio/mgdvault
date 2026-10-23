"""A vault stored in the operating system credential manager.

Uses the `keyring <https://pypi.org/project/keyring/>`_ library, which
targets macOS Keychain, Windows Credential Manager and Linux Secret Service
(GNOME Keyring, KWallet). One class covers all three.

Each secret is a keyring entry with service ``mgdvault`` (configurable) and
the secret key as the username. Because keyring has no portable "list"
operation, an index of keys is kept in an extra entry named
``__mgdvault_index__`` under the same service.
"""

from __future__ import annotations

import json
import sys
import threading

import keyring
import keyring.errors

from mgdvault.base import Vault
from mgdvault.exceptions import BackendUnavailableError, VaultStorageError
from mgdvault.settings import DEFAULT_KEYRING_SERVICE

INDEX_USERNAME = "__mgdvault_index__"
"""Username of the keyring entry holding the JSON list of keys."""


def _backend_is_usable(backend: object) -> bool:
    """Return False for keyring's inert ``fail`` / ``null`` backends."""
    module = type(backend).__module__.lower()
    return not (module.endswith(".fail") or module.endswith(".null"))


class KeyringVault(Vault):
    """Vault that stores secrets in the OS credential manager via keyring.

    Args:
        service: Keyring service name; all entries share it. Defaults to
            ``"mgdvault"``.

    Raises:
        BackendUnavailableError: If keyring has no working backend (common on
            headless Linux without a Secret Service daemon).
    """

    backend_name = "keyring"

    def __init__(self, service: str = DEFAULT_KEYRING_SERVICE) -> None:
        """Create the vault and verify a keyring backend is available."""
        self.service = service
        self._lock = threading.RLock()
        try:
            backend = keyring.get_keyring()
        except Exception as exc:  # pragma: no cover - defensive
            raise BackendUnavailableError(f"keyring is not usable: {exc}") from exc
        if not _backend_is_usable(backend):
            raise BackendUnavailableError(
                "No OS keyring backend is available on this machine. Use the "
                "KeePass backend (unset MGDVAULT_BACKEND) or install a keyring "
                "backend such as a Secret Service daemon."
            )
        self.backend_description = (
            f"{type(backend).__module__}.{type(backend).__name__}"
        )

    # -- primitives -------------------------------------------------------

    def _get(self, key: str) -> str | None:
        try:
            return keyring.get_password(self.service, key)
        except keyring.errors.KeyringError as exc:
            raise VaultStorageError(
                f"keyring refused to read {key!r} from service {self.service!r}: {exc}"
            ) from exc

    def _set(self, key: str, value: str) -> None:
        with self._lock:
            self._write(key, value)
            index = self._read_index()
            if key not in index:
                index.append(key)
                self._write(INDEX_USERNAME, json.dumps(sorted(index)))

    def _delete(self, key: str) -> bool:
        with self._lock:
            existed = self._get(key) is not None
            if existed:
                try:
                    keyring.delete_password(self.service, key)
                except keyring.errors.PasswordDeleteError as exc:
                    raise VaultStorageError(
                        f"keyring refused to delete {key!r}: {exc}"
                        + self._manual_fix_hint(key)
                    ) from exc
            index = self._read_index()
            if key in index:
                index.remove(key)
                self._write(INDEX_USERNAME, json.dumps(sorted(index)))
            return existed

    def _list(self) -> list[str]:
        return self._read_index()

    # -- helpers ----------------------------------------------------------

    def _read_index(self) -> list[str]:
        raw = self._get(INDEX_USERNAME)
        if not raw:
            return []
        try:
            keys = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return [k for k in keys if isinstance(k, str)]

    def _write(self, username: str, value: str) -> None:
        try:
            keyring.set_password(self.service, username, value)
        except keyring.errors.PasswordSetError as exc:
            raise VaultStorageError(
                f"keyring refused to store {username!r} under service "
                f"{self.service!r}: {exc}" + self._manual_fix_hint(username)
            ) from exc

    def _manual_fix_hint(self, username: str) -> str:
        if sys.platform == "darwin":
            return (
                "\nOn macOS this usually means the Keychain item was created by a "
                "Python binary that no longer exists (e.g. a rebuilt .venv). "
                "Remove the stale item with:\n"
                f'  security delete-generic-password -s "{self.service}" '
                f'-a "{username}"'
            )
        return ""

    def describe_location(self) -> str:
        """Describe the keyring backend and service name."""
        return f"OS keyring ({self.backend_description}) service {self.service!r}"
