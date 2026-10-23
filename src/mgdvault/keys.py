"""Key naming rules shared by every backend.

A key is a slash-separated path such as ``mgdio/google/personal``. Each
segment may contain ASCII letters, digits, ``_``, ``-`` and ``.``. The path
form lets a single vault be shared by many applications on one machine
without collisions: by convention the first segment is the application name.
"""

from __future__ import annotations

import re

from mgdvault.exceptions import InvalidKeyError

SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
"""Pattern every path segment must match."""

SEPARATOR = "/"
"""Character separating key segments."""


def split_key(key: str) -> list[str]:
    """Validate ``key`` and return its path segments.

    Args:
        key: The secret key, for example ``"mgdio/google/personal"``.

    Returns:
        The list of segments, for example ``["mgdio", "google", "personal"]``.

    Raises:
        InvalidKeyError: If the key is empty, has empty segments, or contains
            characters outside the allowed set.
    """
    if not isinstance(key, str):
        raise InvalidKeyError(f"Key must be a str, got {type(key).__name__}.")
    if not key:
        raise InvalidKeyError("Key must not be empty.")
    segments = key.split(SEPARATOR)
    for segment in segments:
        if not segment:
            raise InvalidKeyError(
                f"Key {key!r} has an empty segment; keys must not start or end "
                f"with '/' or contain '//'."
            )
        if not SEGMENT_RE.match(segment):
            raise InvalidKeyError(
                f"Key segment {segment!r} in {key!r} is invalid. Segments may "
                "contain letters, digits, '_', '-' and '.', and must start "
                "with a letter, digit or '_'."
            )
    return segments


def validate_key(key: str) -> str:
    """Validate ``key`` and return it unchanged.

    Args:
        key: The secret key to validate.

    Returns:
        The same key, for fluent use.

    Raises:
        InvalidKeyError: If the key violates the naming rules.
    """
    split_key(key)
    return key


def join_key(segments: list[str]) -> str:
    """Join path segments into a key string.

    Args:
        segments: Segments previously produced by :func:`split_key`.

    Returns:
        The joined key.
    """
    return SEPARATOR.join(segments)


def matches_prefix(key: str, prefix: str | None) -> bool:
    """Return whether ``key`` lives under the namespace ``prefix``.

    A prefix matches the key itself and every key below it, so ``"mgdio"``
    matches ``"mgdio"`` and ``"mgdio/google/personal"`` but not
    ``"mgdio2/token"``.

    Args:
        key: A full secret key.
        prefix: A namespace prefix, or ``None`` to match everything.

    Returns:
        True if the key is within the prefix.
    """
    if prefix is None or prefix == "":
        return True
    prefix = prefix.rstrip(SEPARATOR)
    return key == prefix or key.startswith(prefix + SEPARATOR)
