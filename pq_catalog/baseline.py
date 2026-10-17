"""Read guarded source bytes and require a separate prepared target copy."""
from pathlib import Path

from runtime.shared.archive import sha256_file
from .json_store import digest_bytes
from .paths import source_file


def separate_roots(source: Path, target: Path) -> None:
    original, output = source.resolve(strict=True), target.resolve(strict=True)
    if not original.is_dir() or not output.is_dir():
        raise ValueError("Source and target must be existing www directories.")
    if original.is_relative_to(output) or output.is_relative_to(original):
        raise ValueError("Source and target www directories must not overlap.")


def guarded_files(source: Path, target: Path, hashes: dict[str, str]) -> dict[str, bytes]:
    separate_roots(source, target)
    documents: dict[str, bytes] = {}
    for file, expected in hashes.items():
        original, output = source_file(source, file), source_file(target, file)
        content = original.read_bytes()
        if digest_bytes(content) != expected or sha256_file(output) != expected:
            raise ValueError("Source/target baseline differs from catalog: " + file)
        documents[file] = content
    return documents
