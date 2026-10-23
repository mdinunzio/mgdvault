# mgd-vault: design spec

**Status:** approved design, ready to build in a new repository (`mgd-vault`).
**Date:** 2026-10-22. **Author:** Michael DiNunzio, with Claude.

This document is self-contained. A fresh session should be able to build the
library from it without the conversation that produced it. Decisions below
are settled unless listed under *Open questions*; do not relitigate them.

---

## 1. Purpose

A single cross-platform secret store for all of the author's personal tools.
One encrypted KeePass (`.kdbx`) file per machine in a standard location, one
master password delivered through an environment variable, and a small Python
API plus CLI that every project (mgdio, mgd-data-sync, ad-hoc scripts, Claude
Code sessions) uses to read and write secrets.

It replaces the OS keyring as the default credential store for the author's
projects. It is not a password manager for humans; it is a programmatic store
that humans can also open in KeePassXC when they need to.

### Problems it solves

- **The OS keyring is not plug-and-play everywhere.** macOS Keychain and
  Windows Credential Manager work but macOS prompts to approve each binary that
  touches an item, and a rebuilt `.venv` invalidates the item's ACL. Headless
  Linux (the author's Oracle VPS) has no Secret Service daemon, so `keyring`
  needs a file fallback. Cloud sandboxes (Claude Code cloud sessions, CI) have
  no keyring at all.
- **Secrets are stuck on the machine that created them.** A Google OAuth token
  obtained on the Mac cannot be moved to the VPS without re-running the auth
  flow. A `.kdbx` file can be copied, synced, or opened in a GUI.
- **Every project reinvents credential loading.** `.env` files per project,
  keyring in one, plaintext JSON in another.

### Non-goals

- Not a security upgrade over a locked-down plaintext file *on the running
  machine*. With the master password in the environment, anything running as
  the user can read the vault. The encryption earns its keep when the file is
  at rest without the key: in a Drive sync, a backup, or in transit.
- Not an OAuth client. The vault never refreshes tokens. Refresh logic stays in
  the library that understands the protocol (mgdio). See §6.
- Not a multi-user or team store. No access control, no audit log.
- Not a KeePass GUI replacement. KeePassXC remains the tool for browsing.

---

## 2. Reference: how comparable projects do it

Surveyed 2026-10-21. Both agent frameworks below converged on plaintext
files locked to the user, with no OS keychain and no encryption at rest.

- **Hermes Agent** (Nous Research, Python): static API keys in
  `~/.hermes/.env`; OAuth state in `~/.hermes/auth.json`, written atomically
  with fsync, `0o600` file and `0o700` dir, cross-process lock via
  `fcntl.flock` / `msvcrt.locking` with a pid-stamped lock file and timeout.
  Rotating refresh tokens are written back to the exact store they were read
  from. A refresh that fails terminally is quarantined so it is not replayed.
- **OpenClaw** (TypeScript): live store is SQLite, documented as *not*
  encrypted at rest, relying on `0600`/`0700`. Config holds pointers
  (`{source: env|file|exec|store, provider, id}`) rather than values. The
  `exec` source shells out to an external manager (1Password, Bitwarden,
  Vault, `pass`, sops). OAuth profiles carry `expires`; refreshes write back to
  the owning store; copy flows skip refresh tokens because providers rotate
  them; a failed refresh flags re-auth instead of falling back.

Lessons adopted here: separate static from rotating secrets; lock plus atomic
`0600` write for concurrency; write back to where you read from; never copy a
rotating token between machines; treat stronger encryption as an external
manager's job and leave an exec-style escape hatch.

---

## 3. Primary consumer: mgdio

`mgdio` (github.com/mdinunzio/mgdio) is the author's connectivity package:
Gmail, Calendar, Sheets, Drive, Maps, YNAB, Whoop. Today it stores every
credential via the `keyring` package, with a `keyrings.alt` plaintext-file
fallback on Linux. Its planned `mgdio.secrets` seam (`get` / `set` / `delete` /
`where`, keyed by `(service, username)`) will route to mgd-vault as its
preferred backend, with `env` and `keyring` remaining as alternatives.

Entries mgdio will store, with their current keyring identifiers:

| Service              | Username               | Kind         | Payload                              |
|----------------------|------------------------|--------------|--------------------------------------|
| `mgdio:google:<slug>`| `oauth_token`          | oauth-bundle | google-auth `Credentials.to_json()`  |
| `mgdio:ynab`         | `personal_access_token`| static       | PAT string                           |
| `mgdio:maps`         | `api_key`              | static       | API key string                       |
| `mgdio:whoop`        | `app_credentials`      | static       | JSON `{client_id, client_secret}`    |
| `mgdio:whoop`        | `oauth_token`          | oauth-bundle | JSON token bundle, **rotating**      |

Key mapping from mgdio identifiers to vault keys: drop the `mgdio:` prefix,
replace `:` with `/`, append `/` + username. So `mgdio:google:mdinunziosvc` +
`oauth_token` becomes `google/mdinunziosvc/oauth_token`.

mgdio behaviours the vault must support:

- **Refresh write-back.** After google-auth or the Whoop client refreshes an
  access token, mgdio calls `set` with the new bundle. For Whoop this bundle
  contains a *new* refresh token and the old one is dead. Two mgdio processes
  refreshing concurrently must not clobber each other (§7).
- **`mgdio auth status`** reports which backend holds each secret. The vault
  exposes `where` / `exists` and a human-readable path for this.
- **`mgdio auth <provider> --reset`** deletes entries. `delete` must be silent
  on a missing key.
- **Multi-account Google profiles.** Keys are per-slug; `list("google/")`
  must enumerate them so mgdio can drop its on-disk `profiles.json` index.
- **Migration.** A one-shot `mgdio auth migrate --to vault` (built in mgdio,
  not here) reads each keyring entry and calls `set`. The vault needs no
  special support beyond `set`.

Other consumers: `mgd-data-sync` (Dexcom email/password, Anthropic API key,
GitHub token, currently in a systemd `EnvironmentFile`), and any Claude Code
cloud session that installs mgdio and receives `MGD_VAULT_PASSWORD` plus an
exported vault.

---

## 4. Storage

### File

- Format: KDBX 4 via `pykeepass` (>= 4.2). Pure Python with `argon2-cffi`
  and `pycryptodomex` wheels; installs cleanly in cloud sandboxes.
- Default path: `platformdirs.user_data_dir("mgd-vault") / "vault.kdbx"`.
  - macOS: `~/Library/Application Support/mgd-vault/vault.kdbx`
  - Linux: `~/.local/share/mgd-vault/vault.kdbx`
  - Windows: `%LOCALAPPDATA%\mgd-vault\mgd-vault\vault.kdbx` (platformdirs
    nests an author dir; accept it, document it).
- Override: `MGD_VAULT_PATH`. Used to point at a Drive-synced file or a
  per-project vault without copying.
- Permissions: file `0o600`, directory `0o700`, re-applied after every write.
  Best effort on Windows (set via `icacls` only if trivial; otherwise rely on
  the user profile ACL and document it).
- Lock file: `vault.kdbx.lock` beside the vault (§7).

### Master password

Resolution order, first hit wins:

1. `MGD_VAULT_PASSWORD` in the process environment.
2. `MGD_VAULT_PASSWORD` in `./.env` (project-local, via `python-dotenv`,
   never overriding an existing env var).
3. `MGD_VAULT_PASSWORD` in the per-user env file
   `platformdirs.user_config_dir("mgd-vault") / "env"` (`0o600`). This is
   the normal place on a workstation, so projects do not each carry the
   password. Cron, launchd, and systemd do not read shell rc files; this file
   is read by the library itself, so it works for them.
4. `MGD_VAULT_KEYFILE` pointing at a KeePass key file (may be combined with a
   password, standard KeePass semantics).
5. Otherwise raise `VaultLockedError` with a message naming the three
   locations.

Never prompt interactively inside the library. The CLI may prompt on
`mgd-vault init` and `mgd-vault unlock-check` only.

### Entry layout inside the KDBX

- Keys are path-like: `google/mdinunziosvc/oauth_token`, `anthropic/api_key`,
  `dexcom/password`. Segments match `^[a-z0-9_.-]+$`.
- All segments but the last map to nested KeePass groups under the root;
  the last segment is the entry title. This makes the vault browsable in
  KeePassXC.
- The secret value lives in the entry's **password** field (KDBX protects it
  in memory). JSON bundles are stored as the JSON string.
- Custom string properties on every entry (set `protect=False`; they are
  metadata, not secrets):
  - `mgd.kind`: `static` | `oauth-bundle` | `other`
  - `mgd.scope`: `shared` | `local` (see §8)
  - `mgd.updated_at`: ISO-8601 UTC
  - `mgd.schema`: integer, currently `1`
- `expiry_time` / `expires`: optional, set by callers that know an expiry.
  The vault never acts on it; it is informational and visible in KeePassXC.
- KeePass `username` and `url` fields: optional free text supplied by the
  caller (e.g. the Google account email), purely for human browsing.
- One reserved entry at root, title `_mgd_vault_meta`, custom property
  `mgd.schema` = vault schema version and `mgd.created_by`.

### Key derivation cost

`pykeepass.create_database` copies a bundled blank template, so KDF
parameters come from that template, and `pykeepass` exposes no documented API
for changing them. Measure `PyKeePass(...)` open time on the Mac and VPS during
Phase 1. Target under 150 ms. If slower, open the file once in KeePassXC and
lower the Argon2 parameters under *Database Settings → Security*, then
document that step in `init`. Do not cache the transformed key across
processes; it is secret-equivalent.

---

## 5. Python API

Functional module, no classes for the public surface (per the author's
project conventions). Package name `mgd_vault`, distribution `mgd-vault`.

```python
from mgd_vault import vault

vault.get(key: str) -> str | None
vault.get_json(key: str) -> Any | None          # json.loads of get()
vault.set(key: str, value: str, *, kind: str = "static",
          scope: str = "shared", expires_at: datetime | None = None,
          username: str | None = None, url: str | None = None) -> None
vault.set_json(key: str, value: Any, **meta) -> None
vault.delete(key: str) -> None                 # silent if absent
vault.exists(key: str) -> bool
vault.list(prefix: str = "") -> list[str]      # sorted keys, no values
vault.info(key: str) -> EntryInfo | None       # metadata only, never value
vault.update(key: str, fn: Callable[[str | None], str | None], **meta) -> str | None
vault.where() -> VaultLocation                 # path, backend, password source
```

- `EntryInfo` and `VaultLocation` are frozen dataclasses.
- `update(key, fn)` is the concurrency primitive (§7). It acquires the lock,
  reloads the vault from disk, calls `fn(current_value)`, and if `fn` returns
  a string different from the current value, writes it and saves. Returning
  `None` deletes. Returning the unchanged value is a no-op with no write.
- Every public function opens the vault fresh, does its work, and closes. No
  module-level cached `PyKeePass` object. Simplicity and correctness beat the
  key-derivation cost; revisit only if measurements in §4 demand it.
- Errors: `VaultError` base; `VaultLockedError` (no password);
  `VaultNotFoundError` (no file at the resolved path and not creating);
  `VaultLockTimeoutError`; `VaultKeyError` (malformed key).

### Env override backend (bootstrap only)

Before consulting the file, `get` checks the environment variable
`MGD_SECRET_<KEY>` where `<KEY>` is the key upper-cased with `/`, `.`, and
`-` replaced by `_` (`google/mdinunziosvc/oauth_token` becomes
`MGD_SECRET_GOOGLE_MDINUNZIOSVC_OAUTH_TOKEN`). If present:

- the value is returned, and
- if a vault file is openable, the value is written into it (same key, kind
  from `MGD_SECRET_<KEY>__KIND` if set, else `static`), and
- subsequent reads prefer the vault copy once it exists.

This is how a cloud session bootstraps from pasted env vars and still supports
rotating tokens afterwards. `set` never writes to the environment.

### Exec escape hatch (Phase 3, optional)

`MGD_VAULT_EXEC=/abs/path/to/cmd` names a program that receives
`{"ids": [...]}` on stdin and returns `{"values": {...}}` on stdout, the same
protocol shape OpenClaw uses. If set, `get` consults it before the file. This
lets 1Password `op` or Bitwarden `bws` serve some keys later without touching
callers. Not needed for v1; keep the seam in mind when structuring `get`.

---

## 6. Static vs rotating secrets

The vault stores opaque strings. The distinction matters for three features:

| Concern            | `static`                        | `oauth-bundle`                                   |
|--------------------|---------------------------------|--------------------------------------------------|
| Who writes         | human / setup flow, once        | provider library, on every refresh                |
| Export             | included                        | **excluded** by default (`--include-rotating` to force) |
| Multi-machine sync | safe                            | unsafe for providers that rotate refresh tokens   |
| Default scope      | `shared`                        | `local`                                          |

Known provider facts the builder must not get wrong:

- **Whoop** rotates the refresh token on every refresh and invalidates the
  old one. Only one machine can hold a live grant. Never copy its bundle.
- **Google** refresh tokens do not rotate; several machines may share one
  bundle. But if the OAuth client is in *Testing* publishing status, refresh
  tokens expire after seven days. That is a Cloud Console setting, not a vault
  concern.
- **YNAB, Maps, Anthropic, GitHub PATs, Dexcom**: static until revoked.

Refresh logic never lives here. mgdio calls `vault.update` with a function
that checks expiry, refreshes if still needed, and returns the new bundle.

---

## 7. Concurrency

The problem: `pykeepass` loads the whole file into memory and overwrites it on
save. Two processes doing load → modify → save will drop one write. On the
VPS, Airflow runs several mgdio-using tasks in parallel, and each may write
back a refreshed token.

Decision: **one vault file, one lock. Not one file per secret.** Per-secret
files only avoid collisions between *different* secrets, which are the easy
case. The collisions that happen in practice are on the *same* secret (two
tasks both refreshing the Google access token), and only a lock fixes those.

Rules:

- Every write (`set`, `delete`, `update`, env-bootstrap write) runs inside
  `filelock.FileLock(vault_path + ".lock", timeout=10)`. `filelock` handles
  POSIX and Windows.
- Inside the lock: reload from disk, mutate, `save()` to a temp file in the
  same directory, `os.replace` onto the vault path, `chmod 0o600`, fsync the
  directory on POSIX. Never `save()` directly onto the live path.
- Reads do not take the lock. Atomic replace guarantees a reader sees a
  complete old or new file. A read that hits a transient decrypt error retries
  once after 50 ms.
- `update(key, fn)` is the only correct way to do check-then-write. Document
  prominently that `get` followed by `set` is a race.
- Lock timeout raises `VaultLockTimeoutError` with the lock path in the
  message. Never spin forever; cron must fail loudly.

---

## 8. Sync and multi-machine policy

- `scope=shared` entries may be replicated across machines (Drive-synced
  `.kdbx`, `export`/`import`).
- `scope=local` entries are machine-bound. `export` skips them unless forced.
- Syncing the live vault file through Drive is **supported but discouraged**
  while any `local`/rotating entries live in it, because concurrent writes
  from two machines produce Drive conflict copies. The recommended pattern is
  a one-time `export` → `import` and then independent vaults per machine.
- If the author later wants a synced shared vault, the design accommodates a
  second file (`MGD_VAULT_SHARED_PATH`) read after the local one for `shared`
  keys only. **Out of scope for v1**; do not build it speculatively.

---

## 9. CLI

Entry point `mgd-vault` (Click). Every command honours `MGD_VAULT_PATH` and
the password resolution in §4. Nothing prints a secret value unless the
command is explicitly `get`.

```
mgd-vault init [--from PATH] [--password-stdin] [--keyfile PATH]
    Create a new vault at the standard location, or copy an existing .kdbx
    there (--from). Prompts for the master password unless --password-stdin.
    Offers to write MGD_VAULT_PASSWORD into the per-user env file (0600).
    If --from is given, prints a notice that the original is now a stale copy
    and suggests MGD_VAULT_PATH if the user wants it used in place instead.

mgd-vault where
    Print resolved vault path, whether it exists, which password source was
    used (env / .env / user env file / keyfile / none), lock path.

mgd-vault get KEY            Print the value (and nothing else) to stdout.
mgd-vault set KEY [--value V | --stdin | --prompt] [--kind K] [--scope S]
                              [--expires ISO] [--username U] [--url U]
mgd-vault delete KEY
mgd-vault list [PREFIX] [--long]
    Keys only; --long adds kind, scope, updated_at, expiry. Never values.
mgd-vault export [--format env|json] [--prefix P] [--include-rotating]
    env format prints MGD_SECRET_<KEY>=<value> lines (shell-quoted) suitable
    for pasting into a cloud environment's variable config or a .env.
    json format prints {key: {value, kind, scope, ...}}.
mgd-vault import [--format env|json] [FILE | -]
    Inverse of export. Existing keys are overwritten only with --overwrite.
mgd-vault doctor
    Opens the vault, times the open, checks file and dir permissions, checks
    the lock file is not stale, reports entry counts by kind/scope, warns if
    MGD_VAULT_PASSWORD is in a world-readable file.
```

Exit codes: 0 ok, 1 vault error (locked, not found, lock timeout), 2 usage.

---

## 10. Onboarding an existing KeePass database

Two supported paths, chosen by the user:

1. **Copy in** (`mgd-vault init --from ~/Downloads/existing.kdbx`): the file
   is copied to the standard path, permissions applied, the meta entry added
   if missing. Entries that already exist are left untouched; entries without
   `mgd.*` properties are treated as `kind=static, scope=shared` on read and
   get the properties written on their next `set`. Group paths become key
   prefixes (lower-cased, invalid characters replaced with `-`), so a
   pre-existing `Email/Gmail` entry reads as `email/gmail`.
2. **Use in place** (`MGD_VAULT_PATH=/path/to/existing.kdbx`): no copy. The
   user keeps editing in KeePassXC. All locking and atomic-write rules apply
   to that path. Document that KeePassXC's own save will race the lock, so
   close KeePassXC before unattended jobs run, or accept last-writer-wins.

Entries created by other tools and lacking a title, or with titles that do not
match the key grammar, are listed by `doctor` as "unaddressable" and ignored
by `list`/`get`. Nothing is ever deleted or renamed automatically.

---

## 11. Project conventions

Match the author's other repos:

- `uv` for environment and lockfile; `pyproject.toml` with `[project]`
  metadata; `requires-python >= 3.11` (filelock and platformdirs floors).
- Dependencies: `pykeepass>=4.2`, `filelock>=3.13`, `platformdirs>=4.2`,
  `python-dotenv>=1.0`, `click>=8.1`. No others without justification.
- `black` formatting, `flake8` + `flake8-docstrings` linting, `isort`.
- Functional modules over classes. Module-level state only for the resolved
  configuration, and it must be re-resolvable in tests.
- `pytest` with test-driven development. Every public function has tests.
  Tests create real `.kdbx` files in `tmp_path`; do not mock `pykeepass`.
  Concurrency tests spawn real subprocesses (`multiprocessing` with `spawn`)
  hammering `update` on one file and assert no lost writes.
- Google-style docstrings. README documents every env var, every CLI
  command, the password resolution order, the static/rotating rule, and the
  "`get` then `set` is a race" warning.
- `examples/` folder with a quickstart script.
- Commit messages and PR bodies end with the attribution line the session's
  system reminder specifies.

Suggested layout:

```
mgd-vault/
  pyproject.toml
  README.md
  mgd_vault/
    __init__.py        # re-exports vault API + exceptions
    _config.py         # path + password resolution
    _store.py          # pykeepass open/save, locking, atomic replace
    _keys.py           # key grammar, key <-> group path, env var name mapping
    vault.py           # public functional API
    exceptions.py
    cli.py
  tests/
  examples/
```

---

## 12. Phased plan

**Phase 1: core** (ship first)
`_config`, `_keys`, `_store` with lock + atomic save, `vault.get/set/
delete/exists/list/info/update/where`, exceptions, env-override bootstrap,
`init`/`where`/`get`/`set`/`delete`/`list`/`doctor` CLI, open-time
measurement on Mac and VPS, concurrency test. README.

**Phase 2: portability**
`export`/`import`, `init --from`, onboarding rules from §10, scope handling
in export.

**Phase 3: integration and extras**
mgdio `secrets` seam gets a `vault` backend (built in the mgdio repo against
this package). `mgd-data-sync` moves its env-file secrets into the vault.
Exec escape hatch if a use case appears. Optional `MGD_VAULT_SHARED_PATH` if
Drive sync of shared statics proves wanted.

---

## 13. Open questions

Decide during Phase 1; none block starting.

1. Windows permission hardening: is an `icacls` call worth it, or document
   that `%LOCALAPPDATA%` is already user-private?
2. Should `list` include entries lacking `mgd.*` properties (onboarded
   foreign entries) by default, or only with `--all`? Leaning: include, since
   onboarding is a stated goal.
3. Should `export --format env` emit `MGD_SECRET_<KEY>__KIND` lines so the
   bootstrap write preserves kind? Leaning: yes, cheap.
4. Lock timeout default: 10 s is a guess. Airflow tasks tolerate it; a CLI
   user might prefer 2 s. Make it `MGD_VAULT_LOCK_TIMEOUT`-tunable either way.

---

## 14. Related documents

- `mgdio/docs/secret-store-design.md`: the earlier, narrower design for a
  secrets seam inside mgdio. This spec supersedes its "file backend" idea
  with mgd-vault; its env-as-seed rule and Whoop rotation caveat carry over
  unchanged and are restated above.
