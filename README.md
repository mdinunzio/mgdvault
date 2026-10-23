# mgdvault

Zero-setup secret storage for Python projects. One environment variable
unlocks an encrypted [KeePass](https://keepass.info/) database shared by every
project on the machine; the OS keyring is available as an alternative backend.

```python
import mgdvault

mgdvault.set("myapp/openai/api_key", "sk-...")
api_key = mgdvault.get("myapp/openai/api_key")
```

## Why

OS credential managers do not exist on cloud or headless machines, and on
macOS every rebuilt virtualenv triggers a fresh round of Keychain permission
prompts. A KeePass file is portable, encrypted and unlocked by a password you
control, so it works the same way on a laptop, a VPS, in CI, or inside Claude
Code on the web.

## Install

```bash
uv add mgdvault            # in a project
uv tool install mgdvault   # just the CLI, globally
```

## Quick start

```bash
export MGDVAULT_PASSWORD='a long passphrase'   # or put it in the project's gitignored .env
uv run mgdvault set myapp/openai/api_key       # hidden prompt; database created automatically
uv run mgdvault info
```

```python
import mgdvault
mgdvault.get("myapp/openai/api_key")
mgdvault.get("myapp/optional", default=None)
mgdvault.set_json("myapp/google/oauth", creds_dict)
mgdvault.update("myapp/google/oauth", refresh_if_expired)  # locked read-modify-write
mgdvault.list_keys("myapp")
```

| Variable | Purpose | Default |
| --- | --- | --- |
| `MGDVAULT_PASSWORD` | Master password | required |
| `MGDVAULT_PATH` | Database location | `~/Library/Application Support/mgdvault/vault.kdbx` (macOS), `%LOCALAPPDATA%\mgdvault\vault.kdbx` (Windows), `~/.local/share/mgdvault/vault.kdbx` (Linux) |
| `MGDVAULT_BACKEND` | `keepass`, `keyring`, `env`, `memory` | `keepass` |
| `MGDVAULT_KEYFILE` | Optional KeePass key file | unset |
| `MGDVAULT_DOTENV` | `.env` to load, or `0` to disable | nearest `.env` above cwd |

mgdvault loads the nearest `.env` above the working directory when first used
and in every CLI command, without overriding variables that are already set.
Cron and systemd jobs should export the password instead.

## Claude Code skills

```bash
uv run mgdvault install-skill            # ./.claude/skills/
mgdvault install-skill --global          # ~/.claude/skills/
```

The bundled skills teach an agent to check for secrets with `exists`/`list`,
ask you to add missing ones via `mgdvault set`, and never print values into
the conversation.

## Examples

[examples/mgdvault_tour.ipynb](examples/mgdvault_tour.ipynb) is an executed
notebook that goes from the first secret to power-user features (atomic
`update`, concurrent writers, caching, alternative backends, KeePassXC
interoperability), all against a throwaway vault with made-up values.

## Documentation

Full docs (quick start, configuration, backends, CLI, API reference) are in
`docs/` and build with `uv run mkdocs serve`.

## Development

```bash
uv sync --extra dev --extra docs   # also installs the JupyterLab dev group
uv run pytest
uv run black src tests && uv run flake8 src tests
```

## License

MIT
