from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import mgdvault
from mgdvault import settings
from mgdvault.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_info_not_configured(runner):
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 1
    assert "not configured" in result.output
    assert settings.ENV_PASSWORD in result.output


def test_info_configured(runner, keepass_env):
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0, result.output
    assert "keepass" in result.output
    assert str(keepass_env) in result.output
    assert "secrets:   0" in result.output


def test_set_from_stdin_then_get(runner, keepass_env):
    result = runner.invoke(main, ["set", "app/key"], input="s3cret\n")
    assert result.exit_code == 0, result.output
    assert "s3cret" not in result.output
    result = runner.invoke(main, ["get", "app/key"])
    assert result.exit_code == 0
    assert result.output == "s3cret"


def test_set_rejects_empty(runner, keepass_env):
    result = runner.invoke(main, ["set", "app/key"], input="\n")
    assert result.exit_code != 0
    assert "empty" in result.output


def test_set_from_file_keeps_contents(runner, keepass_env, tmp_path):
    f = tmp_path / "client_secret.json"
    f.write_text('{"a": 1}\n')
    result = runner.invoke(main, ["set", "app/json", "--from-file", str(f), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(mgdvault.get("app/json")) == {"a": 1}


def test_set_json_validation(runner, keepass_env):
    result = runner.invoke(main, ["set", "app/json", "--json"], input="not json")
    assert result.exit_code != 0
    assert "not valid JSON" in result.output


def test_exists_and_list(runner, keepass_env):
    runner.invoke(main, ["set", "app/one"], input="1")
    runner.invoke(main, ["set", "other/two"], input="2")
    assert runner.invoke(main, ["exists", "app/one"]).exit_code == 0
    assert runner.invoke(main, ["exists", "app/none"]).exit_code == 1
    result = runner.invoke(main, ["list"])
    assert result.output.split() == ["app/one", "other/two"]
    result = runner.invoke(main, ["list", "app"])
    assert result.output.split() == ["app/one"]


def test_get_missing_and_default(runner, keepass_env):
    result = runner.invoke(main, ["get", "app/none"])
    assert result.exit_code != 0
    assert "No secret stored" in result.output
    result = runner.invoke(main, ["get", "app/none", "--default", "x"])
    assert result.exit_code == 0
    assert result.output == "x"


def test_delete(runner, keepass_env):
    runner.invoke(main, ["set", "app/one"], input="1")
    result = runner.invoke(main, ["delete", "app/one"], input="n\n")
    assert result.exit_code != 0
    assert mgdvault.exists("app/one")
    result = runner.invoke(main, ["delete", "app/one", "-y"])
    assert result.exit_code == 0
    assert not mgdvault.exists("app/one")
    assert runner.invoke(main, ["delete", "app/one", "-y"]).exit_code == 1


def test_init_with_env_password(runner, keepass_env):
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert keepass_env.exists()
    result = runner.invoke(main, ["init"])
    assert "already exists" in result.output


def test_init_prompts_without_password(runner, tmp_path):
    target = tmp_path / "v.kdbx"
    result = runner.invoke(main, ["init", "--path", str(target)], input="pw\npw\n")
    assert result.exit_code == 0, result.output
    assert target.exists()
    assert "pw" not in result.output.replace("password", "")


def test_wrong_password_message(runner, keepass_env, monkeypatch):
    runner.invoke(main, ["set", "app/one"], input="1")
    mgdvault.reset_default_vault()
    monkeypatch.setenv(settings.ENV_PASSWORD, "wrong")
    result = runner.invoke(main, ["list"])
    assert result.exit_code != 0
    assert "wrong password" in result.output


def test_list_skills(runner):
    result = runner.invoke(main, ["list-skills"])
    assert result.exit_code == 0
    assert "mgdvault:" in result.output
    assert "mgdvault-integration:" in result.output


def test_install_skill_project_and_global(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    result = runner.invoke(main, ["install-skill"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".claude" / "skills" / "mgdvault" / "SKILL.md").is_file()
    assert (
        tmp_path / ".claude" / "skills" / "mgdvault-integration" / "SKILL.md"
    ).is_file()

    result = runner.invoke(main, ["install-skill"])
    assert "skipped" in result.output
    result = runner.invoke(main, ["install-skill", "--force"])
    assert "updated" in result.output

    result = runner.invoke(main, ["install-skill", "--global", "--skill", "mgdvault"])
    assert result.exit_code == 0, result.output
    assert (home / ".claude" / "skills" / "mgdvault" / "SKILL.md").is_file()
    assert not (home / ".claude" / "skills" / "mgdvault-integration").exists()

    result = runner.invoke(main, ["install-skill", "--skill", "nope"])
    assert result.exit_code != 0
    assert "Unknown skill" in result.output


def test_version(runner):
    result = runner.invoke(main, ["--version"])
    assert mgdvault.__version__ in result.output
