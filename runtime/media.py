"""Probe media headers and the official codec library; never render or transcode."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
from pathlib import Path
import subprocess
import tempfile

from .media_references import audit_references
from .shared.asset_crypto import decrypt_asset


PROBE_ENTRIES = "stream=codec_type,codec_name,width,height,sample_rate,channels:format=format_name"


def ffprobe_file(ffprobe: Path, file: Path) -> dict:
    result = subprocess.run(["/usr/bin/nice", "-n", "10", str(ffprobe), "-v", "error",
                             "-show_entries", PROBE_ENTRIES, "-of", "json", str(file)],
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError(f"ffprobe exited {result.returncode}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise ValueError("Media file contains no identified streams")
    if any(not stream.get("codec_name") for stream in data["streams"]):
        raise ValueError("Media file contains an unidentified codec")
    return {"streams": data["streams"], "format": data.get("format", {}).get("format_name")}


def inspect_media_file(www: Path, file: Path, ffprobe: Path, key: str, temporary: Path) -> dict:
    relative = file.relative_to(www).as_posix()
    try:
        if file.suffix.lower() != ".rpgmvo":
            return {"file": relative, **ffprobe_file(ffprobe, file)}
        with tempfile.TemporaryDirectory(prefix="audio-header-", dir=temporary) as folder:
            decoded = Path(folder) / "probe.ogg"
            decrypt_asset(file, decoded, key)
            with decoded.open("rb") as handle:
                if handle.read(4) != b"OggS":
                    raise ValueError("Decrypted audio does not have an Ogg header")
            return {"file": relative, "encrypted_header_valid": True, **ffprobe_file(ffprobe, decoded)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"file": relative, "error": str(error).replace(str(www), "<www>").replace(str(temporary), "<temporary>")}


def inspect_codec_library(library: Path, codec_names: set[str]) -> dict:
    # This loads only the codec dylib, whose sole linked dependency is libSystem.
    # It does not start NW.js, Chromium, an audio device or a renderer.
    codec = ctypes.CDLL(str(library.resolve()))
    codec.av_version_info.restype = ctypes.c_char_p
    codec.avcodec_find_decoder_by_name.argtypes = [ctypes.c_char_p]
    codec.avcodec_find_decoder_by_name.restype = ctypes.c_void_p
    return {"version": codec.av_version_info().decode("utf-8"),
            "registered_decoders": {name: bool(codec.avcodec_find_decoder_by_name(name.encode("ascii")))
                                    for name in sorted(codec_names)},
            "scope": "FFmpeg registrations only; Chromium has separate VPx/Opus decoders"}


def audit_media(www: Path, ffprobe: Path, library: Path, temporary: Path) -> dict:
    system = json.loads((www / "data/System.json").read_text(encoding="utf-8-sig"))
    files = sorted(file for category in ("movies", "audio") for file in (www / category).rglob("*")
                   if file.is_file())
    key = system["encryptionKey"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda file: inspect_media_file(www, file, ffprobe, key, temporary), files))
    errors = [row for row in rows if "error" in row]
    counts = Counter(stream["codec_name"] for row in rows if "error" not in row for stream in row["streams"])
    categories = Counter(row["file"].split("/")[0] for row in rows)
    return {"schema": 1, "file_count": len(rows), "categories": dict(categories),
            "stream_codecs": dict(counts), "metadata_errors": errors,
            "official_ffmpeg": inspect_codec_library(library, set(counts)),
            "literal_references": audit_references(www, system["hasEncryptedAudio"]),
            "files": rows, "rendered": False, "transcoded": False,
            "decrypted_audio_retained": False, "browser_canPlayType_tested": False}
