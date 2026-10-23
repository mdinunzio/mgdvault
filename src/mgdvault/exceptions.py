"""Exception hierarchy for mgdvault.

Every error raised by this package derives from :class:`MgdvaultError`, so
callers can catch one type when they do not care about the specific cause.
"""

from __future__ import annotations


class MgdvaultError(Exception):
    """Base class for all mgdvault errors."""


class VaultConfigurationError(MgdvaultError):
    """The default vault could not be resolved from the environment.

    Raised, for example, when ``MGDVAULT_BACKEND`` names an unknown backend
    or when the KeePass backend is selected but neither ``MGDVAULT_PASSWORD``
    nor ``MGDVAULT_KEYFILE`` is set.
    """


class VaultCredentialsError(MgdvaultError):
    """The vault exists but could not be unlocked with the given credentials."""


class BackendUnavailableError(MgdvaultError):
    """The selected backend cannot be used on this machine.

    Typical cause: the keyring backend was requested on a headless Linux host
    that has no Secret Service daemon.
    """


class InvalidKeyError(MgdvaultError, ValueError):
    """A secret key does not satisfy the naming rules.

    See :func:`mgdvault.keys.validate_key` for the rules.
    """


class SecretNotFoundError(MgdvaultError, KeyError):
    """The requested secret does not exist in the vault.

    Attributes:
        key: The key that was requested.
    """

    def __init__(self, key: str, vault: str | None = None) -> None:
        """Build the error message.

        Args:
            key: The key that was requested.
            vault: Optional human-readable description of the vault searched.
        """
        self.key = key
        self.vault = vault
        where = f" in {vault}" if vault else ""
        super().__init__(f"No secret stored at {key!r}{where}.")

    def __str__(self) -> str:
        """Return the plain message instead of KeyError's quoted repr."""
        return self.args[0]


class ReadOnlyVaultError(MgdvaultError):
    """A write was attempted on a vault that only supports reads."""


class VaultStorageError(MgdvaultError):
    """The backend accepted the request but failed to persist or read it."""


class VaultLockTimeoutError(VaultStorageError):
    """Another process held the vault's write lock for too long.

    Raised instead of blocking forever so unattended jobs fail loudly.
    """
