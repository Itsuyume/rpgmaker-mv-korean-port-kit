"""Prepare guarded audited JS/plugin replacements, without partial commits."""
import json
from pathlib import Path

from runtime.shared.archive import sha256_file
from .baseline import guarded_files
from .js_spans import replace_spans
from .js_syntax import check_syntax
from .model import PreparedUpdates
from .plugin_catalog import identifier
from .plugin_codecs import apply_nested, parse_plugins, selected_text
from .plugin_contract import Target, load_targets
from .plugin_diff import assert_nested_diff
from .schema import Catalog
from .validation import validate


def target_map(catalog: Catalog, audit_path: Path) -> dict[str, Target]:
    if catalog["scope"] != "plugin" or catalog.get("audit_spec_sha256") != sha256_file(audit_path):
        raise ValueError("Plugin catalog/audit spec hash or scope mismatch.")
    targets = load_targets(audit_path)
    mapped: dict[str, Target] = {}
    for row in catalog["segments"]:
        if len(row["locations"]) != 1 or row["locations"][0]["role"] != "plugin_audit":
            raise ValueError("Plugin catalog location is not one audited selector.")
        path = row["locations"][0]["path"]
        if len(path) != 2 or path[0] != "audit" or type(path[1]) is not int or path[1] < 0:
            raise ValueError("Invalid audit selector index.")
        target = targets[path[1]]
        location = row["locations"][0]
        if (location["file"] != target.file or location["source_sha256"] != target.source_sha256
                or catalog["source_files"].get(target.file) != target.file_sha256):
            raise ValueError("Plugin location/source hash differs from audited target.")
        if identifier(target) != row["id"] or target.source != row["source"]:
            raise ValueError("Plugin unit ID/source differs from audit SSOT.")
        mapped[row["id"]] = target
    if len(mapped) != len(targets):
        raise ValueError("Plugin catalog does not cover every audited selector.")
    return mapped


def prepare_plugin(source: Path, target_root: Path, catalog: Catalog, audit_path: Path,
                   translations: dict[str, str], node: str) -> PreparedUpdates:
    ids = [row["id"] for row in catalog["segments"] if row["translate"]]
    result = validate(catalog, ids, translations)
    if not result.complete:
        raise ValueError("Refusing partial/invalid plugin translations: " + str(len(result.pending)) + " pending; " + str(result.errors))
    mapped = target_map(catalog, audit_path)
    documents = guarded_files(source, target_root, catalog["source_files"])
    grouped: dict[str, list[tuple[Target, str]]] = {}
    for row in catalog["segments"]:
        value = translations[row["id"]] if row["translate"] else row["source"]
        grouped.setdefault(mapped[row["id"]].file, []).append((mapped[row["id"]], value))
    updates: dict[str, bytes] = {}
    changed = 0
    for file, changes in grouped.items():
        original = documents[file]
        updated = replace_file(original, changes)
        if updated != original:
            check_syntax(updated, node)
            updates[file] = updated
        changed += sum(item.source != value for item, value in changes)
    return PreparedUpdates(updates, dict(catalog["source_files"]), len(ids), changed)


def replace_file(original: bytes, changes: list[tuple[Target, str]]) -> bytes:
    codecs = {target.document_codec for target, _ in changes}
    if "plugins-array" not in codecs:
        return replace_spans(original, changes)
    if codecs != {"plugins-array"}:
        raise ValueError("A file mixes incompatible audited document codecs.")
    prefix, before, suffix = parse_plugins(original)
    for target, _ in changes:
        selected_text(before, target)
    after = apply_nested(before, changes)
    assert_nested_diff(before, after, changes)
    if before == after:
        return original
    result = (prefix + json.dumps(after, ensure_ascii=False, indent=2) + suffix).encode("utf-8")
    _, checked, _ = parse_plugins(result)
    if checked != after:
        raise ValueError("Generated plugin array did not round-trip.")
    return result
