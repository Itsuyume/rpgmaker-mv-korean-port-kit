"""Authenticate the pinned official archive and validate paths before extraction."""

from dataclasses import asdict
from pathlib import Path

from .config import RuntimeSpec
from .shared.archive import inspect_zip, sha256_file
from .shared.native import extract_zip


def validate_runtime_archive(path: Path, spec: RuntimeSpec) -> dict:
    if path.name != spec.runtime_filename or sha256_file(path) != spec.runtime_sha256:
        raise ValueError("NW.js archive does not match the pinned official filename and SHA-256")
    return asdict(inspect_zip(path, path.stem, "nwjs.app", "credits.html"))


def extract_runtime(path: Path, destination: Path) -> Path:
    extract_zip(path, destination)
    app = destination / path.stem / "nwjs.app"
    if not (app / "Contents/MacOS/nwjs").is_file():
        raise ValueError("Official runtime archive does not contain the expected nwjs.app")
    for link in app.rglob("*"):
        if link.is_symlink() and not link.resolve(strict=True).is_relative_to(app.resolve()):
            raise ValueError(f"Extracted runtime link escapes the app: {link.relative_to(app)}")
    return app
