"""Space the MAP labels and percentages in 1280-pixel UI coordinates."""

import struct
from pathlib import Path

# The PS3 reads these coordinates from its MAP strip float table. Vita
# loads the same floats with MOVT after zeroing the lower half of the word.
# Each row is a PS3 file offset, a Vita VA, original x, and translated x.
COLUMNS = (
    (0x4DE1B8, 0x81049B34, 720, 696),   # Evade
    (0x4DE1BC, 0x81049B84, 816, 824),   # Evade percentage
    (0x4DE1C0, 0x81049BC8, 984, 964),   # Recover
    (0x4DE1C4, 0x81049C18, 1080, 1136), # Recover percentage
)
VITA_ORIGINAL = tuple(bytes.fromhex(word) for word in (
    "c4f23440", "c4f24c41", "c4f27640", "c4f28740",
))


def patch_ps3(path):
    path = Path(path)
    data = bytearray(path.read_bytes())
    for offset, _, old, new in COLUMNS:
        if data[offset:offset + 4] != struct.pack(">f", old):
            raise ValueError(f"Unexpected PS3 MAP coordinate at {offset:#x}")
        struct.pack_into(">f", data, offset, new)
    path.write_bytes(data)


def vita_changes():
    from vita_arm import immediate

    for (_, address, _, x), original in zip(COLUMNS, VITA_ORIGINAL):
        bits, = struct.unpack(">I", struct.pack(">f", x))
        if bits & 0xFFFF:
            raise ValueError(f"MAP x coordinate cannot be loaded with MOVT: {x}")
        yield address, original, immediate(original, bits >> 16)
