"""Prepare only allowed core JSON leaves in a separate baseline www copy."""
from copy import deepcopy
import json
from pathlib import Path

from .baseline import guarded_files
from .core_fields import core_fields
from .event_fields import event_fields
from .file_transaction import guarded_commit
from .json_diff import assert_allowed_diff
from .json_store import decode_json, digest_text, get_path, set_path, string_value
from .model import JsonPath, JsonValue, PreparedUpdates
from .schema import Catalog
from .validation import validate


def source_documents(source: Path, target: Path, catalog: Catalog) -> dict[str, JsonValue]:
    files = guarded_files(source, target, catalog["source_files"])
    return {file: decode_json(content.decode("utf-8-sig")) for file, content in files.items()}


def selected_locations(documents: dict[str, JsonValue]) -> set[tuple[str, JsonPath]]:
    locations: set[tuple[str, JsonPath]] = set()
    for file, document in documents.items():
        events, mismatches = event_fields(file, document)
        if mismatches:
            raise ValueError("Source choice aliases do not match.")
        for item in [*core_fields(file, document), *events]:
            locations.update((location.file, location.path) for location in item.locations)
    return locations


def replacements(catalog: Catalog, translations: dict[str, str], documents: dict[str, JsonValue]) -> dict[str, dict[JsonPath, str]]:
    found: set[tuple[str, JsonPath]] = set()
    result: dict[str, dict[JsonPath, str]] = {}
    for row in catalog["segments"]:
        for item in row["locations"]:
            file, path = item["file"], tuple(item["path"])
            value = string_value(get_path(documents[file], path))
            if digest_text(value) != item["source_sha256"]:
                raise ValueError("Selected source leaf hash mismatch: " + file + str(path))
            if (file, path) in found:
                raise ValueError("Duplicate catalog location.")
            found.add((file, path))
            if row["translate"]:
                result.setdefault(file, {})[path] = translations[row["id"]]
    if found != selected_locations(documents):
        raise ValueError("Catalog locations do not exactly cover the core display allowlist.")
    return result


def prepare_core(source: Path, target: Path, catalog: Catalog, translations: dict[str, str]) -> PreparedUpdates:
    if catalog["scope"] != "core":
        raise ValueError("Core application refuses non-core catalog scopes.")
    ids = [row["id"] for row in catalog["segments"] if row["translate"]]
    result = validate(catalog, ids, translations)
    if not result.complete:
        raise ValueError("Refusing partial/invalid translation application: " + str(len(result.pending)) + " pending; " + str(result.errors))
    documents = source_documents(source, target, catalog)
    expected = replacements(catalog, translations, documents)
    updates: dict[str, bytes] = {}
    changed = 0
    for file, leaves in expected.items():
        before = documents[file]
        after = deepcopy(before)
        for path, text in leaves.items():
            changed += get_path(before, path) != text
            set_path(after, path, text)
        assert_allowed_diff(before, after, leaves)
        if before != after:
            updates[file] = (json.dumps(after, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    return PreparedUpdates(updates, dict(catalog["source_files"]), len(ids), changed)


def apply_core(source: Path, target: Path, catalog: Catalog, translations: dict[str, str]) -> dict[str, int]:
    prepared = prepare_core(source, target, catalog, translations)
    guarded_commit(target, prepared.updates, prepared.expected_hashes)
    return {"translated_units": prepared.translated_units, "changed_display_leaves": prepared.changed_leaves,
            "changed_files": len(prepared.updates)}
