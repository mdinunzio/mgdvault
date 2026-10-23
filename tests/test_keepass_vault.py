from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from pykeepass import PyKeePass

from mgdvault.backends import KeePassVault
from mgdvault.exceptions import (
    VaultConfigurationError,
    VaultCredentialsError,
    VaultStorageError,
)


def test_requires_password_or_keyfile(tmp_path):
    with pytest.raises(VaultConfigurationError):
        KeePassVault(tmp_path / "v.kdbx")


def test_auto_creates_file_and_parents(keepass_vault, db_path):
    assert not keepass_vault.file_exists
    keepass_vault.set("app/key", "v")
    assert keepass_vault.file_exists
    assert db_path.parent.is_dir()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_file_permissions_locked_down(keepass_vault, db_path):
    keepass_vault.set("app/key", "v")
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(db_path.parent.stat().st_mode) == 0o700


def test_no_auto_create_raises(tmp_path):
    vault = KeePassVault(tmp_path / "v.kdbx", password="pw", auto_create=False)
    with pytest.raises(VaultStorageError):
        vault.get("a/b", default=None)


def test_wrong_password(keepass_vault, db_path):
    keepass_vault.set("app/key", "v")
    other = KeePassVault(db_path, password="wrong")
    with pytest.raises(VaultCredentialsError):
        other.get("app/key")


def test_keyfile_only(tmp_path):
    keyfile = tmp_path / "key.bin"
    keyfile.write_bytes(os.urandom(32))
    vault = KeePassVault(tmp_path / "v.kdbx", keyfile=keyfile)
    vault.set("a/b", "c")
    again = KeePassVault(tmp_path / "v.kdbx", keyfile=keyfile)
    assert again.get("a/b") == "c"


def test_layout_matches_keepass_groups(keepass_vault, db_path):
    keepass_vault.set("mgdio/google/personal", "tok")
    keepass_vault.set("top", "flat")
    kp = PyKeePass(str(db_path), password="test-password")
    entry = kp.find_entries(path=["mgdio", "google", "personal"])
    assert entry.password == "tok"
    assert kp.find_groups(path=["mgdio", "google"]) is not None
    assert kp.find_entries(path=["top"]).password == "flat"


def test_delete_prunes_empty_groups(keepass_vault, db_path):
    keepass_vault.set("a/b/c", "1")
    keepass_vault.set("a/d", "2")
    keepass_vault.delete("a/b/c")
    kp = PyKeePass(str(db_path), password="test-password")
    assert kp.find_groups(path=["a", "b"]) is None
    assert kp.find_groups(path=["a"]) is not None
    keepass_vault.delete("a/d")
    kp = PyKeePass(str(db_path), password="test-password")
    assert kp.find_groups(path=["a"]) is None
    assert keepass_vault.list_keys() == []


def test_reads_are_cached(keepass_vault, monkeypatch):
    keepass_vault.set("a/b", "1")
    opens = []
    original = PyKeePass.__init__

    def counting_init(self, *args, **kwargs):
        opens.append(kwargs)
        original(self, *args, **kwargs)

    monkeypatch.setattr(PyKeePass, "__init__", counting_init)
    for _ in range(50):
        assert keepass_vault.get("a/b") == "1"
    assert opens == []


def test_sees_changes_from_another_process(keepass_vault, db_path):
    """A second handle stands in for another process writing the file."""
    keepass_vault.set("a/b", "1")
    assert keepass_vault.get("a/b") == "1"
    writer = KeePassVault(db_path, password="test-password")
    writer.set("a/b", "2")
    writer.set("a/new", "3")
    assert keepass_vault.get("a/b") == "2"
    assert keepass_vault.list_keys() == ["a/b", "a/new"]


def test_reload_uses_cached_key_not_password(keepass_vault, db_path, monkeypatch):
    keepass_vault.set("a/b", "1")
    KeePassVault(db_path, password="test-password").set("a/b", "2")
    seen = []
    original = PyKeePass.__init__

    def spy(self, *args, **kwargs):
        seen.append(kwargs)
        original(self, *args, **kwargs)

    monkeypatch.setattr(PyKeePass, "__init__", spy)
    assert keepass_vault.get("a/b") == "2"
    assert len(seen) == 1
    assert seen[0].get("transformed_key") is not None
    assert seen[0].get("password") is None


def test_write_after_external_change_does_not_clobber(keepass_vault, db_path):
    keepass_vault.set("a/b", "1")
    KeePassVault(db_path, password="test-password").set("a/other", "x")
    keepass_vault.set("a/b", "2")
    fresh = KeePassVault(db_path, password="test-password")
    assert fresh.get("a/other") == "x"
    assert fresh.get("a/b") == "2"


def test_cache_disabled_still_works(db_path):
    vault = KeePassVault(db_path, password="pw", cache=False)
    vault.set("a/b", "1")
    assert vault.get("a/b") == "1"
    assert vault.list_keys() == ["a/b"]


def test_close_and_reopen(keepass_vault):
    keepass_vault.set("a/b", "1")
    keepass_vault.close()
    assert keepass_vault.get("a/b") == "1"
    keepass_vault.reload()
    assert keepass_vault.get("a/b") == "1"


def test_recreated_when_file_removed(keepass_vault, db_path):
    keepass_vault.set("a/b", "1")
    db_path.unlink()
    assert keepass_vault.get("a/b", default=None) is None
    assert db_path.exists()


def test_expands_user(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    vault = KeePassVault("~/v.kdbx", password="pw")
    assert vault.path == Path(tmp_path / "v.kdbx")


def test_lock_file_sits_next_to_database(keepass_vault, db_path):
    keepass_vault.set("a/b", "1")
    assert Path(str(db_path) + ".lock").parent == db_path.parent
