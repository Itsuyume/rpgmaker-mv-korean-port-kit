"""Strict JSON and explicit paths at the external-data boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4
from typing import NoReturn
import math

from .model import JsonObject, JsonPath, JsonValue


def reject_duplicates(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value: str) -> NoReturn:
    raise ValueError("Non-JSON numeric constant: " + value)


def decode_json(text: str) -> JsonValue:
    value: object = json.loads(text, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    return json_value(value)


def read_json(path: Path) -> JsonValue:
    return decode_json(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def object_value(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object.")
    return value


def array_value(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError("Expected a JSON array.")
    return value


def string_value(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected a JSON string.")
    return value


def int_value(value: JsonValue) -> int:
    if type(value) is not int:
        raise TypeError("Expected a JSON integer.")
    return value


def get_path(value: JsonValue, path: JsonPath) -> JsonValue:
    current = value
    for key in path:
        if isinstance(key, str):
            current = object_value(current)[key]
        else:
            current = array_value(current)[key]
    return current


def set_path(value: JsonValue, path: JsonPath, target: str) -> None:
    if not path:
        raise ValueError("Replacing the document root is forbidden.")
    parent, key = get_path(value, path[:-1]), path[-1]
    if isinstance(key, str):
        object_value(parent)[key] = target
    else:
        array_value(parent)[key] = target


def decode_prefix(text: str, start: int) -> tuple[JsonValue, int]:
    decoder = json.JSONDecoder(object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    value, end = decoder.raw_decode(text, start)
    return json_value(value), end


def json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite JSON number.")
        return value
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        result: JsonObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings.")
            result[key] = json_value(item)
        return result
    raise TypeError("Unexpected value at the JSON decoder boundary.")
