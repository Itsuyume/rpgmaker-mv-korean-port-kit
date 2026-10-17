"""One complete-catalog preparation and one guarded commit to an explicit target."""
from pathlib import Path

from .application import prepare_core
from .catalog_set import all_translations, combined, components
from .file_transaction import guarded_commit
from .json_store import write_json
from .model import PreparedUpdates
from .plugin_application import prepare_plugin
from .validation import validate


def apply_project(project: Path, source: Path, target: Path, audit: Path | None, node: str) -> dict[str, int]:
    parts = components(project)
    catalog = combined(parts)
    translations = all_translations(project)
    ids = [row["id"] for row in catalog["segments"] if row["translate"]]
    validation = validate(catalog, ids, translations)
    if not validation.complete:
        raise ValueError("No target write: incomplete/invalid catalog translations; pending=" + str(len(validation.pending)) + "; errors=" + str(validation.errors))
    prepared: list[PreparedUpdates] = []
    for part in parts:
        part_ids = {row["id"] for row in part["segments"] if row["translate"]}
        values = {key: value for key, value in translations.items() if key in part_ids}
        if part["scope"] == "core":
            prepared.append(prepare_core(source, target, part, values))
        elif audit is None:
            raise ValueError("Applying plugin translations requires --audit-spec.")
        else:
            prepared.append(prepare_plugin(source, target, part, audit, values, node))
    updates: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for update in prepared:
        if updates.keys() & update.updates.keys():
            raise ValueError("Two application components write the same file.")
        updates.update(update.updates)
        hashes.update(update.expected_hashes)
    guarded_commit(target, updates, hashes)
    for file, content in updates.items():
        if target.joinpath(*file.split("/")).read_bytes() != content:
            raise ValueError("Committed target bytes differ from prepared output: " + file)
    report = {"translated_units": len(ids), "changed_display_leaves": sum(part.changed_leaves for part in prepared),
              "changed_files": len(updates), "guarded_source_files": len(hashes)}
    write_json(project / "catalog/application-report.json", report)
    return report
