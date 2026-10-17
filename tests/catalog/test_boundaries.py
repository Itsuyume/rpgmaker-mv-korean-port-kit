"""External JSON, path and transaction failure boundaries use real files."""
from pathlib import Path
import tempfile
import unittest

from runtime.shared.archive import sha256_file
from pq_catalog.event_fields import event_fields
from pq_catalog.file_transaction import guarded_commit
from pq_catalog.json_store import decode_json
from pq_catalog.paths import json_path, relative_file, source_file


class BoundaryTests(unittest.TestCase):
    def test_unsafe_paths_boolean_indices_and_nonfinite_json_fail(self):
        for value in ("", "/absolute", "data/../file", "data//file", "data\\file"):
            with self.assertRaises(ValueError):
                relative_file(value)
        for value in ([], [True], [-1], [None]):
            with self.assertRaises(ValueError):
                json_path(value)
        for value in ("NaN", "Infinity", "1e9999"):
            with self.assertRaises(ValueError):
                decode_json(value)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "inside").mkdir(); (root / "outside").mkdir()
            (root / "inside/link").symlink_to(root / "outside", target_is_directory=True)
            with self.assertRaises(ValueError):
                source_file(root / "inside", "link/file")

    def test_late_file_guard_failure_writes_nothing_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "a").write_bytes(b"A"); (root / "b").write_bytes(b"B")
            guards = {"a": sha256_file(root / "a"), "b": "wrong"}
            with self.assertRaises(ValueError):
                guarded_commit(root, {"a": b"new A", "b": b"new B"}, guards)
            self.assertEqual((root / "a").read_bytes(), b"A")
            self.assertEqual((root / "b").read_bytes(), b"B")
            self.assertFalse((root / ".localization-write.lock").exists())

    def test_existing_concurrent_writer_lock_is_never_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / "a").write_bytes(b"A")
            lock = root / ".localization-write.lock"; lock.write_text("other writer")
            with self.assertRaises(FileExistsError):
                guarded_commit(root, {"a": b"B"}, {"a": sha256_file(root / "a")})
            self.assertEqual(lock.read_text(), "other writer")
            self.assertEqual((root / "a").read_bytes(), b"A")

    def test_scrolling_name_nickname_profile_are_selected_without_internal_ids(self):
        commands = [{"code": code, "indent": 0, "parameters": params} for code, params in (
            (405, ["Scrolling"]), (320, [7, "Alice"]), (324, [7, "Explorer"]),
            (325, [7, "Profile\nSecond line"]), (122, [1, 2, "Internal value"]),
            (356, ["InternalCommand argument"]))]
        rows, mismatches = event_fields("data/CommonEvents.json", [None, {"name": "Internal", "list": commands}])
        self.assertEqual([row.kind for row in rows], ["scrolling_text", "actor_name_change", "actor_nickname_change", "actor_profile_change"])
        self.assertEqual([row.locations[0].path[-1] for row in rows], [0, 1, 1, 1])
        self.assertEqual(mismatches, [])
        self.assertEqual(commands[1]["parameters"][0], 7)


if __name__ == "__main__":
    unittest.main()
