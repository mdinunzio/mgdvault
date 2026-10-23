"""Claude Code skills bundled with mgdvault.

Each subdirectory of this package holding a ``SKILL.md`` is a skill. They
are installed into ``.claude/skills/`` (project) or ``~/.claude/skills/``
(global) by ``mgdvault install-skill``.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator, NamedTuple


class InstallResult(NamedTuple):
    """Outcome of installing one skill."""

    name: str
    """Skill directory name."""

    target: Path
    """Where the skill was (or would have been) written."""

    status: str
    """``"installed"``, ``"updated"`` or ``"skipped"``."""


@contextmanager
def iter_skill_dirs() -> Iterator[list[Path]]:
    """Yield the bundled skill directories as real filesystem paths.

    Works whether the package is installed from a wheel or a zip; the
    context manager keeps any temporary extraction alive while in use.

    Yields:
        Sorted list of skill directories, each containing ``SKILL.md``.
    """
    root = resources.files(__package__)
    with resources.as_file(root) as root_path:
        dirs = sorted(
            p
            for p in Path(root_path).iterdir()
            if p.is_dir() and (p / "SKILL.md").is_file()
        )
        yield dirs


def skill_names() -> list[str]:
    """Return the names of the bundled skills.

    Returns:
        Sorted skill directory names.
    """
    with iter_skill_dirs() as dirs:
        return [d.name for d in dirs]


def read_description(skill_dir: Path) -> str:
    """Return the ``description`` from a skill's front matter, or ``""``.

    Args:
        skill_dir: Directory containing ``SKILL.md``.

    Returns:
        The description text.
    """
    try:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    if not text.startswith("---"):
        return ""
    front = text.split("---", 2)[1]
    for line in front.splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def install_skills(
    target_root: Path, force: bool = False, only: list[str] | None = None
) -> list[InstallResult]:
    """Copy the bundled skills into ``target_root``.

    Args:
        target_root: Skills directory, e.g. ``~/.claude/skills``.
        force: Overwrite skills that already exist there.
        only: Restrict to these skill names; default all.

    Returns:
        One :class:`InstallResult` per skill considered.

    Raises:
        ValueError: If ``only`` names an unknown skill.
    """
    results: list[InstallResult] = []
    with iter_skill_dirs() as dirs:
        known = {d.name: d for d in dirs}
        if only:
            unknown = sorted(set(only) - set(known))
            if unknown:
                raise ValueError(
                    f"Unknown skill(s): {', '.join(unknown)}. "
                    f"Available: {', '.join(sorted(known))}"
                )
            dirs = [known[n] for n in only]
        target_root.mkdir(parents=True, exist_ok=True)
        for src in dirs:
            dest = target_root / src.name
            if dest.exists():
                if not force:
                    results.append(InstallResult(src.name, dest, "skipped"))
                    continue
                shutil.rmtree(dest)
                shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
                results.append(InstallResult(src.name, dest, "updated"))
            else:
                shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
                results.append(InstallResult(src.name, dest, "installed"))
    return results
