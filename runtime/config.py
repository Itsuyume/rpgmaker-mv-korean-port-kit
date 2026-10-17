"""The checked-in runtime lock is the only packaging configuration."""

from dataclasses import dataclass, fields
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class RuntimeSpec:
    release: str
    runtime_filename: str
    runtime_sha256: str
    runtime_url: str
    checksums_url: str
    package_name: str
    bundle_id: str
    display_name: str
    game_version: str
    font_filename: str
    font_sha256: str
    font_license_sha256: str


def load_spec(path: Path) -> RuntimeSpec:
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = {field.name for field in fields(RuntimeSpec)}
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("Runtime lock fields do not match the configuration schema")
    if any(not isinstance(value, str) or not value for value in data.values()):
        raise ValueError("Runtime lock values must be nonempty strings")
    spec = RuntimeSpec(**data)
    filename = f"nwjs-v{spec.release}-osx-arm64.zip"
    if spec.runtime_filename != filename or not re.fullmatch(r"[0-9a-f]{64}", spec.runtime_sha256):
        raise ValueError("Runtime archive filename or SHA-256 is invalid")
    if not re.fullmatch(r"[a-z0-9._-]+", spec.package_name):
        raise ValueError("NW.js profile name is invalid")
    for digest in (spec.font_sha256, spec.font_license_sha256):
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Font dependency SHA-256 is invalid")
    if spec.font_filename != "NotoSansCJKkr-Regular.otf":
        raise ValueError("Expected the retained Noto Sans CJK KR font")
    return spec
