# Examples

| Notebook | What it covers |
| --- | --- |
| [mgdvault_tour.ipynb](mgdvault_tour.ipynb) | Quick start (one env var, `get`/`set`), everyday use (defaults, JSON token bundles, namespaces, the CLI), then power-user features (explicit and layered vaults, test doubles, atomic `update`, concurrent writers, caching, alternative backends, key files, KeePassXC interoperability, error types) |

The notebook runs against a throwaway vault in a temporary directory with
made-up values, so the saved outputs contain nothing sensitive and it never
touches your real vault.

## Running it yourself

```bash
uv sync --extra dev          # installs JupyterLab from the dev dependency group
uv run jupyter lab examples/
```

To refresh the saved outputs after a code change:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace examples/mgdvault_tour.ipynb
```
