"""Save-file exclusion and safe archive symlink resolution."""

import os
from pathlib import Path, PurePosixPath


SAVE_DIRECTORIES = frozenset({"save", "saves", "savedata", "savegames", "savedgames"})
PERSISTENT_FILES = frozenset({"persistent", "persistent.new", "persistent.old", "persistent.bak"})


def check_save_name(name: str, is_directory: bool, location: str) -> None:
    lowered = name.casefold()
    directory = is_directory and lowered in SAVE_DIRECTORIES
    filename = lowered in PERSISTENT_FILES or lowered.endswith((".save", ".sav"))
    backup = lowered.endswith((".save.new", ".save.bak", ".save.old", ".sav.bak"))
    if directory or filename or backup:
        raise ValueError(f"Possible personal save data: {location}")


def check_tree(app: Path) -> None:
    for root, directories, filenames in os.walk(app, followlinks=False, onerror=_walk_error):
        _check_children(Path(root), directories, True, app)
        _check_children(Path(root), filenames, False, app)


def _walk_error(error: OSError) -> None:
    raise error


def _check_children(root: Path, names: list[str], directories: bool, app: Path) -> None:
    for name in names:
        path = root / name
        check_save_name(name, directories, str(path.relative_to(app)))
        _check_local_link(path, app)


def _check_local_link(path: Path, app: Path) -> None:
    if not path.is_symlink():
        return
    target = os.readlink(path)
    if Path(target).is_absolute() or not path.resolve(strict=True).is_relative_to(app):
        raise ValueError(f"App symlink must stay relative and inside the app: {path.relative_to(app)}")


def check_links(links: dict[PurePosixPath, str], members: set[PurePosixPath]) -> None:
    for member in members:
        if any(parent in links for parent in member.parents):
            raise ValueError(f"ZIP member descends through a symlink: {member}")
    for link, target in links.items():
        if not target or target.startswith("/") or "\\" in target or "\0" in target:
            raise ValueError(f"Unsafe ZIP symlink target: {link}")
        _resolve_link(list(link.parent.parts) + target.split("/"), links)


def _resolve_link(pending: list[str], links: dict[PurePosixPath, str]) -> None:
    resolved: list[str] = []
    traversals = 0
    while pending:
        part, *pending = pending
        if part in {"", "."}:
            continue
        if part == "..":
            _pop_parent(resolved)
            continue
        resolved.append(part)
        target = links.get(PurePosixPath(*resolved))
        if target is None:
            continue
        traversals += 1
        if traversals > 40:
            raise ValueError("ZIP symlink cycle or excessive chain")
        resolved.pop()
        pending = target.split("/") + pending


def _pop_parent(resolved: list[str]) -> None:
    if len(resolved) <= 1:
        raise ValueError("ZIP symlink escapes the release folder")
    resolved.pop()
