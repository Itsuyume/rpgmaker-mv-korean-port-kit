"""Verify a prepared app's signature, architecture and captured payload hashes."""

import argparse
import json
from pathlib import Path

from runtime.qa import inspect_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true",
                        help="Inspect staging payload and architecture; do not claim a verified signature")
    args = parser.parse_args()
    report = json.loads(args.build_report.read_text(encoding="utf-8"))
    result = inspect_app(args.app, report, prepare_only=args.prepare_only)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"mach_o_files": len(result["mach_o_files"]),
                      "signature_verified": result["signature_verified"],
                      "payload_hashes_match_build_report": True, "gui_tested": False}))


if __name__ == "__main__":
    main()
