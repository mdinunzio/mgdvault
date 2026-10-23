"""A vault stored in a KeePass (``.kdbx``) database via pykeepass.

This is the default backend. One password (or key file) unlocks the vault,
the file works identically on every operating system, and it can be copied
or committed wherever it is needed because it is encrypted at rest.

Performance
-----------
Unlocking a KDBX 4 database runs a deliberately slow key derivation
(Argon2), which costs a few hundred milliseconds. :class:`KeePassVault`
pays that cost once per instance: it caches the open database and the
derived key in memory. Before every operation it stats the file and,
if another process has modified it, re-reads it using the cached derived
key, which takes about a millisecond. Repeated reads are therefore
effectively free, and concurrent writers from other processes are seen
promptly.

Concurrency
-----------
Writes take an inter-process file lock (``<db>.lock`` next to the database)
and re-read the file before modifying it, so several ETL jobs sharing one
vault do not overwrite each other's changes. Reads do not lock: pykeepass
writes to a temporary file and renames it into place, so a reader always
sees a complete old or new file. Use :meth:`KeePassVault.update` for
read-modify-write sequences such as OAuth token refresh; ``get`` followed by
``set`` is a race. A thread lock serialises access within a process.

Layout
------
Key segments map to KeePass groups and the final segment to the entry
title, so ``mgdio/google/personal`` is the entry ``personal`` inside the
group ``mgdio/google``. The secret is the entry's password field. The
database stays fully usable from KeePassXC or any other KeePass client.
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from filelock import FileLock, Timeout
from pykeepass import PyKeePass, create_database
from pykeepass.exceptions import CredentialsError

from mgdvault.base import Vault
from mgdvault.exceptions import (
    VaultConfigurationError,
    VaultCredentialsError,
    VaultLockTimeoutError,
    VaultStorageError,
)
from mgdvault.keys import join_key, split_key
from mgdvault.settings import DEFAULT_LOCK_TIMEOUT

logger = logging.getLogger(__name__)


class KeePassVault(Vault):
    """Vault backed by a KeePass ``.kdbx`` file.

    Args:
        path: Location of the database file.
        password: Master password. May be omitted when ``keyfile`` is given.
        keyfile: Optional KeePass key file used instead of, or together
            with, the password.
        auto_create: Create the database (and parent directories) on first
            use if the file does not exist. Enabled by default so a fresh
            machine needs no setup beyond the environment variables.
        cache: Keep the unlocked database in memory between operations.
            Disabling this forces a re-read on every call; the derived key
            is still cached so this is cheap, but normally unnecessary.
        lock_timeout: Seconds to wait for the write lock held by another
            process before raising
            :class:`~mgdvault.exceptions.VaultLockTimeoutError`.

    Raises:
        VaultConfigurationError: If neither a password nor a key file is
            provided.
    """

    backend_name = "keepass"

    def __init__(
        self,
        path: str | os.PathLike[str],
        password: str | None = None,
        keyfile: str | os.PathLike[str] | None = None,
        auto_create: bool = True,
        cache: bool = True,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
    ) -> None:
        """Create the vault handle. The file is opened lazily on first use."""
        if not password and not keyfile:
            raise VaultConfigurationError(
                "A KeePass vault needs a password and/or a key file."
            )
        self.path = Path(path).expanduser()
        self.keyfile = Path(keyfile).expanduser() if keyfile else None
        self.auto_create = auto_create
        self.cache = cache
        self._password = password or None
        self._kp: PyKeePass | None = None
        self._transformed_key: bytes | None = None
        self._stat: tuple[int, int] | None = None
        self._lock = threading.RLock()
        self.lock_timeout = lock_timeout
        self._file_lock = FileLock(str(self.path) + ".lock", timeout=lock_timeout)

    # -- properties -------------------------------------------------------

    @property
    def file_exists(self) -> bool:
        """Whether the database file currently exists on disk."""
        return self.path.is_file()

    # -- open / reload ----------------------------------------------------

    def _current_stat(self) -> tuple[int, int] | None:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _create(self) -> PyKeePass:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _best_effort_chmod(self.path.parent, 0o700)
        logger.info("Creating new KeePass vault at %s", self.path)
        create_database(
            str(self.path),
            password=self._password,
            keyfile=str(self.keyfile) if self.keyfile else None,
        )
        _best_effort_chmod(self.path, 0o600)
        # create_database() saves (rotating the KDF salt) after deriving the
        # key it reports, so reopen to obtain a derived key that matches the
        # file on disk. This happens once per vault creation.
        return self._open_fresh()

    def _open_fresh(self) -> PyKeePass:
        """Open the file with the password/keyfile (slow path)."""
        if not self.path.exists():
            if not self.auto_create:
                raise VaultStorageError(
                    f"KeePass database not found at {self.path}. Run "
                    "`mgdvault init` or enable auto_create."
                )
            with self._write_lock():
                if self.path.exists():  # another process created it meanwhile
                    return self._open_fresh()
                return self._create()
        try:
            return PyKeePass(
                str(self.path),
                password=self._password,
                keyfile=str(self.keyfile) if self.keyfile else None,
            )
        except CredentialsError as exc:
            raise VaultCredentialsError(
                f"Could not unlock the KeePass database at {self.path}: wrong "
                "password or key file (check MGDVAULT_PASSWORD / MGDVAULT_KEYFILE)."
            ) from exc
        except FileNotFoundError:  # pragma: no cover - race with deletion
            return self._open_fresh()

    def _open_with_cached_key(self) -> PyKeePass:
        """Re-read a changed file using the cached derived key (fast path)."""
        try:
            return PyKeePass(str(self.path), transformed_key=self._transformed_key)
        except Exception:
            # KDF parameters changed (e.g. password rotated in KeePassXC) or
            # the file was replaced; fall back to the slow path.
            logger.debug("Cached key rejected for %s; re-deriving.", self.path)
            return self._open_fresh()

    def _db(self) -> PyKeePass:
        """Return the open database, loading or refreshing it as needed."""
        with self._lock:
            stat = self._current_stat()
            if self._kp is None or self._transformed_key is None:
                self._kp = self._open_fresh()
                self._transformed_key = self._kp.transformed_key
                self._stat = self._current_stat()
            elif stat is None:
                # File vanished; recreate or fail according to policy.
                self._kp = self._open_fresh()
                self._stat = self._current_stat()
            elif stat != self._stat or not self.cache:
                self._kp = self._open_with_cached_key()
                self._transformed_key = self._kp.transformed_key
                self._stat = stat
            return self._kp

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        """Hold the inter-process write lock, failing loudly on timeout."""
        try:
            self._file_lock.acquire()
        except Timeout as exc:
            raise VaultLockTimeoutError(
                f"Timed out after {self.lock_timeout:g}s waiting for the vault "
                f"write lock {self._file_lock.lock_file}. Another process may be "
                "stuck; remove the lock file if it is stale."
            ) from exc
        try:
            yield
        finally:
            self._file_lock.release()

    def reload(self) -> None:
        """Discard the in-memory copy and re-read the file on next access."""
        with self._lock:
            self._stat = None

    def close(self) -> None:
        """Drop the cached database and derived key."""
        with self._lock:
            self._kp = None
            self._transformed_key = None
            self._stat = None

    # -- primitives -------------------------------------------------------

    def _find_entry(self, kp: PyKeePass, segments: list[str]) -> Any:
        entry = kp.find_entries(path=segments)
        return entry

    def _get(self, key: str) -> str | None:
        segments = split_key(key)
        with self._lock:
            entry = self._find_entry(self._db(), segments)
            if entry is None:
                return None
            return entry.password if entry.password is not None else ""

    def _set(self, key: str, value: str) -> None:
        segments = split_key(key)
        with self._lock, self._write_lock():
            kp = self._db()
            entry = self._find_entry(kp, segments)
            if entry is not None:
                entry.password = value
            else:
                group = self._ensure_group(kp, segments[:-1])
                kp.add_entry(group, segments[-1], "", value)
            self._save(kp)

    def _delete(self, key: str) -> bool:
        segments = split_key(key)
        with self._lock, self._write_lock():
            kp = self._db()
            entry = self._find_entry(kp, segments)
            if entry is None:
                return False
            group = entry.group
            kp.delete_entry(entry)
            self._prune_empty_groups(kp, group)
            self._save(kp)
            return True

    def _update(self, key: str, fn: Callable[[str | None], str | None]) -> str | None:
        # Hold the inter-process lock across read, callback and write so
        # concurrent refreshers cannot interleave.
        with self._lock, self._write_lock():
            return super()._update(key, fn)

    def _list(self) -> list[str]:
        with self._lock:
            kp = self._db()
            recycle = kp.recyclebin_group
            keys = []
            for entry in kp.entries:
                if recycle is not None and _in_group(entry, recycle):
                    continue
                keys.append(join_key(list(entry.path)))
            return keys

    # -- helpers ----------------------------------------------------------

    def _ensure_group(self, kp: PyKeePass, segments: list[str]) -> Any:
        group = kp.root_group
        for depth in range(1, len(segments) + 1):
            found = kp.find_groups(path=segments[:depth])
            if found is None:
                found = kp.add_group(group, segments[depth - 1])
            group = found
        return group

    def _prune_empty_groups(self, kp: PyKeePass, group: Any) -> None:
        root = kp.root_group
        recycle = kp.recyclebin_group
        while (
            group is not None
            and group != root
            and group != recycle
            and not group.entries
            and not group.subgroups
        ):
            parent = group.parentgroup
            kp.delete_group(group)
            group = parent

    def _save(self, kp: PyKeePass) -> None:
        try:
            # Passing the derived key keeps the KDF salt stable across saves,
            # so other processes holding a cached key can still fast-reload.
            # Encryption seeds are still rotated on every save.
            kp.save(transformed_key=self._transformed_key)
        except OSError as exc:
            raise VaultStorageError(
                f"Could not write the KeePass database at {self.path}: {exc}"
            ) from exc
        _best_effort_chmod(self.path, 0o600)
        self._stat = self._current_stat()

    def describe_location(self) -> str:
        """Describe the database path."""
        return f"KeePass database at {self.path}"


def _in_group(entry: Any, group: Any) -> bool:
    current = entry.group
    while current is not None:
        if current == group:
            return True
        current = current.parentgroup
    return False


def _best_effort_chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:  # pragma: no cover - exotic filesystems / Windows
        pass
