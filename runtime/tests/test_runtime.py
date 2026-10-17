"""Behavioral checks use synthetic files only; no game or renderer is launched."""

from dataclasses import replace
from html.parser import HTMLParser
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.archive import validate_runtime_archive
from runtime.bundle import configure_package, copy_payload, validate_font, validate_output, verify_payload
from runtime.config import load_spec
from runtime.files import (FONT_DESTINATION, LICENSE_DESTINATION, game_hashes, patch_index,
                           source_manifest, validate_game, validate_manifest, validate_package)
from runtime.shared.archive import sha256_file


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script":
            self.scripts.append(values.get("src"))
        if tag == "link" and values.get("rel") == "stylesheet":
            self.styles.append(values.get("href"))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pq synthetic ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.www = self.root / "www"
        self.www.mkdir()
        html = '<html>\r\n<head></head>\r\n<body><script type="text/javascript" src="js/main.js"></script></body></html>'
        (self.www / "index.html").write_bytes(html.encode())
        (self.www / "opaque.bin").write_bytes(bytes(range(256)))
        (self.www / "save").mkdir()
        self.package = self.root / "package.json"
        self.original = {"name": "", "main": "www/index.html", "window": {"width": 816, "height": 624}}
        self.package.write_text(json.dumps(self.original))
        self.spec = load_spec(Path(__file__).parents[1] / "runtime-lock.json")

    def test_manifest_mismatch_fails_without_changing_input(self):
        snapshot = source_manifest(self.www, self.package)
        (self.www / "opaque.bin").write_bytes(b"changed")
        before = game_hashes(self.www)
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_manifest(self.www, self.package, snapshot)
        self.assertEqual(game_hashes(self.www), before)

    def test_empty_input_snapshot_is_explicitly_empty(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(source_manifest(empty, self.package)["www_files"], {})
        with self.assertRaisesRegex(ValueError, "Required MV game file"):
            validate_game(empty)

    def test_game_symlink_is_rejected(self):
        (self.www / "leak").symlink_to(self.package)
        with self.assertRaisesRegex(ValueError, "symlink"):
            game_hashes(self.www)

    def test_existing_output_and_input_overlap_are_rejected(self):
        existing = self.root / "Existing.app"
        existing.mkdir()
        for output in (existing, self.www / "Nested.app"):
            with self.subTest(output=output.name), self.assertRaises(ValueError):
                validate_output(self.www, self.package, output, self.root / "report.json")

    def test_save_data_is_rejected_without_deletion(self):
        save = self.www / "save/file1.rpgsave"
        save.write_bytes(b"personal-save")
        with self.assertRaisesRegex(ValueError, "contains data"):
            validate_output(self.www, self.package, self.root / "New.app", self.root / "report.json")
        self.assertEqual(save.read_bytes(), b"personal-save")

    def test_index_adds_css_and_orders_hooks_after_main(self):
        path = self.www / "index.html"
        patch_index(path)
        parsed = Elements()
        parsed.feed(path.read_text())
        self.assertEqual(parsed.scripts, ["js/main.js", "mac/KoreanFont.js", "mac/NativeRuntime.js"])
        self.assertEqual(parsed.styles, ["mac/KoreanFont.css"])
        self.assertEqual(path.read_bytes().count(b"\n"), path.read_bytes().count(b"\r\n"))
        with self.assertRaises(ValueError):
            patch_index(path)

    def test_manifest_changes_only_explicit_fields(self):
        result = configure_package(self.original, self.spec)
        self.assertEqual(self.original["name"], "")
        self.assertEqual(result["window"]["width"], 816)
        self.assertEqual(result["window"]["height"], 624)
        self.assertEqual(result["pq-runtime"]["profile"], result["name"])

    def test_unexpected_startup_hook_is_rejected(self):
        self.original["node-main"] = "foreign.js"
        self.package.write_text(json.dumps(self.original))
        with self.assertRaises(ValueError):
            validate_package(self.package)

    def fixture_archive(self, name, payload=b"data", mode=stat.S_IFREG | 0o644):
        archive = self.root / self.spec.runtime_filename
        with zipfile.ZipFile(archive, "w") as handle:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = mode << 16
            handle.writestr(info, payload)
        return archive, replace(self.spec, runtime_sha256=sha256_file(archive))

    def test_wrong_checksum_is_rejected(self):
        archive, _ = self.fixture_archive("nwjs-v0.117.0-osx-arm64/nwjs.app/file")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_runtime_archive(archive, self.spec)

    def test_zip_traversal_and_special_file_fail_before_extraction(self):
        for name, mode in [("../outside", stat.S_IFREG),
                           ("nwjs-v0.117.0-osx-arm64/nwjs.app/fifo", stat.S_IFIFO)]:
            archive, spec = self.fixture_archive(name, mode=mode | 0o644)
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_runtime_archive(archive, spec)
            self.assertFalse((self.root / "outside").exists())

    def test_zip_escaping_symlink_is_rejected(self):
        archive, spec = self.fixture_archive("nwjs-v0.117.0-osx-arm64/nwjs.app/escape",
                                              b"../../../outside", stat.S_IFLNK | 0o777)
        with self.assertRaisesRegex(ValueError, "escapes"):
            validate_runtime_archive(archive, spec)

    @unittest.skipUnless(sys.platform == "darwin", "uses the macOS ditto file-copy boundary")
    def test_payload_preserves_assets_and_records_only_index_change(self):
        app = self.root / "Synthetic.app"
        (app / "Contents/Resources").mkdir(parents=True)
        font = self.root / self.spec.font_filename
        font.write_bytes(b"synthetic-font")
        license_file = self.root / "OFL.txt"
        license_file.write_bytes(b"synthetic-license")
        original = game_hashes(self.www)
        copy_payload(self.www, app, self.original, self.spec, font, license_file)
        result = verify_payload(app, original)
        payload = app / "Contents/Resources/app.nw/www"
        self.assertEqual((payload / "opaque.bin").read_bytes(), bytes(range(256)))
        self.assertEqual((payload / FONT_DESTINATION).read_bytes(), font.read_bytes())
        self.assertEqual((payload / LICENSE_DESTINATION).read_bytes(), license_file.read_bytes())
        self.assertFalse((payload / "save").exists())
        self.assertEqual(result["changed_input_files"], ["index.html"])
        self.assertEqual(game_hashes(self.www), original)
        (payload / "opaque.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "Unexpected payload delta"):
            verify_payload(app, original)

    def test_font_hash_mismatch_is_not_accepted(self):
        font = self.root / self.spec.font_filename
        font.write_bytes(b"wrong-font")
        license_file = self.root / "OFL.txt"
        license_file.write_bytes(b"wrong-license")
        with self.assertRaisesRegex(ValueError, "pinned"):
            validate_font(font, license_file, self.spec)


if __name__ == "__main__":
    unittest.main()
