"""Prevent previews/backups from silently replacing numbered binary payloads."""
from pathlib import Path
import tempfile
import unittest
from cpk import read_replacements


class ReplacementTests(unittest.TestCase):
    def test_one_payload_per_id(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'00118.bin').write_bytes(b'GXT\0binary')
            (p/'README.txt').write_text('Separate previews from replacements')
            self.assertEqual(read_replacements(temp),{118:b'GXT\0binary'})

    def test_duplicate_preview_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'00118.bin').write_bytes(b'GXT\0binary')
            (p/'00118.png').write_bytes(b'PNG preview')
            with self.assertRaisesRegex(ValueError,'Duplicate replacement ID 00118'):
                read_replacements(temp)


if __name__=='__main__':unittest.main()
