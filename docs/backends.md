# Backends

Every backend implements the same `Vault` interface: `get`, `set`, `delete`,
`exists`, `list_keys`, `get_json`, `set_json`.

## KeePassVault (default)

```python
from mgdvault import KeePassVault
vault = KeePassVault("~/vault.kdbx", password="...", keyfile=None,
                     auto_create=True, cache=True)
```

- **Storage**: a standard KDBX 4 file (AES-256, Argon2 key derivation),
  readable by KeePassXC and other clients. Key segments become groups; the
  last segment is the entry title; the secret is the entry password.
- **Latency**: unlocking costs a few hundred milliseconds of key derivation.
  The vault keeps the unlocked database and the derived key in memory, checks
  the file's modification time before each operation, and re-reads with the
  cached key (about a millisecond) only when another process has written.
  Hot reads are effectively free.
- **Concurrency**: writes take an inter-process lock (`vault.kdbx.lock`) and
  re-read the file before modifying it, so several jobs can share a vault.
  Reads never lock (pykeepass saves via rename, so a reader sees a complete
  file). For read-modify-write, such as refreshing an OAuth token, use
  `vault.update(key, fn)`: it holds the lock across the callback. `get`
  followed by `set` is a race. A lock held longer than `lock_timeout`
  seconds raises `VaultLockTimeoutError` rather than hanging.
- **Auto-create**: with `auto_create=True` (default) a missing file is created
  on first use. Set it to `False` to require `mgdvault init`.
- **Key file**: pass `keyfile=` for a second factor, or use it alone.

## KeyringVault

```python
from mgdvault import KeyringVault
vault = KeyringVault(service="mgdvault")
```

- **Storage**: the OS credential manager via the `keyring` library: macOS
  Keychain, Windows Credential Manager, Linux Secret Service. One class covers
  all three.
- **Listing**: keyring has no portable list operation, so an index entry
  (`__mgdvault_index__`) under the same service tracks the stored keys.
- **Caveats**: unavailable on headless Linux without a Secret Service daemon
  (`BackendUnavailableError`). On macOS, rebuilding a virtualenv changes the
  binary that owns the Keychain items, which triggers permission prompts or
  write refusals; error messages include the `security` command that clears a
  stale item.

## EnvVault

```python
from mgdvault import EnvVault
vault = EnvVault(prefix="MGDVAULT_SECRET_")
```

Read-only. `myapp/openai/api_key` is read from
`MGDVAULT_SECRET_MYAPP__OPENAI__API_KEY` (`/` becomes `__`, `-` and `.`
become `_`, upper-cased). Useful when a CI system injects secrets as
variables and you want the same `mgdvault.get()` calls to work.

## MemoryVault

```python
from mgdvault import MemoryVault
vault = MemoryVault({"myapp/token": "test"})
```

A dictionary. Nothing persists. Intended for tests:

```python
@pytest.fixture(autouse=True)
def fake_vault():
    mgdvault.set_default_vault(MemoryVault({"myapp/token": "t"}))
    yield
    mgdvault.reset_default_vault()
```

## Writing your own

Subclass `mgdvault.Vault` and implement `_get`, `_set`, `_delete` and
`_list`. Key validation, defaults, JSON helpers and error types come from the
base class.
