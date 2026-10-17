from __future__ import annotations

from pathlib import Path


RPG_MAKER_MV_HEADER = bytes.fromhex("5250474d560000000003010000000000")
PNG_SIGNATURE = bytes.fromhex("89504e470d0a1a0a")


def decrypt_asset(source: Path, destination: Path, key_hex: str) -> None:
    encrypted = source.read_bytes()
    if not encrypted.startswith(RPG_MAKER_MV_HEADER):
        raise ValueError(f"Unexpected encrypted asset header: {source}")
    payload = _xor_prefix(encrypted[len(RPG_MAKER_MV_HEADER) :], _decode_key(key_hex))
    if source.suffix.lower() == ".rpgmvp" and not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"Decrypted asset is not a PNG: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def encrypt_png(source: Path, destination: Path, key_hex: str) -> None:
    payload = source.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"Source is not a PNG: {source}")
    encrypted = RPG_MAKER_MV_HEADER + _xor_prefix(payload, _decode_key(key_hex))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encrypted)


def _decode_key(key_hex: str) -> bytes:
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as error:
        raise ValueError("Encryption key must be hexadecimal") from error
    if len(key) != 16:
        raise ValueError(f"Encryption key must be 16 bytes, got {len(key)}")
    return key


def _xor_prefix(payload: bytes, key: bytes) -> bytes:
    prefix_length = min(16, len(payload))
    prefix = bytes(payload[index] ^ key[index] for index in range(prefix_length))
    return prefix + payload[prefix_length:]

