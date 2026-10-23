"""mgdvault: zero-setup secret storage for Python projects.

Set ``MGDVAULT_PASSWORD`` and start calling :func:`get` and :func:`set`.
Secrets land in an encrypted KeePass database in your user data directory
that every application on the machine can share. Switch to the OS keyring
with ``MGDVAULT_BACKEND=keyring``, or build vaults explicitly with the
classes below.

Example:
    >>> import mgdvault
    >>> mgdvault.set("myapp/api_key", "sk-...")
    >>> mgdvault.get("myapp/api_key")
    'sk-...'
"""

from mgdvault.api import (
    default_vault,
    delete,
    exists,
    get,
    get_json,
    list_keys,
    reset_default_vault,
    set,
    set_default_vault,
    set_json,
    update,
    vault_from_env,
)
from mgdvault.backends import EnvVault, KeePassVault, KeyringVault, MemoryVault
from mgdvault.base import MISSING, Vault
from mgdvault.exceptions import (
    BackendUnavailableError,
    InvalidKeyError,
    MgdvaultError,
    ReadOnlyVaultError,
    SecretNotFoundError,
    VaultConfigurationError,
    VaultCredentialsError,
    VaultLockTimeoutError,
    VaultStorageError,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # functional API
    "get",
    "set",
    "delete",
    "exists",
    "list_keys",
    "get_json",
    "set_json",
    "update",
    "default_vault",
    "set_default_vault",
    "reset_default_vault",
    "vault_from_env",
    # classes
    "Vault",
    "KeePassVault",
    "KeyringVault",
    "EnvVault",
    "MemoryVault",
    "MISSING",
    # errors
    "MgdvaultError",
    "VaultConfigurationError",
    "VaultCredentialsError",
    "BackendUnavailableError",
    "InvalidKeyError",
    "SecretNotFoundError",
    "ReadOnlyVaultError",
    "VaultStorageError",
    "VaultLockTimeoutError",
]
