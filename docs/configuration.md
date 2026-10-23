# Configuration

All configuration is through environment variables, read lazily when the
default vault is first used. mgdvault never loads `.env` itself.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MGDVAULT_BACKEND` | `keepass`, `keyring`, `env` or `memory` | `keepass` |
| `MGDVAULT_PASSWORD` | Master password for the KeePass database | required unless a key file is given |
| `MGDVAULT_KEYFILE` | Path to a KeePass key file, used alone or with the password | unset |
| `MGDVAULT_PATH` | Location of the `.kdbx` file | per-user data directory (see below) |
| `MGDVAULT_KEYRING_SERVICE` | Service name for the keyring backend | `mgdvault` |
| `MGDVAULT_LOCK_TIMEOUT` | Seconds to wait for another process's write lock before failing | `30` |

## Default database location

Resolved with [platformdirs](https://pypi.org/project/platformdirs/):

| OS | Path |
| --- | --- |
| macOS | `~/Library/Application Support/mgdvault/vault.kdbx` |
| Windows | `%LOCALAPPDATA%\mgdvault\vault.kdbx` |
| Linux | `$XDG_DATA_HOME/mgdvault/vault.kdbx`, normally `~/.local/share/mgdvault/vault.kdbx` |

The directory is created with mode `700` and the file with mode `600` where
the filesystem supports it.

## Per-project vaults

Point `MGDVAULT_PATH` at a file inside the repository to give one project
its own vault, for instance in that project's `.env`:

```bash
MGDVAULT_PATH=./.secrets/vault.kdbx
MGDVAULT_PASSWORD=...
```

The `.kdbx` file is encrypted, so committing it is reasonable as long as the
password stays out of the repository (keep `.env` gitignored). This is the
simplest way to make secrets available in a cloud or CI environment: ship the
file, inject the password.

## Switching to the OS keyring

```bash
MGDVAULT_BACKEND=keyring
```

Secrets then go to macOS Keychain, Windows Credential Manager or Linux
Secret Service. Keys are stored under service `mgdvault` (or
`MGDVAULT_KEYRING_SERVICE`) with the key as the account name. See
[Backends](backends.md) for trade-offs.

## Programmatic control

```python
import mgdvault
from mgdvault import KeePassVault, MemoryVault

# Replace the default vault for this process (e.g. in tests)
mgdvault.set_default_vault(MemoryVault({"myapp/token": "test"}))

# Go back to environment-based resolution
mgdvault.reset_default_vault()

# Build a vault from an arbitrary mapping instead of os.environ
vault = mgdvault.vault_from_env({"MGDVAULT_BACKEND": "memory"})
```

## Resolution order

1. `MGDVAULT_BACKEND` decides the backend (default `keepass`).
2. For `keepass`, `MGDVAULT_PASSWORD` and/or `MGDVAULT_KEYFILE` must be set,
   otherwise `VaultConfigurationError` is raised with instructions.
3. `MGDVAULT_PATH` overrides the file location.
4. The resulting vault is cached for the process. Call
   `mgdvault.reset_default_vault()` if the environment changes afterwards.
