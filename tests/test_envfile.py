from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import mgdvault
from mgdvault import settings
from mgdvault.cli import main
from mgdvault.envfile import find_env_file, load_env_file


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    """A repo with a .env at its root; cwd is a nested subdirectory."""
    (tmp_path / ".env").write_text(
        "MGDVAULT_PASSWORD=from-dotenv\n"
        f"MGDVAULT_PATH={tmp_path / 'vault.kdbx'}\n"
        "MGDVAULT_LOCK_TIMEOUT=7\n"
    )
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv(settings.ENV_DOTENV, raising=False)  # re-enable discovery
    return tmp_path


def test_find_env_file_walks_upward(project):
    assert find_env_file() == project / ".env"
    assert find_env_file(project / "src") == project / ".env"


def test_find_env_file_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # tmp_path's parents are unlikely to hold a .env, but guard anyway
    found = find_env_file()
    assert found is None or found.parent not in (tmp_path,)


def test_load_sets_missing_variables_only(project, monkeypatch):
    monkeypatch.setenv(settings.ENV_PASSWORD, "exported-wins")
    loaded = load_env_file()
    assert loaded == project / ".env"
    import os

    assert os.environ[settings.ENV_PASSWORD] == "exported-wins"
    assert os.environ[settings.ENV_LOCK_TIMEOUT] == "7"


def test_default_vault_picks_up_dotenv(project):
    vault = mgdvault.default_vault()
    assert vault.path == project / "vault.kdbx"
    assert vault.lock_timeout == 7.0


def test_explicit_mapping_skips_dotenv(project):
    with pytest.raises(mgdvault.VaultConfigurationError):
        mgdvault.vault_from_env({})


def test_disabled_via_env_var(project, monkeypatch):
    monkeypatch.setenv(settings.ENV_DOTENV, "0")
    assert load_env_file() is None
    with pytest.raises(mgdvault.VaultConfigurationError):
        mgdvault.default_vault()


def test_explicit_file_via_env_var(project, tmp_path, monkeypatch):
    other = tmp_path / "other.env"
    other.write_text("MGDVAULT_BACKEND=memory\n")
    monkeypatch.setenv(settings.ENV_DOTENV, str(other))
    assert load_env_file() == other
    assert isinstance(mgdvault.default_vault(), mgdvault.MemoryVault)


def test_missing_explicit_file_is_ignored(project, monkeypatch):
    monkeypatch.setenv(settings.ENV_DOTENV, str(project / "nope.env"))
    assert load_env_file() is None


def test_cli_reads_dotenv(project):
    runner = CliRunner()
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0, result.output
    assert f"dotenv:    {project / '.env'}" in result.output
    assert str(project / "vault.kdbx") in result.output


def test_cli_info_reports_no_dotenv(keepass_env):
    result = CliRunner().invoke(main, ["info"])
    assert "dotenv:    none loaded" in result.output
