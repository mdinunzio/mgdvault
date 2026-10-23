from __future__ import annotations

import pytest

import mgdvault
from mgdvault import settings
from mgdvault.backends import EnvVault, KeePassVault, KeyringVault, MemoryVault
from mgdvault.exceptions import SecretNotFoundError, VaultConfigurationError

from .fake_keyring import install_fake_keyring


def test_default_is_keepass_at_env_path(keepass_env):
    vault = mgdvault.default_vault()
    assert isinstance(vault, KeePassVault)
    assert vault.path == keepass_env
    assert mgdvault.default_vault() is vault


def test_default_path_when_unset(monkeypatch):
    monkeypatch.setenv(settings.ENV_PASSWORD, "pw")
    vault = mgdvault.default_vault()
    assert isinstance(vault, KeePassVault)
    assert vault.path == settings.default_db_path()
    assert vault.path.name == "vault.kdbx"
    assert "mgdvault" in str(vault.path)


def test_missing_password_is_a_clear_error():
    with pytest.raises(VaultConfigurationError) as exc:
        mgdvault.default_vault()
    assert settings.ENV_PASSWORD in str(exc.value)


def test_keyfile_alone_is_enough(monkeypatch, tmp_path):
    monkeypatch.setenv(settings.ENV_KEYFILE, str(tmp_path / "k"))
    assert isinstance(mgdvault.default_vault(), KeePassVault)


def test_backend_keyring(monkeypatch):
    install_fake_keyring(monkeypatch)
    monkeypatch.setenv(settings.ENV_BACKEND, "keyring")
    monkeypatch.setenv(settings.ENV_KEYRING_SERVICE, "custom")
    vault = mgdvault.default_vault()
    assert isinstance(vault, KeyringVault)
    assert vault.service == "custom"


def test_backend_env_and_memory(monkeypatch):
    monkeypatch.setenv(settings.ENV_BACKEND, "env")
    assert isinstance(mgdvault.default_vault(), EnvVault)
    mgdvault.reset_default_vault()
    monkeypatch.setenv(settings.ENV_BACKEND, "Memory ")
    assert isinstance(mgdvault.default_vault(), MemoryVault)


def test_unknown_backend(monkeypatch):
    monkeypatch.setenv(settings.ENV_BACKEND, "sqlite")
    with pytest.raises(VaultConfigurationError):
        mgdvault.default_vault()


def test_environment_read_lazily(monkeypatch, keepass_env):
    """Variables set after import, before first use, are honoured."""
    monkeypatch.setenv(settings.ENV_BACKEND, "memory")
    assert isinstance(mgdvault.default_vault(), MemoryVault)


def test_functional_api(keepass_env):
    assert not mgdvault.exists("app/key")
    mgdvault.set("app/key", "v")
    assert mgdvault.get("app/key") == "v"
    assert mgdvault.exists("app/key")
    mgdvault.set_json("app/json", {"a": 1})
    assert mgdvault.get_json("app/json") == {"a": 1}
    assert mgdvault.list_keys() == ["app/json", "app/key"]
    assert mgdvault.list_keys("app") == ["app/json", "app/key"]
    assert mgdvault.delete("app/key") is True
    assert mgdvault.get("app/key", default="d") == "d"
    with pytest.raises(SecretNotFoundError):
        mgdvault.get("app/key")


def test_set_default_vault_overrides_env():
    fake = MemoryVault({"app/key": "fake"})
    mgdvault.set_default_vault(fake)
    assert mgdvault.get("app/key") == "fake"
    mgdvault.reset_default_vault()
    with pytest.raises(VaultConfigurationError):
        mgdvault.get("app/key")


def test_vault_from_env_does_not_cache(monkeypatch):
    first = mgdvault.vault_from_env({settings.ENV_BACKEND: "memory"})
    second = mgdvault.vault_from_env({settings.ENV_BACKEND: "memory"})
    assert first is not second


def test_public_exports():
    for name in mgdvault.__all__:
        assert hasattr(mgdvault, name), name
