"""Exercise the checker on temporary module graphs and control-flow limits."""

from pathlib import Path
import tempfile
import unittest

from checks.architecture import check


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_empty_and_acyclic_modules_pass(self):
        self.assertEqual(check(self.root), [])
        self.write("pq_catalog/model.py", "value = 1\n")
        self.write("pq_catalog/process.py", "from .model import value\n")
        self.assertEqual(check(self.root), [])

    def test_relative_import_cycle_fails(self):
        self.write("package/a.py", "from .b import value\nvalue = 1\n")
        self.write("package/b.py", "from .a import value\nvalue = 2\n")
        self.assertTrue(any(item.startswith("Import cycle:") for item in check(self.root)))

    def test_elif_dispatch_is_not_counted_as_deep_nesting(self):
        branches = "if value == 0:\n        return 0\n"
        branches += "".join("    elif value == " + str(index) + ":\n        return value\n" for index in range(1, 9))
        self.write("dispatch.py", "def dispatch(value):\n    " + branches)
        self.assertEqual(check(self.root), [])

    def test_shared_hash_is_allowed_but_runtime_back_import_fails(self):
        self.write("runtime/shared/archive.py", "def sha256_file(path):\n    return path\n")
        self.write("pq_catalog/store.py", "from runtime.shared.archive import sha256_file\n")
        self.assertEqual(check(self.root), [])
        self.write("runtime/start.py", "from pq_catalog.store import sha256_file\n")
        self.assertTrue(any("runtime imports catalog" in item for item in check(self.root)))

    def test_disallowed_runtime_dependency_and_deep_flow_fail(self):
        self.write("runtime/start.py", "value = 1\n")
        self.write("pq_catalog/store.py", "from runtime.start import value\n")
        self.write("deep.py", "def deep(value):\n" + "".join("    " * level + "if value:\n" for level in range(1, 6)) + "                        return value\n")
        errors = check(self.root)
        self.assertTrue(any("runtime implementation" in item for item in errors))
        self.assertTrue(any("four levels" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
