"""Combine frozen component catalogs and plans without rewriting either."""
from pathlib import Path

from .catalog import statistics
from .catalog_read import assert_unique, read_catalog
from .schema import Catalog
from .validation import load_shards, plan_ids


def components(project: Path) -> list[Catalog]:
    core = read_catalog(project / "catalog/core-catalog.json")
    plugin = project / "catalog/plugin-catalog.json"
    return [core, read_catalog(plugin)] if plugin.exists() else [core]


def combined(parts: list[Catalog]) -> Catalog:
    if not parts:
        raise ValueError("At least one catalog component is required.")
    first = parts[0]
    result: Catalog = {**first, "scope": "combined", "segments": [], "traces": {}, "source_files": {}}
    for part in parts:
        if part["token_version"] != first["token_version"] or part["source_manifest_sha256"] != first["source_manifest_sha256"]:
            raise ValueError("Catalog components do not share one source/token contract.")
        result["segments"].extend(part["segments"])
        for key, trace in part["traces"].items():
            if key in result["traces"] and trace != result["traces"][key]:
                raise ValueError("Context trace collision between catalog components.")
            result["traces"][key] = trace
        for file, digest in part["source_files"].items():
            if file in result["source_files"] and digest != result["source_files"][file]:
                raise ValueError("Source hash collision between catalog components.")
            result["source_files"][file] = digest
    assert_unique(result["segments"], result["traces"])
    result["stats"] = statistics(result["segments"])
    return result


def group_ids(project: Path, group: int, phase: str = "all") -> list[str]:
    phases = ("core", "additions") if phase == "all" else (phase,)
    result: list[str] = []
    for name in phases:
        path = project / "catalog/groups" / ("group-" + str(group) + "-" + name + "-plan.json")
        if name == "additions" and not path.exists() and phase == "all":
            continue
        result.extend(plan_ids(path))
    if len(result) != len(set(result)):
        raise ValueError("Component plans contain duplicate IDs.")
    return result


def all_translations(project: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for group in range(1, 7):
        values = load_shards(project / "translation" / ("group-" + str(group)))
        if set(values) - set(group_ids(project, group)):
            raise ValueError("Shard IDs are outside their assigned group: " + str(group))
        if result.keys() & values.keys():
            raise ValueError("Duplicate translation ID across groups.")
        result.update(values)
    return result
