"""Translate the fixed-width terrain names outside the PS3 text banks."""

from pathlib import Path

TABLE_OFFSET = 0x51432C
RECORD_SIZE = 40
NAME_SIZE = 16
NAMES = (
    ("進入不可", "Blocked"),
    ("平地", "Plains"),
    ("森", "Forest"),
    ("海", "Sea"),
    ("山", "Mountain"),
    ("床", "Floor"),
    ("床", "Floor"),
    ("柱", "Pillar"),
    ("穴", "Pit"),
    ("タワー／基地", "Tower"),
    ("本拠地", "HQ"),
    ("宇宙空間", "Space"),
    ("暗礁宙域", "Asteroid"),
    ("要塞", "Fortress"),
    ("川", "River"),
    ("池", "Pond"),
    ("湖", "Lake"),
)


def translate_terrain(path):
    path = Path(path)
    data = bytearray(path.read_bytes())
    for index, (japanese, english) in enumerate(NAMES):
        start = TABLE_OFFSET + index * RECORD_SIZE
        end = start + NAME_SIZE
        expected = japanese.encode("cp932").ljust(NAME_SIZE, b"\0")
        record_id = data[start + 36:start + RECORD_SIZE]
        if data[start:end] != expected or record_id != index.to_bytes(4, "big"):
            raise ValueError(f"Unexpected PS3 terrain record at {start:#x}")
        translated = english.encode("ascii") + b"\0"
        if len(translated) > NAME_SIZE:
            raise ValueError(f"Terrain name exceeds fixed field: {english}")
        data[start:end] = translated.ljust(NAME_SIZE, b"\0")
    path.write_bytes(data)
