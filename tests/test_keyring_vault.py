from __future__ import annotations

import keyring
import keyring.backends.fail
import pytest

from mgdvault.backends import KeyringVault
from mgdvault.backends.keyring import INDEX_USERNAME
from mgdvault.exceptions import BackendUnavailableError

from .fake_keyring import install_fake_keyring


def test_entries_land_under_service_with_key_as_username(monkeypatch):
    fake = install_fake_keyring(monkeypatch)
    vault = KeyringVault(service="svc")
    vault.set("app/token", "t")
    assert fake.store[("svc", "app/token")] == "t"
    assert ("svc", INDEX_USERNAME) in fake.store


def test_index_tracks_keys(monkeypatch):
    install_fake_keyring(monkeypatch)
    vault = KeyringVault(service="svc")
    vault.set("a/1", "x")
    vault.set("b/2", "y")
    vault.set("a/1", "z")
    assert vault.list_keys() == ["a/1", "b/2"]
    vault.delete("a/1")
    assert vault.list_keys() == ["b/2"]


def test_index_is_not_listed_as_a_secret(monkeypatch):
    install_fake_keyring(monkeypatch)
    vault = KeyringVault(service="svc")
    vault.set("a/1", "x")
    assert INDEX_USERNAME not in vault.list_keys()


def test_corrupt_index_is_tolerated(monkeypatch):
    fake = install_fake_keyring(monkeypatch)
    vault = KeyringVault(service="svc")
    fake.store[("svc", INDEX_USERNAME)] = "not json"
    assert vault.list_keys() == []
    vault.set("a/1", "x")
    assert vault.list_keys() == ["a/1"]


def test_fail_backend_raises_unavailable(monkeypatch):
    monkeypatch.setattr(keyring, "get_keyring", lambda: keyring.backends.fail.Keyring())
    with pytest.raises(BackendUnavailableError):
        KeyringVault()


def test_describe_location_mentions_service(monkeypatch):
    install_fake_keyring(monkeypatch)
    assert "'svc'" in KeyringVault(service="svc").describe_location()
