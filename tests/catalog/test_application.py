"""Apply to real synthetic files and verify untouched values and failure effects."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from runtime.shared.archive import sha256_file
from pq_catalog.application import apply_core, prepare_core
from pq_catalog.catalog import build_core
from pq_catalog.json_diff import assert_allowed_diff
from pq_catalog.json_store import digest_text, read_json, write_json


def command(code, parameters, indent=0):
    return {"code": code, "indent": indent, "parameters": parameters}


def fixture(root):
    source, target = root / "source", root / "target"
    commands = [command(401, [r"\n<Alice>Hello 3"]), command(102, [["Yes", "No"], 2, 0, 1, 0]),
                command(402, [0, "Yes"]), command(355, ["internal('Yes')"]),
                command(402, [1, "No"]), command(403, []), command(404, []), command(108, ["Comment"])]
    data = [None, {"id": 1, "name": "EditorName", "list": commands, "note": "not displayed"}]
    for folder in (source, target):
        write_json(folder / "data/CommonEvents.json", data)
    file = "data/CommonEvents.json"
    write_json(root / "manifest.json", {"www_files": {file: sha256_file(source / file)}})
    write_json(root / "glossary.json", {"machine_preserves": []})
    catalog = build_core(source, root / "manifest.json", root / "glossary.json")
    mapping = {r"\n<Alice>Hello 3": r"\n<앨리스>안녕 3", "Yes": "응", "No": "아니"}
    translations = {row["id"]: mapping[row["source"]] for row in catalog["segments"]}
    return source, target, catalog, translations


class ApplicationTests(unittest.TestCase):
    def test_only_display_leaves_change_and_aliases_share_one_translation(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target, catalog, translations = fixture(Path(folder))
            original = (source / "data/CommonEvents.json").read_bytes()
            report = apply_core(source, target, catalog, translations)
            game = read_json(target / "data/CommonEvents.json")[1]
            self.assertEqual(game["list"][1]["parameters"][0], ["응", "아니"])
            self.assertEqual(game["list"][2]["parameters"], [0, "응"])
            self.assertEqual(game["list"][4]["parameters"], [1, "아니"])
            self.assertEqual(game["list"][3]["parameters"], ["internal('Yes')"])
            self.assertEqual(game["list"][5], command(403, []))
            self.assertEqual(game["name"], "EditorName")
            self.assertEqual((source / "data/CommonEvents.json").read_bytes(), original)
            self.assertEqual(report["changed_display_leaves"], 5)
            self.assertFalse((target / ".localization-write.lock").exists())

    def test_partial_translation_fails_without_target_side_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target, catalog, translations = fixture(Path(folder))
            path = target / "data/CommonEvents.json"; original = path.read_bytes()
            translations.pop(next(iter(translations)))
            with self.assertRaises(ValueError):
                apply_core(source, target, catalog, translations)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in target.iterdir()), ["data"])

    def test_changed_baseline_and_overlapping_roots_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target, catalog, translations = fixture(Path(folder))
            with self.assertRaises(ValueError):
                prepare_core(source, source, catalog, translations)
            path = target / "data/CommonEvents.json"; path.write_bytes(path.read_bytes() + b" ")
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                apply_core(source, target, catalog, translations)
            self.assertEqual(path.read_bytes(), original)

    def test_injected_script_location_cannot_bypass_core_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target, catalog, translations = fixture(Path(folder))
            row = catalog["segments"][0]; bad = deepcopy(row["locations"][0])
            bad["path"] = [1, "list", 3, "parameters", 0]
            bad["source_sha256"] = digest_text("internal('Yes')")
            row["locations"].append(bad)
            with self.assertRaises(ValueError):
                prepare_core(source, target, catalog, translations)
            self.assertEqual((source / "data/CommonEvents.json").read_bytes(),
                             (target / "data/CommonEvents.json").read_bytes())

    def test_missing_manifest_data_file_cannot_become_an_empty_complete_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source, target, catalog, translations = fixture(root)
            manifest = read_json(root / "manifest.json")
            manifest["www_files"]["data/Map999.json"] = "missing"
            write_json(root / "manifest.json", manifest)
            before = (target / "data/CommonEvents.json").read_bytes()
            with self.assertRaises(ValueError):
                build_core(source, root / "manifest.json", root / "glossary.json")
            self.assertEqual((target / "data/CommonEvents.json").read_bytes(), before)

    def test_recursive_diff_rejects_numeric_types_arrays_and_notes(self):
        for before, after in (({"a": 1}, {"a": True}), ({"a": []}, {"a": [1]}),
                              ({"note": "a"}, {"note": "b"})):
            with self.assertRaises(ValueError):
                assert_allowed_diff(before, after, {})


if __name__ == "__main__":
    unittest.main()
