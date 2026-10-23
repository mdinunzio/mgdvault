import pytest

from mgdvault.backends import EnvVault
from mgdvault.backends.env import env_var_to_key, key_to_env_var
from mgdvault.exceptions import ReadOnlyVaultError


def test_key_mapping():
    assert key_to_env_var("mgdio/google/personal") == (
        "MGDVAULT_SECRET_MGDIO__GOOGLE__PERSONAL"
    )
    assert key_to_env_var("a-b.c/d", prefix="P_") == "P_A_B_C__D"
    assert env_var_to_key("MGDVAULT_SECRET_MGDIO__GOOGLE__PERSONAL") == (
        "mgdio/google/personal"
    )


def test_reads_from_mapping():
    env = {"MGDVAULT_SECRET_APP__TOKEN": "t", "UNRELATED": "x"}
    vault = EnvVault(environ=env)
    assert vault.get("app/token") == "t"
    assert vault.get("app/other", default=None) is None
    assert vault.list_keys() == ["app/token"]
    assert vault.read_only


def test_reads_os_environ_by_default(monkeypatch):
    monkeypatch.setenv("MGDVAULT_SECRET_APP__TOKEN", "t")
    assert EnvVault().get("app/token") == "t"


def test_writes_rejected():
    vault = EnvVault(environ={})
    with pytest.raises(ReadOnlyVaultError):
        vault.set("app/token", "t")
    with pytest.raises(ReadOnlyVaultError):
        vault.delete("app/token")
