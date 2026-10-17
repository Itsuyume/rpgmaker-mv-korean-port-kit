"""Freeze six ordered core groups; later additions never repartition them."""
from collections import OrderedDict
from pathlib import Path

from .catalog import stable_key
from .json_store import read_json, write_json
from .packets import bounded_packets
from .schema import Catalog, Segment


def block_key(row: Segment) -> tuple[str, tuple[str | int, ...]]:
    location = row["locations"][0]
    if location["role"] == "plugin_audit":
        return location["file"], (row["contexts"][0]["trace"],)
    path = location["path"]
    if "pages" in path:
        path = path[:path.index("pages")]
    elif "list" in path:
        path = path[:path.index("list")]
    elif len(path) > 1:
        path = path[:-1]
    return location["file"], tuple(path)


def partition(catalog: Catalog, count: int = 6) -> list[list[Segment]]:
    if count < 1:
        raise ValueError("Group count must be positive.")
    blocks: OrderedDict[tuple[str, tuple[str | int, ...]], list[Segment]] = OrderedDict()
    for row in catalog["segments"]:
        if row["translate"]:
            blocks.setdefault(block_key(row), []).append(row)
    result: list[list[Segment]] = [[] for _ in range(count)]
    remaining = sum(row["word_count"] for rows in blocks.values() for row in rows)
    group, current_words = 0, 0
    for rows in blocks.values():
        words = sum(row["word_count"] for row in rows)
        target = remaining / (count - group)
        if group < count - 1 and result[group] and abs(current_words - target) < abs(current_words + words - target):
            remaining -= current_words
            group += 1
            current_words = 0
        result[group].extend(rows)
        current_words += words
    return result


def frozen_json(path: Path, value: object) -> None:
    if path.exists():
        if read_json(path) != value:
            raise ValueError("Refusing to change frozen translation input: " + str(path))
        return
    write_json(path, value)


def write_groups(catalog: Catalog, catalog_dir: Path, inputs_dir: Path, phase: str = "core") -> dict[str, object]:
    summaries: list[dict[str, object]] = []
    for number, rows in enumerate(partition(catalog), 1):
        chunks = bounded_packets(catalog, rows, number, phase=phase)
        ids = [row["id"] for row in rows]
        plan = {"schema_version": 1, "phase": phase, "group": number, "ids": ids,
                "ids_sha256": stable_key(ids), "units": len(rows),
                "source_words": sum(row["word_count"] for row in rows), "chunks": len(chunks)}
        frozen_json(catalog_dir / "groups" / ("group-" + str(number) + "-" + phase + "-plan.json"), plan)
        root = inputs_dir / ("group-" + str(number))
        for index, chunk in enumerate(chunks, 1):
            frozen_json(root / phase / (str(index).zfill(3) + ".json"), chunk)
        manifest = {**plan, phase + "_chunks": [phase + "/" + str(i).zfill(3) + ".json" for i in range(1, len(chunks) + 1)]}
        frozen_json(root / (phase + "-manifest.json"), manifest)
        summaries.append({key: value for key, value in plan.items() if key != "ids"})
    summary = {"schema_version": 1, phase: summaries, "catalog_stats": catalog["stats"]}
    frozen_json(catalog_dir / (phase + "-group-summary.json"), summary)
    return summary
