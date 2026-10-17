"""Select only declared MV database/System/map display fields."""
from collections.abc import Iterator
from dataclasses import replace
from pathlib import PurePosixPath
import re

from .json_store import array_value, object_value
from .model import Candidate, Context, JsonPath, JsonValue, Location
from .rules import DATABASE_FIELDS, SYSTEM_ARRAYS, SYSTEM_SCALARS


def candidate(file: str, path: JsonPath, source: str, kind: str, owner: str) -> Candidate:
    return Candidate(source, kind, (Location(file, path, source),), Context(path[:-1], owner))


def term_strings(value: JsonValue, path: JsonPath = ()) -> Iterator[tuple[JsonPath, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from term_strings(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from term_strings(child, path + (index,))


def database_fields(file: str, data: JsonValue) -> Iterator[Candidate]:
    fields = DATABASE_FIELDS.get(PurePosixPath(file).name, ())
    if not fields:
        return
    for index, value in enumerate(array_value(data)):
        if value is None:
            continue
        row = object_value(value)
        owner = str(row.get("name", ""))
        for field in fields:
            text = row.get(field)
            if isinstance(text, str) and text.strip():
                item = candidate(file, (index, field), text, "database_" + field, owner)
                composition = None
                if PurePosixPath(file).name == "Skills.json" and field.startswith("message"):
                    composition = "subject.name + fragment; %1=item.name" if field == "message1" else "fragment; %1=item.name"
                if PurePosixPath(file).name == "States.json" and field.startswith("message"):
                    composition = "battler.name + fragment"
                related = tuple(str(row[k]) for k in fields if k != field and isinstance(row.get(k), str) and row[k])
                yield replace(item, context=replace(item.context, composition=composition, related=related))


def system_fields(file: str, data: JsonValue) -> Iterator[Candidate]:
    row = object_value(data)
    for key in SYSTEM_SCALARS:
        value = row[key]
        if isinstance(value, str) and value.strip():
            item = candidate(file, (key,), value, "system_" + key, key)
            if key == "currencyUnit":
                item = replace(item, context=replace(item.context, composition="currency unit after numeric amount"))
            yield item
    for key in SYSTEM_ARRAYS:
        for index, value in enumerate(array_value(row[key])):
            if isinstance(value, str) and value.strip():
                yield candidate(file, (key, index), value, "system_" + key, key)
    for path, value in term_strings(row["terms"], ("terms",)):
        if value.strip():
            yield candidate(file, path, value, "system_terms", "terms")


def core_fields(file: str, data: JsonValue) -> Iterator[Candidate]:
    name = PurePosixPath(file).name
    yield from database_fields(file, data)
    if name == "System.json":
        yield from system_fields(file, data)
    if re.fullmatch(r"Map\d+\.json", name):
        text = object_value(data)["displayName"]
        if isinstance(text, str) and text.strip():
            yield candidate(file, ("displayName",), text, "map_display_name", name)
