"""Environment variable names and default paths.

Nothing in this module reads the environment at import time. The default
vault is resolved lazily by :func:`mgdvault.api.default_vault`, using
whatever is in ``os.environ`` at that moment. mgdvault never loads a
``.env`` file itself; that decision belongs to the application.
"""

from __future__ import annotations

from pathlib import Path

import platformdirs

APP_NAME = "mgdvault"
"""Application name used for the platform data directory."""

ENV_BACKEND = "MGDVAULT_BACKEND"
"""Selects the default backend: ``keepass`` (default), ``keyring``, ``env``
or ``memory``."""

ENV_PASSWORD = "MGDVAULT_PASSWORD"
"""Master password for the KeePass database."""

ENV_KEYFILE = "MGDVAULT_KEYFILE"
"""Optional path to a KeePass key file (used alone or with the password)."""

ENV_PATH = "MGDVAULT_PATH"
"""Overrides the location of the KeePass database file."""

ENV_KEYRING_SERVICE = "MGDVAULT_KEYRING_SERVICE"
"""Service name used by the keyring backend (default ``mgdvault``)."""

ENV_SECRET_PREFIX = "MGDVAULT_SECRET_"
"""Prefix of environment variables read by the ``env`` backend."""

ENV_LOCK_TIMEOUT = "MGDVAULT_LOCK_TIMEOUT"
"""Seconds to wait for the KeePass write lock before failing (default 30)."""

DEFAULT_LOCK_TIMEOUT = 30.0
"""Default write-lock timeout in seconds."""

DEFAULT_BACKEND = "keepass"
"""Backend used when ``MGDVAULT_BACKEND`` is unset."""

DEFAULT_KEYRING_SERVICE = "mgdvault"
"""Default keyring service name."""

DEFAULT_DB_FILENAME = "vault.kdbx"
"""File name of the default KeePass database."""

BACKENDS = ("keepass", "keyring", "env", "memory")
"""Names accepted by ``MGDVAULT_BACKEND``."""


def default_data_dir() -> Path:
    """Return the per-user data directory for mgdvault.

    Resolves to ``~/Library/Application Support/mgdvault`` on macOS,
    ``%LOCALAPPDATA%/mgdvault`` on Windows and ``~/.local/share/mgdvault``
    on Linux (honouring ``XDG_DATA_HOME``). The directory is not created.

    Returns:
        The data directory path.
    """
    return Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))


def default_db_path() -> Path:
    """Return the default KeePass database location.

    Returns:
        ``default_data_dir() / "vault.kdbx"``.
    """
    return default_data_dir() / DEFAULT_DB_FILENAME
