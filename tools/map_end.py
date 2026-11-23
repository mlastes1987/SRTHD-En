"""Right-align the map-clear end label in both native preview renderers."""
from pathlib import Path
import struct

RIGHT_EDGE = 1140


def patch_ps3(path):
    path = Path(path)
    data = bytearray(path.read_bytes())
    changes = {
        0x4de2b8: (struct.pack(">f", 1052), struct.pack(">f", RIGHT_EDGE)),
        0x4de348: (struct.pack(">f", 1052), struct.pack(">f", RIGHT_EDGE)),
        0xbe18c: (bytes.fromhex("38800002"), bytes.fromhex("38800003")),
        0xbec9c: (bytes.fromhex("38800002"), bytes.fromhex("38800003")),
    }
    for offset, (before, after) in changes.items():
        if data[offset:offset + 4] != before:
            raise ValueError(f"Unexpected PS3 map-end field at {offset:#x}")
        data[offset:offset + 4] = after
    path.write_bytes(data)


def vita_changes():
    from vita_arm import immediate

    # Both callers already load 0x8000 into the low half of the float.
    bits, = struct.unpack(">I", struct.pack(">f", RIGHT_EDGE))
    assert bits & 0xffff == 0x8000
    for coordinate, alignment in ((0x8104a51a, 0x8104a552), (0x8104ae32, 0x8104ae6a)):
        before = bytes.fromhex("c4f28340")
        yield coordinate, before, immediate(before, bits >> 16)
        yield alignment, bytes.fromhex("0221"), bytes.fromhex("0321")
