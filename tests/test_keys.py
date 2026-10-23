import pytest

from mgdvault.exceptions import InvalidKeyError
from mgdvault.keys import join_key, matches_prefix, split_key, validate_key


@pytest.mark.parametrize(
    "key, segments",
    [
        ("a", ["a"]),
        ("mgdio/google/personal", ["mgdio", "google", "personal"]),
        ("x-y.z_1/B2", ["x-y.z_1", "B2"]),
        ("_hidden", ["_hidden"]),
    ],
)
def test_split_valid(key, segments):
    assert split_key(key) == segments
    assert validate_key(key) == key
    assert join_key(segments) == key


@pytest.mark.parametrize(
    "key", ["", "/a", "a/", "a//b", "a b", "a/b!", "-lead", ".lead", "a\\b", 123]
)
def test_split_invalid(key):
    with pytest.raises(InvalidKeyError):
        split_key(key)


def test_invalid_key_is_value_error():
    with pytest.raises(ValueError):
        validate_key("bad key")


@pytest.mark.parametrize(
    "key, prefix, expected",
    [
        ("mgdio/google/x", None, True),
        ("mgdio/google/x", "", True),
        ("mgdio/google/x", "mgdio", True),
        ("mgdio/google/x", "mgdio/", True),
        ("mgdio/google/x", "mgdio/google", True),
        ("mgdio", "mgdio", True),
        ("mgdio2/x", "mgdio", False),
        ("other/mgdio/x", "mgdio", False),
    ],
)
def test_matches_prefix(key, prefix, expected):
    assert matches_prefix(key, prefix) is expected
