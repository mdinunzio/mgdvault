"""Shared fixtures.

The package itself never loads ``.env``; the test suite does, so a repo-local
``.env`` can point opt-in tests at a real vault.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    import dotenv

    dotenv.load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover
    pass

import mgdvault
from mgdvault import settings
from mgdvault.backends import KeePassVault, MemoryVault

MGDVAULT_VARS = [
    settings.ENV_BACKEND,
    settings.ENV_PASSWORD,
    settings.ENV_KEYFILE,
    settings.ENV_PATH,
    settings.ENV_KEYRING_SERVICE,
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Strip every MGDVAULT_* variable and reset the default vault."""
    for name in list(os.environ):
        if name.startswith("MGDVAULT_"):
            monkeypatch.delenv(name, raising=False)
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
