"""Explicit catalog shapes; no runtime or model-client dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

JsonPath: TypeAlias = tuple[str | int, ...]
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True)
class Location:
    file: str
    path: JsonPath
    source: str
    role: str = "primary"


@dataclass(frozen=True)
class Context:
    owner_path: JsonPath
    owner_name: str
    command_index: int | None = None
    face_name: str | None = None
    choices: tuple[str, ...] = ()
    composition: str | None = None
    related: tuple[str, ...] = ()
    nearby: tuple[tuple[int, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class Candidate:
    source: str
    kind: str
    locations: tuple[Location, ...]
    context: Context


@dataclass(frozen=True)
class EventList:
    file: str
    path: JsonPath
    owner_name: str
    commands: tuple[JsonObject, ...]


@dataclass(frozen=True)
class PreparedUpdates:
    updates: dict[str, bytes]
    expected_hashes: dict[str, str]
    translated_units: int
    changed_leaves: int
