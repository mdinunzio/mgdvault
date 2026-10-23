"""Shared fixtures.

The autouse fixture strips every ``MGDVAULT_*`` variable and disables the
package's automatic ``.env`` loading, so a developer's repo-local ``.env``
cannot leak into the suite. Tests that exercise ``.env`` discovery opt back
in explicitly.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import mgdvault
from mgdvault import settings
from mgdvault.backends import KeePassVault, MemoryVault

MGDVAULT_VARS = [
    settings.ENV_BACKEND,
    settings.ENV_PASSWORD,
    settings.ENV_KEYFILE,
    settings.ENV_PATH,
    settings.ENV_KEYRING_SERVICE,
    settings.ENV_DOTENV,
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Strip every MGDVAULT_* variable and reset the default vault."""
    for name in list(os.environ):
        if name.startswith("MGDVAULT_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(settings.ENV_DOTENV, "0")
    mgdvault.reset_default_vault()
    yield
    mgdvault.reset_default_vault()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "nested" / "vault.kdbx"


@pytest.fixture
def keepass_vault(db_path: Path) -> KeePassVault:
    return KeePassVault(db_path, password="test-password")


@pytest.fixture
def memory_vault() -> MemoryVault:
    return MemoryVault({"app/a": "1", "app/sub/b": "2", "other/c": "3"})


@pytest.fixture
def keepass_env(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> Path:
    monkeypatch.setenv(settings.ENV_PASSWORD, "test-password")
    monkeypatch.setenv(settings.ENV_PATH, str(db_path))
    return db_path
