# Secret store: generalizing beyond the OS keyring

**Status:** deferred design note (2026-09-25). Not implemented. Superseded in
part by [mgd-vault-spec.md](mgd-vault-spec.md) (2026-10-22), which moves the
file backend into a separate `mgd-vault` package; the `secrets` seam, the
env-as-seed rule, and the Whoop rotation caveat here still apply.

## Why this note exists

mgdio stores every credential in the OS keyring (`keyring` package). That is
the right default on macOS (Keychain) and Windows (Credential Manager), and
it works on Linux desktops with a Secret Service daemon. It is a poor fit for:

- **Claude Code cloud sessions** (and CI generally): no keyring, no
  persistent home directory you set up by hand. The only reliable way to
  inject a secret is an environment variable.
- **Headless Linux (the Oracle VPS)**: no Secret Service, so
  `mgdio/keyring_backend.py` probes at import time and falls back to a
  `keyrings.alt` plaintext file. That file is an INI with base64 values,
  awkward to inspect or seed by hand, and pulls in `pycryptodomex`.

## Triggers for actually building this

1. You want to run mgdio inside a Claude Code cloud session or other CI-like
   environment. The env-var seed backend below is the whole ask.
2. Credentials "disappear" on the VPS between an interactive shell and a
   systemd/Airflow-launched process (see the hypothesis below).
3. You need to move a full set of tokens from one machine to another and
   re-running every `mgdio auth ...` flow is too painful.

## Current state (as of v0.5.0)

- Reads: direct `keyring.get_password` calls in `auth/google/auth.py`,
  `auth/google/_profiles.py`, `auth/ynab/auth.py`, `auth/maps/auth.py`,
  `auth/whoop/auth.py`, `auth/whoop/_setup_server.py`, `auth/status.py`.
- Writes/deletes: `mgdio/auth/_keyring.py` (`set_password`,
  `delete_password`, `ensure_writable`) with macOS stale-ACL recovery via the
  `security` CLI.
- Backend selection: `mgdio/keyring_backend.py`, called once from
  `mgdio/settings.py` at import. Explicit `MGDIO_KEYRING_BACKEND` /
  `PYTHON_KEYRING_BACKEND` wins; otherwise Linux probes Secret Service and
  falls back to `keyrings.alt` under `~/.local/share/mgdio/keyring/`.
- Tests: `tests/conftest.py` monkeypatches a fake `keyring` module into four
  auth modules separately.

## Hypothesis for the VPS "weird results"

Backend selection is per process and depends on whether a D-Bus session bus
is reachable when the probe runs. An interactive SSH shell (with
`DBUS_SESSION_BUS_ADDRESS` set by a login session) and a systemd-launched
Airflow task (without it) can resolve to different backends. A token written
by `mgdio auth` in the shell then looks missing from the task, or vice versa.

Unconfirmed. Cheapest diagnostic: make `mgdio auth status` print the active
backend class and, for file backends, the file path. Run it from both a
shell and `systemd-run --uid ubuntu ...` and compare. Cheapest fix without
any redesign: pin the backend in the systemd `secrets.env` so both contexts
resolve identically.

## What DataGrip does (for reference)

JetBrains IDEs offer three password-store modes: native keychain, a KeePass
file (`c.kdbx` in the config dir, protected by a master password), or don't
save. The KeePass mode is a file vault that needs its master password every
launch. It has the same shape as `keyrings.alt`'s `EncryptedKeyring` and the
same problem for cron and cloud: the master password has to come from an
env var sitting next to the vault, which is barely better than a chmod 600
plaintext file. Not worth adopting as a primary backend.

## Proposed design

One functional module, `mgdio/secrets.py`, with:

```python
get(service: str, username: str) -> str | None
set(service: str, username: str, value: str) -> None
delete(service: str, username: str) -> None
where(service: str, username: str) -> str   # backend name holding it
```

keyed by the existing `(service, username)` pairs (`mgdio:google:<slug>` /
`oauth_token`, `mgdio:ynab` / `personal_access_token`, ...). Every provider
calls this instead of `keyring` or `_keyring`.

### Backends

Selected by `MGDIO_SECRETS_BACKEND=auto|env|keyring|file`. Default `auto`.

1. **`env`**: reads `MGDIO_SECRET_<SERVICE>_<USERNAME>` with the service
   prefix `mgdio:` dropped, colons and dashes mapped to underscores, upper
   case. Examples:
   - `MGDIO_SECRET_GOOGLE_MDINUNZIOSVC_OAUTH_TOKEN`
   - `MGDIO_SECRET_YNAB_PERSONAL_ACCESS_TOKEN`
   - `MGDIO_SECRET_WHOOP_OAUTH_TOKEN`, `MGDIO_SECRET_WHOOP_APP_CREDENTIALS`
   Sourced from the process environment and `.env` (dotenv already loads in
   `settings.py`). Read-only.
2. **`keyring`**: today's behavior, including the macOS recovery in
   `_keyring.py`.
3. **`file`**: plain JSON at `<user_data_dir>/mgdio/secrets.json`, chmod 600
   inside a chmod 700 dir, written atomically (temp file + rename). Human
   readable, hand-editable, scp-able. Replaces `keyrings.alt` and the two
   Linux-only dependencies in `pyproject.toml`.

`auto` = env overlay on top of (keyring if the probe passes, else file).

### Env is a seed, not a store (the non-obvious rule)

**Whoop rotates its refresh token on every refresh** and invalidates the old
one (see `mgd-data-sync/scratch/whoop-one-active-grant.md`). A read-only env
backend therefore breaks Whoop after the first refresh: the new token cannot
be persisted, and the next process presents a dead one. Google refresh tokens
do not rotate; YNAB and Maps keys are static, so those work from env alone.

Rule: a value first found in env is copied into the writable backend
(keyring or file) on first read. Subsequent reads prefer the writable backend
when it has a value. Env bootstraps a fresh machine and then gets out of the
way. In an ephemeral cloud home the file backend still lives for the session,
so Whoop keeps working there too.

`set` with `MGDIO_SECRETS_BACKEND=env` forced raises a clear error telling
the user which variable to set.

### CLI additions

- `mgdio secrets export --format env` prints `MGDIO_SECRET_*=...` lines for
  whatever this machine holds. Run on the Mac, paste into a cloud
  environment's variable config or a `.env`. One-time export is enough for
  Google because its refresh tokens are long-lived.
- `mgdio auth status` gains a column showing which backend holds each secret
  (from `where`).

### Migration

- Replace the direct `keyring.get_password` reads and `_keyring` write
  helpers with `secrets.get/set/delete`. Provider logic is otherwise
  untouched.
- Collapse the four `fake_keyring` monkeypatches in `tests/conftest.py` into
  one in-memory secrets backend.
- On first run with the `file` backend, if the legacy
  `~/.local/share/mgdio/keyring/mgdio_plaintext.cfg` exists, read it once,
  copy entries into `secrets.json`, log a line, and leave the old file.
- Drop `keyrings.alt` and `pycryptodomex` from `pyproject.toml`.

### Explicitly deferred

Encrypted file storage with a key from `MGDIO_SECRETS_KEY` (Fernet via
`cryptography`). Only worth it if a threat model appears where the vault
file and its key live in different places. Otherwise it is a chmod 600 file
protecting another chmod 600 file.

## Rough effort

About a day for the module, backends, migration, and tests. Half a day more
for the CLI additions and README updates.
