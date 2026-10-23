"""Behaviour every backend must share, run against each writable backend."""

from __future__ import annotations

import json

import pytest

from mgdvault.backends import KeePassVault, MemoryVault
from mgdvault.exceptions import InvalidKeyError, SecretNotFoundError

from .fake_keyring import make_keyring_vault


@pytest.fixture(params=["memory", "keepass", "keyring"])
def vault(request, tmp_path, monkeypatch):
    if request.param == "memory":
        return MemoryVault()
    if request.param == "keepass":
        return KeePassVault(tmp_path / "v.kdbx", password="pw")
    return make_keyring_vault(monkeypatch)


def test_roundtrip(vault):
    vault.set("app/key", "value")
    assert vault.get("app/key") == "value"
    assert vault.exists("app/key")
    assert "app/key" in vault
    assert len(vault) == 1


def test_overwrite(vault):
    vault.set("app/key", "one")
    vault.set("app/key", "two")
    assert vault.get("app/key") == "two"
    assert vault.list_keys() == ["app/key"]


def test_missing_raises_without_default(vault):
    with pytest.raises(SecretNotFoundError) as exc:
        vault.get("app/missing")
    assert exc.value.key == "app/missing"
    assert "app/missing" in str(exc.value)
    assert isinstance(exc.value, KeyError)


def test_missing_returns_default(vault):
    assert vault.get("app/missing", default=None) is None
    assert vault.get("app/missing", "fallback") == "fallback"
    assert not vault.exists("app/missing")
    assert "app/missing" not in vault


def test_delete(vault):
    vault.set("app/key", "v")
    assert vault.delete("app/key") is True
    assert vault.delete("app/key") is False
    assert not vault.exists("app/key")
    with pytest.raises(SecretNotFoundError):
        vault.delete("app/key", missing_ok=False)


def test_list_prefix_and_sorting(vault):
    for k in ["b/x", "a/y", "a/sub/z", "ab/w"]:
        vault.set(k, k)
    assert vault.list_keys() == ["a/sub/z", "a/y", "ab/w", "b/x"]
    assert vault.list_keys("a") == ["a/sub/z", "a/y"]
    assert vault.list_keys("a/sub") == ["a/sub/z"]
    assert vault.list_keys("nope") == []
    assert list(vault) == vault.list_keys()


def test_json_helpers(vault):
    payload = {"token": "t", "scopes": ["a", "b"], "n": 1}
    vault.set_json("app/json", payload)
    assert vault.get_json("app/json") == payload
    assert json.loads(vault.get("app/json")) == payload
    assert vault.get_json("app/absent", default={}) == {}
    with pytest.raises(SecretNotFoundError):
        vault.get_json("app/absent")


def test_rejects_non_string_value(vault):
    with pytest.raises(TypeError):
        vault.set("app/key", 123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        vault.set("app/key", {"a": 1})  # type: ignore[arg-type]


def test_invalid_keys_rejected_everywhere(vault):
    for method in (vault.get, vault.exists, vault.delete):
        with pytest.raises(InvalidKeyError):
            method("bad key")
    with pytest.raises(InvalidKeyError):
        vault.set("", "v")


def test_unicode_and_multiline_values(vault):
    value = "pässwörd\nline2\ttab 🔑"
    vault.set("app/uni", value)
    assert vault.get("app/uni") == value


def test_repr_has_no_secret(vault):
    vault.set("app/key", "SUPERSECRET")
    assert "SUPERSECRET" not in repr(vault)
    assert "SUPERSECRET" not in vault.describe_location()
