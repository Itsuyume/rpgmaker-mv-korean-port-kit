"""Read-only inventory using the same selectors and token rules as the catalog."""
from collections import Counter
from pathlib import Path
from typing import TypedDict

from runtime.shared.archive import sha256_file
from .core_fields import core_fields
from .event_fields import event_fields
from .json_store import read_json
from .tokens import has_language, word_count


class Inventory(TypedDict):
    stage: str
    json_files: int
    nonempty_display_occurrences: int
    occurrences_by_kind: dict[str, int]
    language_occurrences: int
    language_occurrences_by_kind: dict[str, int]
    globally_unique_language_strings: int
    unique_english_word_estimate: int
    source_data_sha256: dict[str, str]
    plugin_js_hud_quest_included: bool


def inventory(data_root: Path) -> Inventory:
    hashes: dict[str, str] = {}
    counts: Counter[str] = Counter()
    language: Counter[str] = Counter()
    unique: set[str] = set()
    for path in sorted(data_root.glob("*.json")):
        hashes[path.name] = sha256_file(path)
        file, data = "data/" + path.name, read_json(path)
        events, mismatches = event_fields(file, data)
        if mismatches:
            raise ValueError("Inventory found mismatched 102/402 labels.")
        for item in [*core_fields(file, data), *events]:
            for location in item.locations:
                kind = "choice_branch" if location.role == "choice_alias" else item.kind
                counts[kind] += 1
                if has_language(location.source):
                    language[kind] += 1
                    unique.add(location.source)
    return {"stage": "shared_selector_inventory_not_contextual_catalog", "json_files": len(hashes),
            "nonempty_display_occurrences": sum(counts.values()), "occurrences_by_kind": dict(counts),
            "language_occurrences": sum(language.values()), "language_occurrences_by_kind": dict(language),
            "globally_unique_language_strings": len(unique), "unique_english_word_estimate": sum(map(word_count, unique)),
            "source_data_sha256": hashes, "plugin_js_hud_quest_included": False}
