# Command line

The `mgdvault` command operates on the default vault, so it honours the same
environment variables as the Python API. Run it as `uv run mgdvault` inside a
project or as `mgdvault` after `uv tool install mgdvault`.

```
mgdvault info                        Show backend, location and secret count
mgdvault init [--path FILE]          Create the KeePass database explicitly
mgdvault list [PREFIX]               List keys (never values)
mgdvault exists KEY                  Print yes/no; exit code 0 or 1
mgdvault set KEY                     Store a value from a hidden prompt
mgdvault set KEY --from-file PATH    Store a file's contents
cmd | mgdvault set KEY               Store from stdin
mgdvault set KEY --json              Also validate the value as JSON
mgdvault get KEY [--default VALUE]   Print the value to stdout
mgdvault delete KEY [-y]             Remove a secret
mgdvault list-skills                 Show bundled Claude Code skills
mgdvault install-skill [--global] [--force] [--skill NAME]
```

## Secret values never go on the command line

`set` has no value argument on purpose. Interactively you get a hidden prompt
with confirmation; non-interactively the value is read from stdin or a file.
This keeps secrets out of shell history, `ps` output, and agent transcripts.

```bash
mgdvault set myapp/google/client_secret --from-file ~/Downloads/client_secret.json --json
op read "op://vault/item/token" | mgdvault set myapp/token
```

`get` prints the raw value with no trailing newline when piped, so it composes:

```bash
export OPENAI_API_KEY="$(mgdvault get myapp/openai/api_key)"
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success (for `exists`: the key is present) |
| 1 | Error, or for `exists`/`delete`: the key is absent |
