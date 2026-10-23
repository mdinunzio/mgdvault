# Configuration

All configuration is through environment variables, read lazily when the
default vault is first used. Just before that read, and at the start of every
CLI command, mgdvault loads the nearest `.env` at or above the working
directory **without overriding variables that are already set**.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MGDVAULT_BACKEND` | `keepass`, `keyring`, `env` or `memory` | `keepass` |
| `MGDVAULT_PASSWORD` | Master password for the KeePass database | required unless a key file is given |
| `MGDVAULT_KEYFILE` | Path to a KeePass key file, used alone or with the password | unset |
| `MGDVAULT_PATH` | Location of the `.kdbx` file | per-user data directory (see below) |
| `MGDVAULT_KEYRING_SERVICE` | Service name for the keyring backend | `mgdvault` |
| `MGDVAULT_LOCK_TIMEOUT` | Seconds to wait for another process's write lock before failing | `30` |
| `MGDVAULT_DOTENV` | Path of a `.env` file to load, or `0`/`false`/`off` to disable `.env` loading | nearest `.env` above the working directory |

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
its own vault, for instance in that project's `.env` (which mgdvault loads
automatically):

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

## `.env` loading

`uv run mgdvault ...`, `python script.py` and cron jobs do not load a
project's `.env` the way an application calling `python-dotenv` does. To keep
"it works in the app but not on the command line" from happening, mgdvault
does the loading itself:

- Search starts at the current working directory and walks up to the
  filesystem root; the first `.env` wins.
- Existing environment variables are never overridden (`override=False`).
- `MGDVAULT_DOTENV=/path/to/file` loads that file instead of searching.
- `MGDVAULT_DOTENV=0` disables loading, which test suites should set.
- Nothing happens at import time; loading is triggered by
  `mgdvault.default_vault()` (and therefore the module-level functions) and
  by the CLI. `mgdvault.load_env_file()` triggers it explicitly and returns
  the path loaded.
- `mgdvault info` prints which file, if any, was loaded.

Unattended jobs (cron, systemd, launchd) usually run outside the project
directory, so export `MGDVAULT_PASSWORD` in their environment.

## Resolution order

1. The nearest `.env` is loaded (unless disabled), filling in variables that
   are not already set.
2. `MGDVAULT_BACKEND` decides the backend (default `keepass`).
3. For `keepass`, `MGDVAULT_PASSWORD` and/or `MGDVAULT_KEYFILE` must be set,
   otherwise `VaultConfigurationError` is raised with instructions.
4. `MGDVAULT_PATH` overrides the file location.
5. The resulting vault is cached for the process. Call
   `mgdvault.reset_default_vault()` if the environment changes afterwards.
