"""Validate relative source paths and JSON paths before filesystem access."""
from pathlib import Path, PurePosixPath

from .json_store import array_value, string_value
from .model import JsonPath, JsonValue


def relative_file(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or "\\" in value or "\0" in value:
        raise ValueError("Expected a safe www-relative file path.")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("Relative path traversal or empty component is forbidden.")
    return value


def source_file(root: Path, value: str) -> Path:
    result = root.joinpath(*PurePosixPath(relative_file(value)).parts)
    if not result.resolve().is_relative_to(root.resolve()) or result.is_symlink():
        raise ValueError("Source path escapes its root or is a symlink.")
    return result


def json_path(value: JsonValue) -> JsonPath:
    result: list[str | int] = []
    for item in array_value(value):
        if isinstance(item, str):
            result.append(string_value(item))
        elif type(item) is int and item >= 0:
            result.append(item)
        else:
            raise ValueError("JSON paths require string keys or nonnegative integer indices.")
    if not result:
        raise ValueError("A selected string cannot replace a document root.")
    return tuple(result)
