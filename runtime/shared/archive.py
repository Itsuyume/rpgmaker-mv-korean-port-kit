"""Inspect ZIP paths and payloads before allowing extraction."""

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .hygiene import check_links, check_save_name


@dataclass(frozen=True)
class ArchiveFacts:
    entries: int
    uncompressed_bytes: int
    bytes: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _member(info: zipfile.ZipInfo, folder: str, allowed: set[str]) -> PurePosixPath:
    raw = info.orig_filename.rstrip("/")
    parts = raw.split("/")
    if "\\" in raw or "\0" in raw or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Unsafe ZIP member path: {info.filename}")
    if parts[0] != folder or (len(parts) > 1 and parts[1] not in allowed):
        raise ValueError(f"ZIP member is outside the expected release layout: {info.filename}")
    if len(parts) == 1 and not info.is_dir():
        raise ValueError("ZIP release root must be a directory")
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in {0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK}:
        raise ValueError(f"Unsupported ZIP member type: {info.filename}")
    _check_save_parts(parts, info.is_dir())
    return PurePosixPath(*parts)


def _check_save_parts(parts: list[str], directory: bool) -> None:
    for index, name in enumerate(parts):
        check_save_name(name, directory or index < len(parts) - 1, "/".join(parts))


def _inspect_members(archive: zipfile.ZipFile, folder: str, allowed: set[str]) -> int:
    members: set[PurePosixPath] = set()
    links: dict[PurePosixPath, str] = {}
    total_bytes = 0
    for info in archive.infolist():
        member = _member(info, folder, allowed)
        if member in members:
            raise ValueError(f"Duplicate ZIP member: {member}")
        members.add(member)
        total_bytes += info.file_size
        if stat.S_ISLNK(info.external_attr >> 16):
            links[member] = archive.read(info).decode("utf-8")
    check_links(links, members)
    if not any(len(member.parts) > 2 for member in members):
        raise ValueError("ZIP contains no app contents")
    return total_bytes


def inspect_zip(path: Path, folder: str, app: str, readme: str) -> ArchiveFacts:
    with zipfile.ZipFile(path, metadata_encoding="utf-8") as archive:
        total = _inspect_members(archive, folder, {app, readme})
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC check failed: {bad}")
        count = len(archive.infolist())
    return ArchiveFacts(count, total, path.stat().st_size, sha256_file(path))
