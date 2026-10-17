"""Enumerate MV event lists by schema, excluding unrelated HUD/custom JSON."""
from collections.abc import Iterator
from pathlib import PurePosixPath
import re

from .json_store import array_value, object_value, string_value
from .model import EventList, JsonObject, JsonPath, JsonValue


def command_list(file: str, path: JsonPath, owner: str, value: JsonValue) -> EventList:
    commands = tuple(object_value(v) for v in array_value(value))
    return EventList(file, path, owner, commands)


def pages(file: str, prefix: JsonPath, row: JsonObject) -> Iterator[EventList]:
    owner = string_value(row["name"])
    for index, page in enumerate(array_value(row["pages"])):
        item = object_value(page)
        path = prefix + ("pages", index, "list")
        yield command_list(file, path, owner, item["list"])


def event_lists(file: str, data: JsonValue) -> Iterator[EventList]:
    name = PurePosixPath(file).name
    if re.fullmatch(r"Map\d+\.json", name):
        for index, value in enumerate(array_value(object_value(data)["events"])):
            if value is not None:
                yield from pages(file, ("events", index), object_value(value))
    elif name == "CommonEvents.json":
        for index, value in enumerate(array_value(data)):
            if value is not None:
                row = object_value(value)
                yield command_list(file, (index, "list"), string_value(row["name"]), row["list"])
    elif name == "Troops.json":
        for index, value in enumerate(array_value(data)):
            if value is not None:
                yield from pages(file, (index,), object_value(value))
