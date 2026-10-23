# mgdvault

**One environment variable, one encrypted file, every project on the machine.**

mgdvault stores API keys, passwords and OAuth tokens in a
[KeePass](https://keepass.info/) database that lives in your user data
directory and is shared by all your Python projects. Set `MGDVAULT_PASSWORD`
and start calling `mgdvault.get()`; nothing else to configure.

```python
import mgdvault

mgdvault.set("myapp/openai/api_key", "sk-...")
api_key = mgdvault.get("myapp/openai/api_key")
```

## Why not just use keyring?

OS credential managers are great until they are not:

- **Cloud and headless machines** (Claude Code on the web, CI runners, a VPS)
  have no Keychain or Credential Manager at all.
- **macOS re-prompts after every code change.** Keychain ties access to the
  binary that stored the item, so a rebuilt virtualenv means a cascade of
  permission dialogs. Unattended pipelines cannot click "Always Allow".

A KeePass file has neither problem: it is a portable encrypted file unlocked
by a password you control. The OS keyring is still available as an opt-in
backend (`MGDVAULT_BACKEND=keyring`) for people who prefer it.

## Features

- **Zero setup**: the database is created on first use.
- **Fast**: the unlock cost is paid once per process; reads are cached and
  refreshed only when another process changes the file.
- **Safe for concurrent jobs**: writes take a file lock and re-read before
  modifying.
- **Shared across apps**: slash-namespaced keys (`mgdio/google/personal`)
  let many packages use one vault without collisions.
- **Pluggable**: `KeePassVault`, `KeyringVault`, `EnvVault`, `MemoryVault`,
  all behind one `Vault` interface.
- **Claude Code ready**: bundled skills teach an agent how to check for and
  request secrets without ever printing them.
- **Interoperable**: open the same file in KeePassXC to inspect or edit it.

Continue with the [quick start](quickstart.md).
