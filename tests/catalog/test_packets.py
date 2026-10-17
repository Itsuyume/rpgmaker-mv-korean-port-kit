"""Synthetic packet and shard contracts, including failure-before-overwrite."""
import json
from pathlib import Path
import tempfile
import unittest

from pq_catalog.catalog import merge_candidate, statistics
from pq_catalog.groups import frozen_json, partition
from pq_catalog.json_store import read_json
from pq_catalog.model import Candidate, Context, Location
from pq_catalog.packets import bounded_packets
from pq_catalog.tokens import TOKEN_VERSION
from pq_catalog.validation import load_shards, validate


def catalog():
    merged, traces = {}, {}
    for event in range(12):
        for index, text in enumerate(("Hello %1", "A second line", "Last 3")):
            path = (event, "list", index, "parameters", 0)
            context = Context((event, "list"), "Internal", index,
                              nearby=((index, (text,)),))
            merge_candidate(Candidate(text, "dialogue", (Location("data/CommonEvents.json", path, text),), context),
                            merged, traces, {})
    segments = list(merged.values())
    return {"schema_version": 1, "scope": "core", "token_version": TOKEN_VERSION,
            "source_manifest_sha256": "x", "source_files": {}, "glossary_sha256": "x",
            "segments": segments, "traces": traces, "stats": statistics(segments)}


class PacketTests(unittest.TestCase):
    def test_empty_catalog_produces_empty_groups_and_no_packets(self):
        source = catalog(); source["segments"] = []
        self.assertEqual(partition(source), [[], [], [], [], [], []])
        self.assertEqual(bounded_packets(source, [], 1), [])

    def test_group_order_and_event_ownership_do_not_split(self):
        source = catalog(); groups = partition(source)
        self.assertEqual([row["id"] for group in groups for row in group],
                         [row["id"] for row in source["segments"]])
        ownership = {}
        for number, rows in enumerate(groups):
            for row in rows:
                event = row["locations"][0]["path"][0]
                self.assertEqual(ownership.setdefault(event, number), number)

    def test_packet_limits_include_shared_context_and_retain_order(self):
        source = catalog(); packets = bounded_packets(source, source["segments"], 1, 5, 40)
        self.assertTrue(all(len(item["rows"]) <= 5 and item["stats"]["total_words"] <= 40 for item in packets))
        self.assertEqual([row["id"] for item in packets for row in item["rows"]],
                         [row["id"] for row in source["segments"]])
        with self.assertRaises(ValueError):
            bounded_packets(source, source["segments"], 1, 5, 1)

    def test_duplicate_keys_and_shard_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "1.json").write_text('{"x":"a","x":"b"}')
            with self.assertRaises(ValueError):
                read_json(root / "1.json")
            (root / "1.json").write_text('{"x":"a"}'); (root / "2.json").write_text('{"x":"a"}')
            with self.assertRaises(ValueError):
                load_shards(root)

    def test_validation_reports_missing_extra_empty_and_changed_tokens(self):
        source = catalog(); ids = [row["id"] for row in source["segments"]]
        result = validate(source, ids, {ids[0]: "안녕", ids[1]: " ", "unknown": "값"})
        self.assertFalse(result.complete)
        self.assertEqual(result.saved, 2)
        self.assertEqual(len(result.pending), 34)
        self.assertEqual(len(result.errors), 3)

    def test_frozen_input_is_preserved_on_a_different_update(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"; frozen_json(path, {"a": 1})
            before = path.read_bytes(); frozen_json(path, {"a": 1})
            with self.assertRaises(ValueError):
                frozen_json(path, {"a": 2})
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
