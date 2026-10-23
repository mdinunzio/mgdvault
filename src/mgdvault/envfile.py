"""Discovery and loading of ``.env`` files.

Running ``uv run mgdvault ...`` or a cron job does not load a project's
``.env`` the way an application that calls ``python-dotenv`` does, so the
CLI would otherwise fail with "password not set" in a repo whose
``.env`` plainly holds ``MGDVAULT_PASSWORD``. mgdvault therefore loads a
``.env`` itself, lazily, when the default vault is first resolved and at the
start of every CLI command.

Rules:

* Variables already present in the environment are **never** overridden.
  An exported shell variable or a value injected by CI always wins.
* By default the file is found by walking from the current working
  directory up to the filesystem root and taking the first ``.env``.
* ``MGDVAULT_DOTENV`` changes this: a path loads that exact file, and
  ``0`` / ``false`` / ``off`` / ``none`` disables loading entirely.
* Nothing happens at import time.
"""

from __future__ import annotations

import os
from pathlib import Path

import dotenv

from mgdvault.settings import ENV_DOTENV

_DISABLED_VALUES = {"0", "false", "off", "none", "no"}


def find_env_file(start: str | os.PathLike[str] | None = None) -> Path | None:
    """Return the nearest ``.env`` at or above ``start`` (default: cwd).

    Args:
        start: Directory to begin the upward search from.

    Returns:
        The path of the first ``.env`` found, or ``None``.
    """
    current = Path(start or os.getcwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_env_file(path: str | os.PathLike[str] | None = None) -> Path | None:
    """Load a ``.env`` into ``os.environ`` without overriding existing values.

    Args:
        path: Explicit file to load. When omitted, ``MGDVAULT_DOTENV`` is
            consulted (a path, or a value such as ``0`` to disable), and
            otherwise the nearest ``.env`` above the working directory is
            used.

    Returns:
        The file that was loaded, or ``None`` if loading was disabled or no
        file was found.
    """
    if path is None:
        configured = os.environ.get(ENV_DOTENV, "").strip()
        if configured.lower() in _DISABLED_VALUES:
            return None
        if configured:
            candidate = Path(configured).expanduser()
            if not candidate.is_file():
                return None
        else:
            candidate = find_env_file()
            if candidate is None:
                return None
    else:
        candidate = Path(path).expanduser()
        if not candidate.is_file():
            return None
    dotenv.load_dotenv(candidate, override=False)
    return candidate
