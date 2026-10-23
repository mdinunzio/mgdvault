# Development

```bash
git clone https://github.com/mdinunzio/mgdvault
cd mgdvault
uv sync --extra dev --extra docs
```

`uv sync` also installs the `dev` dependency group (JupyterLab, ipykernel,
nbconvert) used for the examples notebook.

| Task | Command |
| --- | --- |
| Tests | `uv run pytest` |
| Coverage | `uv run pytest --cov=mgdvault --cov-report=term-missing` |
| Format | `uv run black src tests` |
| Lint | `uv run flake8 src tests` |
| Docs (live) | `uv run mkdocs serve` |
| Docs (build) | `uv run mkdocs build --strict` |
| Examples notebook | `uv run jupyter lab examples/` |
| Re-execute notebook outputs | `uv run jupyter nbconvert --to notebook --execute --inplace examples/mgdvault_tour.ipynb` |

Conventions: Google-style docstrings on every public object, `black`
formatting at 88 columns, `flake8` with `flake8-docstrings`. Tests never touch
the real OS keyring (a fake backend is monkeypatched in) and create KeePass
databases under `tmp_path`.

The autouse fixture in `tests/conftest.py` strips `MGDVAULT_*` variables and
sets `MGDVAULT_DOTENV=0`, so a developer's repo-local `.env` cannot leak into
the suite; `tests/test_envfile.py` opts back in to exercise discovery.

## Publishing the docs to GitHub Pages

`mkdocs gh-deploy` builds the site and pushes it to a `gh-pages` branch; in
the repository settings choose that branch as the Pages source. A GitHub
Actions workflow that runs `uv run mkdocs gh-deploy --force` on pushes to
`main` keeps it current.
