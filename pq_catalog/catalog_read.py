"""Validate serialized catalog shapes at the JSON boundary."""
from pathlib import Path
import re

from .catalog import statistics
from .json_store import array_value, digest_text, int_value, object_value, read_json, string_value
from .model import JsonValue
from .paths import json_path, relative_file
from .schema import Catalog, ContextRecord, LocationRecord, Segment, TraceRecord
from .tokens import TOKEN_VERSION, word_count


def nullable_string(value: JsonValue) -> str | None:
    return None if value is None else string_value(value)


def strings(value: JsonValue) -> list[str]:
    return [string_value(item) for item in array_value(value)]


def location(value: JsonValue) -> LocationRecord:
    row = object_value(value)
    role = string_value(row["role"])
    if role not in {"primary", "choice_alias", "plugin_audit"}:
        raise ValueError("Unknown core location role.")
    return {"file": relative_file(string_value(row["file"])), "path": list(json_path(row["path"])),
            "source_sha256": string_value(row["source_sha256"]), "role": role}


def context(value: JsonValue) -> ContextRecord:
    row = object_value(value)
    index = None if row["command_index"] is None else int_value(row["command_index"])
    if index is not None and index < 0:
        raise ValueError("Negative context command index.")
    return {"trace": string_value(row["trace"]), "command_index": index,
            "face_name": nullable_string(row["face_name"]), "choices": strings(row["choices"]),
            "composition": nullable_string(row["composition"])}


def segment(value: JsonValue) -> Segment:
    row = object_value(value)
    identifier, source = string_value(row["id"]), string_value(row["source"])
    if not re.fullmatch(r"pq_[0-9a-f]{24}", identifier):
        raise ValueError("Malformed unit ID.")
    if type(row["translate"]) is not bool:
        raise TypeError("translate must be boolean.")
    if row["source_sha256"] != digest_text(source) or row["word_count"] != word_count(source):
        raise ValueError("Catalog source hash or word count mismatch: " + identifier)
    locations = [location(item) for item in array_value(row["locations"])]
    contexts = [context(item) for item in array_value(row["contexts"])]
    if not locations or not contexts:
        raise ValueError("A core unit needs locations and context.")
    result: Segment = {"id": identifier, "source": source, "source_sha256": digest_text(source),
            "kind": string_value(row["kind"]), "translate": row["translate"],
            "preserve_reason": nullable_string(row["preserve_reason"]), "word_count": word_count(source),
            "locations": locations, "contexts": contexts}
    if "protected" in row:
        result["protected"] = strings(row["protected"])
    return result


def trace(value: JsonValue) -> TraceRecord:
    row = object_value(value)
    owner = array_value(row["owner_path"])
    owner_path = list(json_path(owner)) if owner else []
    entries = {key: strings(item) for key, item in object_value(row["entries"]).items()}
    if any(key != "record" and (not key.isdigit() or str(int(key)) != key) for key in entries):
        raise ValueError("Trace entry indices must be canonical nonnegative integers.")
    return {"file": relative_file(string_value(row["file"])), "owner_path": owner_path,
            "owner_name": string_value(row["owner_name"]), "entries": entries}


def read_catalog(path: Path) -> Catalog:
    row = object_value(read_json(path))
    if row["schema_version"] != 1 or row["token_version"] != TOKEN_VERSION or row["scope"] not in {"core", "plugin"}:
        raise ValueError("Unsupported core catalog schema or token version.")
    segments = [segment(item) for item in array_value(row["segments"])]
    traces = {key: trace(item) for key, item in object_value(row["traces"]).items()}
    assert_unique(segments, traces)
    stats = statistics(segments)
    if stats != row["stats"]:
        raise ValueError("Catalog statistics mismatch.")
    source_files = {relative_file(key): string_value(value) for key, value in object_value(row["source_files"]).items()}
    result: Catalog = {"schema_version": 1, "scope": string_value(row["scope"]), "token_version": TOKEN_VERSION,
            "source_manifest_sha256": string_value(row["source_manifest_sha256"]),
            "glossary_sha256": string_value(row["glossary_sha256"]), "source_files": source_files,
            "segments": segments, "traces": traces, "stats": stats}
    if "audit_spec_sha256" in row:
        result["audit_spec_sha256"] = string_value(row["audit_spec_sha256"])
    return result


def assert_unique(segments: list[Segment], traces: dict[str, TraceRecord]) -> None:
    identifiers: set[str] = set()
    locations: set[tuple[str, tuple[str | int, ...]]] = set()
    for row in segments:
        if row["id"] in identifiers:
            raise ValueError("Duplicate catalog ID.")
        identifiers.add(row["id"])
        for item in row["locations"]:
            key = item["file"], tuple(item["path"])
            if key in locations:
                raise ValueError("Duplicate selected location.")
            locations.add(key)
        for reference in row["contexts"]:
            if reference["trace"] not in traces:
                raise ValueError("Missing context trace.")
