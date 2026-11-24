"""Give the full unit-list header its own texture region."""
import struct

from ssad import chunks, decode_name

UNIT_LIST_BOX = (288, 832, 512, 896)


def patch(original):
    """Replace the borrowed Withdraw fragment and hide the Japanese suffix."""
    if original[:4] != b"SSAD":
        raise ValueError("Unit list layout is not SSAD")
    data = bytearray(original)
    name = ""
    area = None
    found = set()
    for tag, payload, offset in chunks(original):
        if tag == "PART":
            name, area = "", None
        elif tag == "NAME":
            name = decode_name(payload)
        elif tag == "AREA":
            area = struct.unpack("<4I", payload)
        if name == "part 4" and area == (0, 704, 200, 768):
            if tag == "AREA":
                struct.pack_into("<4I", data, offset + 8, *UNIT_LIST_BOX)
                found.add("sprite")
            elif tag == "ORGX" and payload == struct.pack("<i", 256):
                struct.pack_into("<i", data, offset + 8, 112)
                found.add("origin")
            elif tag == "POSX" and payload == struct.pack("<8i", 1, 10000, 1, 0, 357000, 1, 0, 0):
                struct.pack_into("<i", data, offset + 24, 270000)
                found.add("position")
        if name == "part 1" and area == (360, 704, 496, 768) and tag == "TRAN":
            if payload != struct.pack("<8i", 1, 10000, 1, 0, 1000, 1, 0, 0):
                raise ValueError("Unexpected Unit List suffix transparency")
            struct.pack_into("<i", data, offset + 24, 0)
            found.add("suffix")
    if found != {"sprite", "origin", "position", "suffix"}:
        raise ValueError("Could not identify the complete Unit List layout")
    return bytes(data)
