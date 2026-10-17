"""CLI operations; only these boundaries print or publish reports."""
from dataclasses import asdict
import json
from pathlib import Path

from .catalog import build_core
from .catalog_read import read_catalog
from .catalog_set import combined, components, group_ids
from .groups import frozen_json, write_groups
from .json_store import write_json
from .packets import bounded_packets
from .validation import load_shards, pending_rows, validate
from .schema import Catalog


def build(www: Path, manifest: Path, glossary: Path, project: Path) -> None:
    catalog = build_core(www, manifest, glossary)
    catalog = freeze_catalog(project / "catalog/core-catalog.json", catalog)
    summary = write_groups(catalog, project / "catalog", project / "translation/inputs")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def check(project: Path, group: int, pending: int | None, require_complete: bool, report: Path | None, phase: str = "all") -> int:
    catalog = combined(components(project))
    ids = group_ids(project, group, phase)
    translations = load_shards(project / "translation" / ("group-" + str(group)))
    other_phase = set(group_ids(project, group)) - set(ids)
    values = {key: value for key, value in translations.items() if key not in other_phase}
    result = validate(catalog, ids, values)
    summary = {**asdict(result), "pending": len(result.pending), "complete": result.complete}
    if report is not None:
        write_json(report, {**summary, "pending_ids": list(result.pending)})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if pending is not None and result.pending:
        packets = bounded_packets(catalog, pending_rows(catalog, result), group, min(pending, 180), 2500, phase=phase)
        print(json.dumps(packets[0], ensure_ascii=False, indent=2))
    return 1 if result.errors or (require_complete and result.pending) else 0


def freeze_catalog(path: Path, produced: Catalog) -> Catalog:
    if not path.exists():
        frozen_json(path, produced)
        return produced
    existing = read_catalog(path)
    before = {key: value for key, value in existing.items() if key != "glossary_sha256"}
    after = {key: value for key, value in produced.items() if key != "glossary_sha256"}
    if before != after:
        raise ValueError("Catalog selection/guards changed; frozen IDs and inputs were preserved.")
    write_json(path.parent / (path.stem + "-build-provenance.json"), {
        "schema_version": 1, "core_bytes_preserved": True,
        "frozen_glossary_sha256": existing["glossary_sha256"],
        "current_glossary_sha256": produced["glossary_sha256"],
        "selection_and_preserves_unchanged": True})
    return existing


def add_plugins(www: Path, manifest: Path, glossary: Path, audit: Path, project: Path) -> None:
    from .plugin_catalog import build_plugin

    produced = build_plugin(www, manifest, glossary, audit)
    catalog = freeze_catalog(project / "catalog/plugin-catalog.json", produced)
    summary = write_groups(catalog, project / "catalog", project / "translation/inputs", "additions")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def apply(project: Path, source: Path, target: Path, audit: Path | None, node: str) -> None:
    from .integration import apply_project

    print(json.dumps(apply_project(project, source, target, audit, node), ensure_ascii=False, indent=2))
