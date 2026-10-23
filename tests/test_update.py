"""update(): atomic read-modify-write, including real multi-process contention."""

from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

import mgdvault
from mgdvault.backends import KeePassVault, MemoryVault
from mgdvault.exceptions import VaultLockTimeoutError

from .fake_keyring import make_keyring_vault


@pytest.fixture(params=["memory", "keepass", "keyring"])
def vault(request, tmp_path, monkeypatch):
    if request.param == "memory":
        return MemoryVault()
    if request.param == "keepass":
        return KeePassVault(tmp_path / "v.kdbx", password="pw")
    return make_keyring_vault(monkeypatch)


def test_update_creates_modifies_and_deletes(vault):
    assert vault.update("app/n", lambda cur: "1" if cur is None else cur) == "1"
    assert vault.get("app/n") == "1"
    assert vault.update("app/n", lambda cur: str(int(cur) + 1)) == "2"
    assert vault.get("app/n") == "2"
    assert vault.update("app/n", lambda cur: None) is None
    assert not vault.exists("app/n")
    assert vault.update("app/n", lambda cur: None) is None


def test_update_unchanged_value_does_not_write(vault, monkeypatch):
    vault.set("app/n", "same")
    calls = []
    monkeypatch.setattr(vault, "_set", lambda k, v: calls.append((k, v)))
    assert vault.update("app/n", lambda cur: cur) == "same"
    assert calls == []


def test_update_rejects_non_string(vault):
    with pytest.raises(TypeError):
        vault.update("app/n", lambda cur: 5)  # type: ignore[return-value]


def test_functional_update(keepass_env):
    mgdvault.update("app/n", lambda cur: "x")
    assert mgdvault.get("app/n") == "x"


def _increment_many(path: str, times: int) -> None:
    vault = KeePassVault(path, password="pw")
    for _ in range(times):
        vault.update("counter", lambda cur: str(int(cur or 0) + 1))


def test_concurrent_updates_from_real_processes(tmp_path: Path):
    path = tmp_path / "shared.kdbx"
    KeePassVault(path, password="pw").set("counter", "0")
    workers, per_worker = 4, 8
    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(target=_increment_many, args=(str(path), per_worker))
        for _ in range(workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=180)
        assert p.exitcode == 0
    assert KeePassVault(path, password="pw").get("counter") == str(workers * per_worker)


def test_lock_timeout_is_a_clear_error(tmp_path: Path):
    path = tmp_path / "v.kdbx"
    holder = KeePassVault(path, password="pw", lock_timeout=0.2)
    holder.set("a/b", "1")
    waiter = KeePassVault(path, password="pw", lock_timeout=0.2)
    holder._file_lock.acquire()
    try:
        with pytest.raises(VaultLockTimeoutError) as exc:
            waiter.set("a/b", "2")
        assert ".lock" in str(exc.value)
        # reads never need the lock
        assert waiter.get("a/b") == "1"
    finally:
        holder._file_lock.release()
    waiter.set("a/b", "2")
    assert holder.get("a/b") == "2"


def test_lock_timeout_from_env(monkeypatch, keepass_env):
    monkeypatch.setenv("MGDVAULT_LOCK_TIMEOUT", "2.5")
    assert mgdvault.default_vault().lock_timeout == 2.5
    mgdvault.reset_default_vault()
    monkeypatch.setenv("MGDVAULT_LOCK_TIMEOUT", "soon")
    with pytest.raises(mgdvault.VaultConfigurationError):
        mgdvault.default_vault()
