"""Commit prevalidated replacement bytes with source guards and rollback."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.shared.archive import sha256_file
from .paths import source_file


def guarded_commit(root: Path, updates: dict[str, bytes], expected: dict[str, str]) -> None:
    if not updates:
        return
    lock = root / ".localization-write.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        _commit_locked(root, updates, expected)
    finally:
        lock.unlink()


def _commit_locked(root: Path, updates: dict[str, bytes], expected: dict[str, str]) -> None:
    with TemporaryDirectory(prefix=".localization-", dir=root.parent) as folder:
        temporary = Path(folder)
        replacements, backups = prepare(root, updates, expected, temporary)
        committed: list[str] = []
        try:
            for file, replacement in replacements.items():
                target = source_file(root, file)
                if sha256_file(target) != expected[file]:
                    raise ValueError("Target changed during localization: " + file)
                replacement.replace(target)
                committed.append(file)
        except BaseException:
            for file in reversed(committed):
                backups[file].replace(source_file(root, file))
            raise


def prepare(root: Path, updates: dict[str, bytes], expected: dict[str, str], temporary: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    replacements: dict[str, Path] = {}
    backups: dict[str, Path] = {}
    for index, (file, content) in enumerate(updates.items()):
        target = source_file(root, file)
        if file not in expected or sha256_file(target) != expected[file]:
            raise ValueError("Target guard failed before any write: " + file)
        replacement = temporary / (str(index) + ".new")
        backup = temporary / (str(index) + ".old")
        replacement.write_bytes(content)
        backup.write_bytes(target.read_bytes())
        mode = target.stat().st_mode
        replacement.chmod(mode)
        backup.chmod(mode)
        replacements[file], backups[file] = replacement, backup
    return replacements, backups
