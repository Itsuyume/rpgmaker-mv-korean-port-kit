"""Snapshot inputs or build a fresh native NW.js app. Never launch the game."""

import argparse
import json
from pathlib import Path

from runtime.bundle import build_app
from runtime.config import load_spec
from runtime.files import source_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot")
    build = commands.add_parser("build")
    for command in (snapshot, build):
        command.add_argument("--www", type=Path, required=True)
        command.add_argument("--package", type=Path, required=True)
    snapshot.add_argument("--out", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--runtime-zip", type=Path, required=True)
    build.add_argument("--font", type=Path, required=True)
    build.add_argument("--font-license", type=Path, required=True)
    build.add_argument("--out-app", type=Path, required=True)
    build.add_argument("--report", type=Path, required=True)
    build.add_argument("--prepare-only", action="store_true",
                       help="Prepare and hash-check staging files without claiming a valid app signature")
    build.add_argument("--lock", type=Path, default=Path(__file__).parent / "runtime/runtime-lock.json")
    args = parser.parse_args()
    if args.command == "snapshot":
        result = source_manifest(args.www, args.package)
        with args.out.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"file_count": result["file_count"], "bytes": result["bytes"]}))
        return
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = build_app(args.www, args.package, manifest, args.runtime_zip,
                       args.out_app, args.report, load_spec(args.lock), args.font, args.font_license,
                       prepare_only=args.prepare_only)
    print(json.dumps({"input_files": len(result["input_file_hashes"]),
                      "signature_verified": result["signature_verified"], "gui_tested": False}))


if __name__ == "__main__":
    main()
