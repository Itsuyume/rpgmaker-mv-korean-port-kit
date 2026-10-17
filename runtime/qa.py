"""Inspect Mach-O metadata and preserved assets without starting a renderer."""

import json
import os
from pathlib import Path
import plistlib
import struct

from .files import game_hashes, walk_error
from .shared import native


MACHO_MAGIC = {b"\xcf\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xcf": ">",
               b"\xce\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xce": ">"}
CPU_NAMES = {0x0100000C: "arm64", 0x01000007: "x86_64", 12: "arm", 7: "x86"}


def architectures(path: Path) -> tuple[str, ...]:
    with path.open("rb") as handle:
        header = handle.read(4096)
    endian = MACHO_MAGIC.get(header[:4])
    if endian:
        if len(header) < (32 if header[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf") else 28):
            raise ValueError("Truncated Mach-O header")
        cpu = struct.unpack_from(endian + "I", header, 4)[0]
        return (CPU_NAMES.get(cpu, f"cpu-{cpu}"),)
    if header[:4] not in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
        return ()
    if len(header) < 8:
        raise ValueError("Truncated Mach-O universal header")
    count = struct.unpack_from(">I", header, 4)[0]
    stride = 32 if header[:4] == b"\xca\xfe\xba\xbf" else 20
    if not 0 < count <= 64 or len(header) < 8 + count * stride:
        raise ValueError("Invalid Mach-O universal architecture table")
    return tuple(CPU_NAMES.get(struct.unpack_from(">I", header, 8 + index * stride)[0], "unknown")
                 for index in range(count))


def inspect_engine_architectures(app: Path) -> list[dict]:
    results = []
    for directory, directories, filenames in os.walk(app, followlinks=False, onerror=walk_error):
        if Path(directory).relative_to(app).as_posix() == "Contents/Resources":
            directories[:] = [name for name in directories if name != "app.nw"]
        for name in filenames:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            arch = architectures(path)
            if not arch:
                continue
            if "arm64" not in arch:
                raise ValueError(f"Engine Mach-O lacks arm64: {path.relative_to(app)}")
            results.append({"file": path.relative_to(app).as_posix(), "architectures": list(arch)})
    if not results:
        raise ValueError("App contains no Mach-O runtime")
    return results


def inspect_app(app: Path, build_report: dict, *, prepare_only: bool = False) -> dict:
    if not prepare_only:
        native.verify_app(app)
    payload = app / "Contents/Resources/app.nw"
    hashes = game_hashes(payload / "www")
    if hashes != build_report["payload"]["output_file_hashes"]:
        raise ValueError("Staged app payload changed after the build report")
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    package = json.loads((payload / "package.json").read_text(encoding="utf-8"))
    return {"signature_verified": not prepare_only, "signature_check_skipped": prepare_only,
            "mach_o_files": inspect_engine_architectures(app),
            "bundle_identifier": info["CFBundleIdentifier"], "profile_name": package["name"],
            "minimum_macos": info.get("LSMinimumSystemVersion"),
            "payload_file_count": len(hashes), "payload_hashes_match_build_report": True,
            "gui_tested": False, "video_audio_tested": False, "real_save_ui_tested": False}
