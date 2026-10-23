# mgdvault

Secret storage library: KeePass (`pykeepass`) by default, OS keyring optional,
one `Vault` interface. Public API is the module-level functions in
`src/mgdvault/api.py` plus the classes in `src/mgdvault/backends/`.

## Conventions

- `src/` layout, hatchling build, `uv` for everything.
- Google-style docstrings on all public objects; `black` (88 cols) and
  `flake8` + `flake8-docstrings` must pass: `uv run black src tests && uv run flake8 src tests`.
- Tests: `uv run pytest`. Never touch the real OS keyring in tests (use
  `tests/fake_keyring.py`); KeePass databases go under `tmp_path`.
- The package must not read `.env`; only `tests/conftest.py` does.
- Keys are `app/service/name` paths validated in `src/mgdvault/keys.py`.
- CLI (`src/mgdvault/cli.py`) never accepts secret values as arguments.
- Bundled Claude Code skills live in `src/mgdvault/skills/*/SKILL.md`; keep
  them in sync with CLI and API changes.
- Docs: mkdocs + mkdocstrings, `uv run mkdocs build --strict` must pass.
- `examples/mgdvault_tour.ipynb` is generated-then-executed; it must run only
  against a temp-dir vault with fake values and never print the password. After
  API changes, re-execute it with nbconvert so saved outputs stay current.

## KeePass backend gotchas

- `pykeepass.save()` rotates the KDF salt unless `transformed_key` is passed;
  we always pass it so other processes' cached keys stay valid.
- `create_database()` returns a stale `transformed_key`; reopen after creating.
- Reads never take the file lock; `set`/`delete`/`update` do. `update` is the
  only safe read-modify-write; keep that invariant.
- An earlier, more elaborate design (`git show cac7446:mgd-vault-spec.md`)
  was superseded by the 2026-10-23 conversation: names are `mgdvault` /
  `MGDVAULT_*`, no dotenv loading, no entry metadata, export/import deferred.
