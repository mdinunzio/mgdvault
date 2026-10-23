"""The ``mgdvault`` command line interface.

Secret values are never accepted as command-line arguments: ``set`` reads
them from a hidden prompt or from standard input, so they stay out of shell
history, process listings and agent transcripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

import mgdvault
from mgdvault import settings
from mgdvault.backends import KeePassVault
from mgdvault.envfile import load_env_file
from mgdvault.exceptions import MgdvaultError
from mgdvault.skills import install_skills, iter_skill_dirs, read_description


def _vault() -> mgdvault.Vault:
    try:
        return mgdvault.default_vault()
    except MgdvaultError as exc:
        raise click.ClickException(str(exc)) from exc


def _run(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except MgdvaultError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(mgdvault.__version__, prog_name="mgdvault")
def main() -> None:
    """Manage secrets in the default mgdvault vault.

    The vault is chosen from environment variables: set MGDVAULT_PASSWORD for
    the default KeePass database, or MGDVAULT_BACKEND=keyring for the OS
    credential manager. The nearest .env above the working directory is
    loaded first without overriding exported variables (MGDVAULT_DOTENV=0
    disables this). Run `mgdvault info` to see what is in effect.
    """
    load_env_file()


@main.command()
def info() -> None:
    """Show the active backend and location (never prints secret values)."""
    import os

    loaded = load_env_file()
    click.echo(f"dotenv:    {loaded if loaded else 'none loaded'}")
    click.echo(
        f"backend:   {os.environ.get(settings.ENV_BACKEND, settings.DEFAULT_BACKEND)}"
    )
    try:
        vault = mgdvault.default_vault()
    except MgdvaultError as exc:
        click.echo(f"status:    not configured\n           {exc}")
        sys.exit(1)
    click.echo(f"location:  {vault.describe_location()}")
    if isinstance(vault, KeePassVault):
        click.echo(f"file:      {'exists' if vault.file_exists else 'will be created'}")
    try:
        count = len(vault.list_keys())
    except MgdvaultError as exc:
        click.echo(f"status:    locked\n           {exc}")
        sys.exit(1)
    click.echo(f"secrets:   {count}")


@main.command()
@click.option(
    "--path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Database location (default: MGDVAULT_PATH or the user data dir).",
)
def init(path: Path | None) -> None:
    """Create the KeePass database now instead of on first use.

    Reads the master password from MGDVAULT_PASSWORD, or prompts for one.
    """
    import os

    db_path = path or Path(
        os.environ.get(settings.ENV_PATH) or settings.default_db_path()
    )
    password = os.environ.get(settings.ENV_PASSWORD) or None
    keyfile = os.environ.get(settings.ENV_KEYFILE) or None
    if db_path.exists():
        click.echo(f"Database already exists at {db_path}")
        return
    if not password and not keyfile:
        password = click.prompt(
            "Master password for the new vault",
            hide_input=True,
            confirmation_prompt=True,
        )
        click.echo(
            f"Remember to export {settings.ENV_PASSWORD} (or add it to your .env) "
            "so applications can unlock the vault."
        )
    vault = KeePassVault(db_path, password=password, keyfile=keyfile)
    _run(vault.list_keys)  # forces creation
    click.echo(f"Created KeePass vault at {db_path}")


@main.command()
@click.argument("key")
@click.option(
    "--default", "default_value", default=None, help="Print this if KEY is absent."
)
def get(key: str, default_value: str | None) -> None:
    """Print the secret stored at KEY to stdout.

    Avoid running this inside an AI agent session unless the value must
    appear there; prefer `exists` to check presence.
    """
    vault = _vault()
    if default_value is None:
        value = _run(vault.get, key)
    else:
        value = _run(vault.get, key, default_value)
    click.echo(value, nl=False)
    if sys.stdout.isatty():
        click.echo()


@main.command(name="set")
@click.argument("key")
@click.option(
    "--from-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Read the value from this file (whole contents, trailing newline kept).",
)
@click.option(
    "--stdin",
    "from_stdin",
    is_flag=True,
    help="Read the value from stdin (default when stdin is not a terminal).",
)
@click.option("--json", "as_json", is_flag=True, help="Validate the value as JSON.")
def set_(key: str, from_file: Path | None, from_stdin: bool, as_json: bool) -> None:
    """Store a secret at KEY.

    The value is never taken from the command line. Interactively you are
    prompted with hidden input; otherwise pipe it in:
    `cat token.json | mgdvault set myapp/token`.
    """
    if from_file is not None:
        value = from_file.read_text(encoding="utf-8")
    elif from_stdin or not sys.stdin.isatty():
        value = sys.stdin.read()
        if value.endswith("\n"):
            value = value[:-1]
    else:
        value = click.prompt(
            f"Value for {key}", hide_input=True, confirmation_prompt=True
        )
    if as_json:
        import json

        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Value is not valid JSON: {exc}") from exc
    if value == "":
        raise click.ClickException("Refusing to store an empty value.")
    _run(_vault().set, key, value)
    click.echo(f"Stored {key}", err=True)


@main.command()
@click.argument("key")
@click.option("-y", "--yes", is_flag=True, help="Do not ask for confirmation.")
def delete(key: str, yes: bool) -> None:
    """Delete the secret stored at KEY."""
    vault = _vault()
    if not _run(vault.exists, key):
        click.echo(f"No secret at {key}", err=True)
        sys.exit(1)
    if not yes:
        click.confirm(f"Delete {key}?", abort=True)
    _run(vault.delete, key)
    click.echo(f"Deleted {key}", err=True)


@main.command()
@click.argument("key")
def exists(key: str) -> None:
    """Exit 0 if KEY is stored, 1 otherwise. Prints nothing secret."""
    present = _run(_vault().exists, key)
    click.echo("yes" if present else "no")
    sys.exit(0 if present else 1)


@main.command(name="list")
@click.argument("prefix", required=False)
def list_(prefix: str | None) -> None:
    """List stored keys, optionally under PREFIX (e.g. `mgdvault list mgdio`)."""
    for key in _run(_vault().list_keys, prefix):
        click.echo(key)


@main.command(name="list-skills")
def list_skills() -> None:
    """List the Claude Code skills bundled with this version."""
    with iter_skill_dirs() as dirs:
        for d in dirs:
            click.echo(f"{d.name}: {read_description(d)}")


@main.command(name="install-skill")
@click.option(
    "--global",
    "global_install",
    is_flag=True,
    help="Install to ~/.claude/skills/ for every project (default: ./.claude/skills/).",
)
@click.option("--force", is_flag=True, help="Overwrite skills already present.")
@click.option(
    "--skill",
    "only",
    multiple=True,
    help="Install only this skill (repeatable). Default: all bundled skills.",
)
def install_skill(global_install: bool, force: bool, only: tuple[str, ...]) -> None:
    """Install the bundled Claude Code skills.

    Project install: `uv run mgdvault install-skill`.
    Global install without a project: `uv tool install mgdvault` then
    `mgdvault install-skill --global`.
    """
    if global_install:
        target_root = Path.home() / ".claude" / "skills"
    else:
        target_root = Path.cwd() / ".claude" / "skills"
    try:
        results = install_skills(target_root, force=force, only=list(only) or None)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    for res in results:
        click.echo(f"{res.status:>9}  {res.target}")
    if any(r.status == "skipped" for r in results):
        click.echo("Use --force to overwrite skipped skills.", err=True)
    click.echo("Restart Claude Code (or run /clear) for new skills to load.", err=True)


if __name__ == "__main__":  # pragma: no cover
    main()
