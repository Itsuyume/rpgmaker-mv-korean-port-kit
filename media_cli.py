"""Read media metadata with an existing ffprobe and a pinned official codec dylib."""

import argparse
import json
from pathlib import Path

from runtime.media import audit_media


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--www", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    parser.add_argument("--ffmpeg-library", type=Path, required=True)
    parser.add_argument("--temporary-parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Media report output already exists")
    result = audit_media(args.www, args.ffprobe, args.ffmpeg_library, args.temporary_parent)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"files": result["file_count"], "codecs": result["stream_codecs"],
                      "metadata_errors": len(result["metadata_errors"]),
                      "missing_literal_paths": len(result["literal_references"]["missing"]),
                      "rendered": False}))
    if result["metadata_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
