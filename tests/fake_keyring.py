"""An in-memory keyring backend so KeyringVault tests never touch the OS."""

from __future__ import annotations

import keyring
import keyring.backend
import keyring.errors

from mgdvault.backends import KeyringVault


class FakeKeyring(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        try:
            del self.store[(service, username)]
        except KeyError:
            raise keyring.errors.PasswordDeleteError(username)


def install_fake_keyring(monkeypatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr(keyring, "get_keyring", lambda: fake)
    monkeypatch.setattr(keyring, "get_password", fake.get_password)
    monkeypatch.setattr(keyring, "set_password", fake.set_password)
    monkeypatch.setattr(keyring, "delete_password", fake.delete_password)
    return fake


def make_keyring_vault(monkeypatch, service: str = "mgdvault-test") -> KeyringVault:
    install_fake_keyring(monkeypatch)
    return KeyringVault(service=service)
