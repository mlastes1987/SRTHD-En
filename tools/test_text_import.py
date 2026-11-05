"""Regression checks for runtime text loss and neighbouring-data corruption."""
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from srwtext import cmd_import, load_segments


class TextImportTests(unittest.TestCase):
    def build(self, text, slot=8):
        source = bytearray(0x3000)
        struct.pack_into(">Q", source, 0x20, 0x40)
        struct.pack_into(">HH", source, 0x36, 56, 3)
        struct.pack_into(">IIQQQQQQ", source, 0x40, 1, 5, 0, 0x10000,
                         0x10000, 0x1000, 0x1000, 0x10000)
        struct.pack_into(">IIQQQQQQ", source, 0x78, 1, 6, 0x1000, 0x11000,
                         0x11000, 0x2000, 0x50000, 0x10000)
        struct.pack_into(">IIQQQQQQ", source, 0xB0, 1, 4, 0x3000, 0, 0,
                         0, 0, 0x10000)
        source[0x2000:0x2004] = b"old\0"
        source[0x2008:0x2010] = b"KEEP ME\0"
        struct.pack_into(">II", source, 0x2100, 0x12000, 0x2000)
        entry = dict(off=0x2000, end=0x2004, slot=slot, enc="utf-8",
                     text="old", translation=text,
                     refs=[dict(pos=0x2100, vaddr=True),
                           dict(pos=0x2104, vaddr=False)])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "base").write_bytes(source)
            (p / "text.json").write_text(json.dumps([entry]))
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_import(p / "base", p / "text.json", p / "out")
            return bytes(source), (p / "out").read_bytes()

    def test_noop_is_byte_identical(self):
        source, built = self.build("old")
        self.assertEqual(source, built)

    def test_overflow_is_beyond_bss_and_mapped(self):
        source, built = self.build("Battle at the Lake")
        old = load_segments(source)[1]
        segment = load_segments(built)[2]
        self.assertGreaterEqual(segment[3], old[3] + old[6])
        va = struct.unpack_from(">I", built, 0x2100)[0]
        off = segment[2] + va - segment[3]
        self.assertEqual(built[off:off+19], b"Battle at the Lake\0")
        self.assertEqual(load_segments(source)[1], load_segments(built)[1])

    def test_alias_pointer_is_not_modified(self):
        _, built = self.build("Battle at the Lake")
        self.assertEqual(struct.unpack_from(">I", built, 0x2104)[0], 0x2000)

    def test_inflated_slot_cannot_overwrite_neighbour(self):
        source, built = self.build("Battle at the Lake", slot=32)
        self.assertEqual(source[0x2008:0x2010], built[0x2008:0x2010])


if __name__ == "__main__":
    unittest.main()
