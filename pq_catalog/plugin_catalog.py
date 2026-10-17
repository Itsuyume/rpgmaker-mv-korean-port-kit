"""Freeze audited plugin units without moving existing core IDs or groups."""
from dataclasses import asdict
import json
from pathlib import Path

from runtime.shared.archive import sha256_file
from .catalog import stable_key, statistics
from .json_store import object_value, read_json
from .js_spans import selected_literal, template_blocks
from .model import JsonPath, JsonValue
from .paths import source_file
from .plugin_codecs import parse_plugins, selected_text
from .plugin_contract import Target, load_targets
from .schema import Catalog, Segment, TraceRecord
from .tokens import TOKEN_VERSION, has_language, word_count


def identifier(target: Target) -> str:
    return "pq_" + stable_key([target.file, target.document_codec,
                              [asdict(step) for step in target.steps],
                              asdict(target.span) if target.span else None, target.source_sha256])[:24]


def owner(target: Target) -> tuple[JsonPath, str]:
    if not target.steps:
        return (target.document_codec, target.file), target.file
    if target.plugin_index is None or target.plugin_name is None:
        raise ValueError("Plugin context requires its guarded name/index.")
    quest = target.context.get("quest_id")
    if type(quest) is int:
        return ("plugin", target.plugin_index, "quest", quest), target.plugin_name + " / Quest " + str(quest)
    return ("plugin", target.plugin_index, "parameter", str(target.steps[0].path[-1])), target.plugin_name


def build_plugin(root: Path, manifest_path: Path, glossary_path: Path, audit_path: Path) -> Catalog:
    manifest = object_value(object_value(read_json(manifest_path))["www_files"])
    targets = load_targets(audit_path)
    files: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    plugins: dict[str, list[JsonValue]] = {}
    segments: list[Segment] = []
    traces: dict[str, TraceRecord] = {}
    for index, target in enumerate(targets):
        path = source_file(root, target.file)
        if target.file not in files:
            files[target.file], hashes[target.file] = path.read_bytes(), sha256_file(path)
        if target.file_sha256 != hashes[target.file] or manifest.get(target.file) != hashes[target.file]:
            raise ValueError("Plugin audit/source manifest hash mismatch: " + target.file)
        if target.document_codec == "plugins-array":
            if target.file not in plugins:
                _, plugins[target.file], _ = parse_plugins(files[target.file])
            selected_text(plugins[target.file], target)
        else:
            selected_literal(files[target.file], target, "utf8-bytes")
        segments.append(segment(target, index, traces))
    ids = [row["id"] for row in segments]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate audited display selectors.")
    return {"schema_version": 1, "scope": "plugin", "token_version": TOKEN_VERSION,
            "audit_spec_sha256": sha256_file(audit_path), "source_files": hashes,
            "source_manifest_sha256": sha256_file(manifest_path), "glossary_sha256": sha256_file(glossary_path),
            "segments": segments, "traces": traces, "stats": statistics(segments)}


def segment(target: Target, index: int, traces: dict[str, TraceRecord]) -> Segment:
    path, name = owner(target)
    trace_id = "ctx_" + stable_key(["plugin-audit", target.file, path])[:24]
    trace = traces.setdefault(trace_id, {"file": target.file, "owner_path": list(path), "owner_name": name, "entries": {}})
    trace["entries"][str(index)] = [target.source]
    translate = has_language(target.source)
    row: Segment = {"id": identifier(target), "source": target.source,
        "source_sha256": target.source_sha256, "kind": target.kind, "translate": translate,
        "preserve_reason": None if translate else "no-language", "word_count": word_count(target.source),
        "locations": [{"file": target.file, "path": ["audit", index],
                       "source_sha256": target.source_sha256, "role": "plugin_audit"}],
        "contexts": [{"trace": trace_id, "command_index": index, "face_name": None, "choices": [],
                      "composition": json.dumps(target.context, ensure_ascii=False, separators=(",", ":"))}]}
    if target.document_codec == "js-template-literal":
        row["protected"] = template_blocks(target.source, target.expressions)
    return row
