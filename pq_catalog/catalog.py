"""Build the immutable core catalog from explicit selectors and source hashes."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from runtime.shared.archive import sha256_file
from .core_fields import core_fields
from .event_fields import event_fields
from .json_store import array_value, digest_text, get_path, object_value, read_json, string_value
from .model import Candidate, JsonValue
from .paths import json_path, source_file
from .tokens import TOKEN_VERSION, has_language, word_count
from .schema import Catalog, CatalogStats, ContextRecord, Segment, TraceRecord


def stable_key(value: object) -> str:
    return digest_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def preserves(glossary: JsonValue, root: Path) -> dict[tuple[str, tuple[str | int, ...]], str]:
    result: dict[tuple[str, tuple[str | int, ...]], str] = {}
    for raw in array_value(object_value(glossary)["machine_preserves"]):
        row = object_value(raw)
        file, path = string_value(row["file"]), json_path(row["path"])
        source = string_value(row["source"])
        if get_path(read_json(source_file(root, file)), path) != source:
            raise ValueError("Declared preserve source mismatch: " + file + str(path))
        key = file, path
        if key in result:
            raise ValueError("Duplicate declared preserve location.")
        result[key] = string_value(row["reason"])
    return result


def context_record(item: Candidate, traces: dict[str, TraceRecord]) -> ContextRecord:
    context = item.context
    file = item.locations[0].file
    trace_id = "ctx_" + stable_key([file, context.owner_path])[:24]
    trace = traces.setdefault(trace_id, {"file": file, "owner_path": list(context.owner_path),
                                       "owner_name": context.owner_name, "entries": {}})
    entries = trace["entries"]
    if context.command_index is None:
        entries["record"] = list(dict.fromkeys([*entries.get("record", []), item.source, *context.related]))
    else:
        for index, texts in context.nearby:
            entries[str(index)] = list(texts)
    return {"trace": trace_id, "command_index": context.command_index,
            "face_name": context.face_name, "choices": list(context.choices),
            "composition": context.composition}


def merge_candidate(item: Candidate, merged: dict[str, Segment], traces: dict[str, TraceRecord],
                    declared: dict[tuple[str, tuple[str | int, ...]], str]) -> None:
    first, context = item.locations[0], item.context
    key = stable_key([first.file, context.owner_path, item.kind, context.face_name, item.source, context.choices])
    reasons = {declared[(loc.file, loc.path)] for loc in item.locations if (loc.file, loc.path) in declared}
    reason = "; ".join(sorted(reasons)) if reasons else None
    translated = has_language(item.source) and reason is None
    row = merged.setdefault(key, {"id": "pq_" + key[:24], "source": item.source,
        "source_sha256": digest_text(item.source), "kind": item.kind,
        "translate": translated, "preserve_reason": reason or (None if translated else "no-language"),
        "word_count": word_count(item.source), "locations": [], "contexts": []})
    for location in item.locations:
        row["locations"].append({"file": location.file, "path": list(location.path),
                                 "source_sha256": digest_text(location.source), "role": location.role})
    row["contexts"].append(context_record(item, traces))


def build_core(root: Path, manifest_path: Path, glossary_path: Path) -> Catalog:
    manifest = object_value(read_json(manifest_path))
    expected = object_value(manifest["www_files"])
    declared = preserves(read_json(glossary_path), root)
    merged: dict[str, Segment] = {}
    traces: dict[str, TraceRecord] = {}
    source_hashes: dict[str, str] = {}
    paths = sorted((root / "data").glob("*.json"))
    actual_files = {"data/" + path.name for path in paths}
    expected_files = {file for file in expected if file.startswith("data/")
                      and "/" not in file[5:] and file.endswith(".json")}
    if not paths or actual_files != expected_files:
        raise ValueError("Core data JSON file set is empty or differs from source manifest.")
    for candidate_path in paths:
        file = "data/" + candidate_path.name
        path = source_file(root, file)
        digest = sha256_file(path)
        if file not in expected or expected[file] != digest:
            raise ValueError("Source manifest mismatch: " + file)
        source_hashes[file] = digest
        data = read_json(path)
        candidates = list(core_fields(file, data))
        events, mismatches = event_fields(file, data)
        if mismatches:
            raise ValueError("102/402 source label mismatch: " + str(asdict(mismatches[0])))
        for item in [*candidates, *events]:
            merge_candidate(item, merged, traces, declared)
    segments = list(merged.values())
    ids = [row["id"] for row in segments]
    if len(ids) != len(set(ids)):
        raise ValueError("Catalog ID collision.")
    return {"schema_version": 1, "scope": "core", "token_version": TOKEN_VERSION,
            "source_manifest_sha256": sha256_file(manifest_path), "source_files": source_hashes,
            "glossary_sha256": sha256_file(glossary_path), "segments": segments, "traces": traces,
            "stats": statistics(segments)}


def statistics(segments: list[Segment]) -> CatalogStats:
    translated = [row for row in segments if row["translate"]]
    return {"units": len(segments), "translate": len(translated),
            "preserve": len(segments) - len(translated),
            "words": sum(row["word_count"] for row in translated),
            "locations": sum(len(row["locations"]) for row in segments),
            "by_kind": dict(Counter(row["kind"] for row in segments))}
