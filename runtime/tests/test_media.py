"""Media reference behavior and native-header edge cases, without a renderer."""

import json
from pathlib import Path
import plistlib
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.media import inspect_media_file
from runtime.media_references import audit_references, references_in_value
from runtime.files import game_hashes
from runtime.qa import architectures, inspect_app, inspect_engine_architectures


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pq media synthetic ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_literal_video_and_audio_commands_keep_exact_names(self):
        self.assertEqual(references_in_value({"code": 261, "parameters": ["A scene"]}, ".rpgmvo"),
                         ["movies/A scene.webm"])
        self.assertEqual(references_in_value({"code": 250, "parameters": [{"name": "Bell"}]}, ".rpgmvo"),
                         ["audio/se/Bell.rpgmvo"])
        self.assertEqual(references_in_value('ysp.VideoPlayer.newVideo("A scene.webm", "id")', ".ogg"),
                         ["movies/A scene.webm"])
        self.assertEqual(references_in_value('ysp.VideoPlayer.newVideo(prefix + ".webm")', ".ogg"), [])
        self.assertEqual(references_in_value(None, ".ogg"), [])

    def test_missing_paths_case_differences_and_dynamic_calls_are_separate(self):
        (self.root / "data").mkdir()
        (self.root / "movies").mkdir()
        (self.root / "audio").mkdir()
        (self.root / "movies/Scene.webm").write_bytes(b"metadata fixture")
        commands = [{"code": 261, "parameters": ["scene"]},
                    {"code": 261, "parameters": ["missing"]},
                    {"code": 355, "parameters": ['ysp.VideoPlayer.newVideo(variable)']}]
        (self.root / "data/Map001.json").write_text(json.dumps(commands))
        (self.root / "data/System.json").write_text("{}")
        report = audit_references(self.root, False)
        self.assertEqual(list(report["missing"]), ["movies/missing.webm"])
        self.assertEqual(report["case_differences"], {"movies/scene.webm": "movies/Scene.webm"})
        self.assertEqual(len(report["dynamic_ysp_calls_unresolved"]), 1)

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is an explicit optional metadata dependency")
    def test_metadata_error_is_reported_and_temporary_audio_is_removed(self):
        audio = self.root / "invalid.rpgmvo"
        audio.write_bytes(b"invalid encrypted header")
        report = inspect_media_file(self.root, audio, Path(shutil.which("ffprobe")), "00" * 16, self.root)
        self.assertIn("error", report)
        self.assertEqual(report["file"], "invalid.rpgmvo")
        self.assertEqual(sorted(file.name for file in self.root.iterdir()), ["invalid.rpgmvo"])

    def test_thin_and_universal_cpu_headers_are_read_without_execution(self):
        arm = self.root / "arm"
        arm.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C) + bytes(24))
        self.assertEqual(architectures(arm), ("arm64",))
        fat = self.root / "fat"
        fat.write_bytes(b"\xca\xfe\xba\xbe" + struct.pack(">I", 2) +
                        struct.pack(">IIIII", 0x01000007, 0, 0, 0, 0) +
                        struct.pack(">IIIII", 0x0100000C, 0, 0, 0, 0))
        self.assertEqual(architectures(fat), ("x86_64", "arm64"))

    def test_truncated_macho_and_x86_only_engine_fail(self):
        binary = self.root / "runtime"
        binary.write_bytes(b"\xca\xfe\xba\xbe")
        with self.assertRaisesRegex(ValueError, "Truncated"):
            architectures(binary)
        binary.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x01000007) + bytes(24))
        with self.assertRaisesRegex(ValueError, "lacks arm64"):
            inspect_engine_architectures(self.root)

    def test_prepared_qa_detects_asset_changes_without_claiming_a_signature(self):
        app = self.root / "Prepared.app"
        payload = app / "Contents/Resources/app.nw"
        (payload / "www").mkdir(parents=True)
        asset = payload / "www/opaque.bin"
        asset.write_bytes(b"preserved")
        (app / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "test.synthetic"}))
        (payload / "package.json").write_text('{"name":"synthetic-profile"}')
        (app / "Contents/MacOS").mkdir()
        (app / "Contents/MacOS/runtime").write_bytes(
            b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C) + bytes(24))
        report = {"payload": {"output_file_hashes": game_hashes(payload / "www")}}
        result = inspect_app(app, report, prepare_only=True)
        self.assertFalse(result["signature_verified"])
        self.assertTrue(result["signature_check_skipped"])
        self.assertEqual(len(result["mach_o_files"]), 1)
        asset.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "payload changed"):
            inspect_app(app, report, prepare_only=True)


if __name__ == "__main__":
    unittest.main()
