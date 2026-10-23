# Quick start

## 1. Install

```bash
uv add mgdvault          # inside a project
# or
pip install mgdvault
```

For the CLI alone, without a project or Python environment of your own:

```bash
uv tool install mgdvault
```

## 2. Pick a master password

mgdvault needs a single password to unlock the vault. Export it in your shell
profile, your CI secrets, or a gitignored `.env` file that your application
loads:

```bash
export MGDVAULT_PASSWORD='a long passphrase you keep somewhere safe'
```

!!! note "mgdvault does not read `.env` files"
    Loading `.env` is the application's job (for example with
    [python-dotenv](https://pypi.org/project/python-dotenv/)). mgdvault only
    looks at `os.environ` at the moment it is first used.

That is all the configuration required. The database is created automatically
at the default location the first time you store something:

| OS | Default path |
| --- | --- |
| macOS | `~/Library/Application Support/mgdvault/vault.kdbx` |
| Windows | `%LOCALAPPDATA%\mgdvault\vault.kdbx` |
| Linux | `~/.local/share/mgdvault/vault.kdbx` |

## 3. Store a secret

From the terminal (you are prompted; the value never touches the command
line):

```bash
uv run mgdvault set myapp/openai/api_key
```

Or from Python:

```python
import mgdvault
mgdvault.set("myapp/openai/api_key", "sk-...")
```

## 4. Use it

```python
import mgdvault

api_key = mgdvault.get("myapp/openai/api_key")

# Missing keys raise SecretNotFoundError unless you pass a default
token = mgdvault.get("myapp/optional_token", default=None)

# Structured payloads (OAuth token bundles, service-account JSON)
mgdvault.set_json("myapp/google/oauth", creds_dict)
creds_dict = mgdvault.get_json("myapp/google/oauth")

# Atomic read-modify-write, safe across processes (token refresh)
mgdvault.update("myapp/google/oauth", lambda cur: refresh_if_expired(cur))

mgdvault.exists("myapp/openai/api_key")   # True
mgdvault.list_keys("myapp")               # ['myapp/google/oauth', 'myapp/openai/api_key']
mgdvault.delete("myapp/optional_token")
```

Check what is in effect at any time:

```bash
$ uv run mgdvault info
backend:   keepass
location:  KeePass database at /Users/you/Library/Application Support/mgdvault/vault.kdbx
file:      exists
secrets:   2
```

## 5. Optional: explicit vaults

The module-level functions use one default vault resolved from the
environment. When a program needs more than one store, build them directly:

```python
from mgdvault import KeePassVault, KeyringVault

project = KeePassVault("./.secrets/project.kdbx", password=pw)
os_store = KeyringVault()

project.set("deploy/token", "...")
os_store.get("legacy/token", default=None)
```

Every vault class shares the same methods, so code can accept any
`mgdvault.Vault`.

## 6. Optional: Claude Code skills

```bash
uv run mgdvault install-skill            # this project: ./.claude/skills/
mgdvault install-skill --global          # every project: ~/.claude/skills/
```

See [Claude Code skills](claude-code.md).
