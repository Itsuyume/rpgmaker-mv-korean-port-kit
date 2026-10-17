"""Typed audited display selectors; reject unknown codecs and unsafe paths."""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .json_store import array_value, digest_text, int_value, object_value, read_json, string_value
from .model import JsonObject, JsonPath, JsonValue
from .paths import json_path, relative_file

Codec = Literal["raw", "json", "json-string", "js-expression"]
DocumentCodec = Literal["plugins-array", "js-literals", "js-template-literal"]


@dataclass(frozen=True)
class Step:
    path: JsonPath
    codec: Codec


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    unit: str
    quote: str


@dataclass(frozen=True)
class Target:
    file: str
    file_sha256: str
    document_codec: DocumentCodec
    source: str
    source_sha256: str
    kind: str
    steps: tuple[Step, ...]
    span: Span | None
    literal_sha256: str | None
    expression_sha256: str | None
    plugin_index: int | None
    plugin_name: str | None
    expected_status: bool | None
    expressions: tuple[str, ...]
    context: JsonObject


def step(value: JsonValue) -> Step:
    row = object_value(value)
    codec = string_value(row["codec"])
    if codec == "raw": return Step(json_path(row["path"]), "raw")
    if codec == "json": return Step(json_path(row["path"]), "json")
    if codec == "json-string": return Step(json_path(row["path"]), "json-string")
    if codec == "js-expression": return Step(json_path(row["path"]), "js-expression")
    raise ValueError("Unsupported nested display codec: " + codec)


def span(value: JsonValue) -> Span:
    row = object_value(value)
    start, end = int_value(row["start"]), int_value(row["end"])
    if start < 0 or end <= start:
        raise ValueError("Invalid audited JS byte span.")
    quote = string_value(row["quote"])
    if quote not in {"\"", "'", "`"}:
        raise ValueError("Unsupported audited JS quote.")
    return Span(start, end, string_value(row["unit"]), quote)


def optional_string(row: JsonObject, key: str) -> str | None:
    return string_value(row[key]) if key in row else None


def target(value: JsonValue) -> Target:
    row = object_value(value)
    codec = document_codec(row["document_codec"])
    source = string_value(row["source"])
    if row["source_sha256"] != digest_text(source):
        raise ValueError("Audited display source hash mismatch.")
    index = int_value(row["plugin_index"]) if "plugin_index" in row else None
    if index is not None and index < 0:
        raise ValueError("Negative plugin index.")
    status = row["expected_status"] if "expected_status" in row else None
    if status is not None and type(status) is not bool:
        raise TypeError("Expected plugin status must be boolean.")
    steps = tuple(step(item) for item in array_value(row.get("steps", [])))
    if codec == "plugins-array" and (not steps or steps[0].path[:2] != (index, "parameters")):
        raise ValueError("Plugin path does not match its guarded index/parameter root.")
    location = span(row["span"]) if "span" in row else None
    if (codec == "plugins-array" and not steps) or (codec != "plugins-array" and location is None):
        raise ValueError("Audited target lacks its exact selector.")
    return Target(relative_file(string_value(row["file"])), string_value(row["file_sha256"]), codec,
                  source, digest_text(source), string_value(row["kind"]), steps, location,
                  optional_string(row, "literal_sha256"), optional_string(row, "expression_sha256"),
                  index, optional_string(row, "plugin_name"), status,
                  tuple(string_value(item) for item in array_value(row.get("expressions", []))),
                  object_value(row["context"]))


def load_targets(path: Path) -> list[Target]:
    spec = object_value(read_json(path))
    if spec["schema_version"] != 1:
        raise ValueError("Unsupported plugin audit schema.")
    return [target(row) for key in ("records", "js_literals", "error_templates") for row in array_value(spec[key])]


def document_codec(value: JsonValue) -> DocumentCodec:
    if value == "plugins-array": return "plugins-array"
    if value == "js-literals": return "js-literals"
    if value == "js-template-literal": return "js-template-literal"
    raise ValueError("Unsupported audited document codec.")
