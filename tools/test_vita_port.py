"""Safety checks for the initial Vita port, independent of private game files."""
import csv
import io
from pathlib import Path
import struct
import tempfile
import unittest
from PIL import Image
from vita_text import build, segments
from vita_gxt import decode, encode, encode_region, positions
import json


def self_fixture():
    d=bytearray(0x2000)
    d[:4]=b'SCE\0'
    struct.pack_into('<Q',d,0x40,0xa0)
    struct.pack_into('<Q',d,0x48,0xe0)
    struct.pack_into('<Q',d,0x58,0x140)
    d[0xa0:0xa6]=b'\x7fELF\x01\x01'
    struct.pack_into('<H',d,0xa0+44,1)
    struct.pack_into('<8I',d,0xe0,1,0,0x81000000,0,0x1000,0x1000,5,16)
    struct.pack_into('<4Q',d,0x140,0x1000,0x1000,1,2)
    return d


class TextSafety(unittest.TestCase):
    def translate(self,d,rows):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'text.csv'
            with p.open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['japanese','english'])
                w.writeheader();w.writerows(rows)
            return build(bytes(d),p)

    def test_shorter_preserves_neighbor_and_pointers(self):
        d=self_fixture();raw='味方'.encode()+b'\0'
        d[0x1100:0x1100+len(raw)]=raw
        d[0x1108:0x1110]=b'NEIGHBOR'
        struct.pack_into('<I',d,0x1200,0x81000100)
        result,r=self.translate(d,[dict(japanese='味方',english='Allies')])
        self.assertEqual(result[0x1100:0x1107],b'Allies\0')
        self.assertEqual(result[0x1108:],d[0x1108:])
        self.assertEqual(r['counts'],{'translated':1})

    def test_overflow_and_ambiguity_are_unchanged(self):
        d=self_fixture();d[0x1100:0x1104]='空'.encode()+b'\0'
        result,r=self.translate(d,[dict(japanese='空',english='Longer than slot')])
        self.assertEqual(result,d);self.assertEqual(r['counts'],{'overflow':1})
        result,r=self.translate(d,[dict(japanese='空',english='Air'),dict(japanese='空',english='A')])
        self.assertEqual(result,d);self.assertEqual(r['counts'],{'ambiguous':1})

    def test_suffix_match_is_not_replaced(self):
        d=self_fixture();raw='大空'.encode()+b'\0'
        d[0x1100:0x1100+len(raw)]=raw
        result,r=self.translate(d,[dict(japanese='空',english='Air')])
        self.assertEqual(result,d);self.assertEqual(r['counts'],{})

    def test_interior_pointer_protects_merged_literal(self):
        d=self_fixture();raw='大空'.encode()+b'\0'
        d[0x1100:0x1100+len(raw)]=raw
        struct.pack_into('<I',d,0x1200,0x81000103)
        result,r=self.translate(d,[dict(japanese='大空',english='Sky')])
        self.assertEqual(result,d)
        self.assertEqual(r['counts'],{'interior_reference':1})

    def test_encrypted_input_rejected(self):
        d=self_fixture();struct.pack_into('<Q',d,0x140+24,1)
        with self.assertRaises(ValueError):segments(d)


class TextureSafety(unittest.TestCase):
    def fixture(self,layout):
        w,h=8,4;d=bytearray(64+w*h+1024)
        d[:4]=b'GXT\0';struct.pack_into('<7I',d,4,0x10000003,1,64,w*h+1024,0,1,0)
        struct.pack_into('<6IHHI',d,32,64,w*h,0,0,layout,0x95000000,w,h,1)
        return bytes(d)

    def test_swizzle_is_permutation(self):
        self.assertEqual(sorted(positions(8,4,0)),list(range(32)))
        self.assertEqual(sorted(positions(4,8,0)),list(range(32)))

    def test_region_preserves_palette_and_other_pixels(self):
        for layout in (0,0x60000000):
            original=encode(self.fixture(layout),Image.new('RGBA',(8,4),(255,255,255,255)))
            packed=encode_region(original,Image.new('RGBA',(2,2),(0,0,0,0)),(2,1,4,3))
            before=decode(original);after=decode(packed)
            self.assertEqual(packed[-1024:],original[-1024:])
            self.assertEqual(packed[:64],original[:64])
            for y in range(4):
                for x in range(8):
                    if not (2<=x<4 and 1<=y<3):
                        self.assertEqual(after.getpixel((x,y)),before.getpixel((x,y)))
            self.assertEqual(after.getpixel((2,1))[3],0)
        # A dark frame color elsewhere in the palette must not enter white text.
        native=bytearray(self.fixture(0x60000000))
        native[64:96]=bytes([1])*32
        native[96+4:96+8]=bytes([255,255,255,255])
        native[96+8:96+12]=bytes([0,40,100,255])
        target=Image.new('RGBA',(2,2),(0,40,100,255))
        unrestricted=encode_region(bytes(native),target,(2,1,4,3))
        restricted=encode_region(bytes(native),target,(2,1,4,3),use_region_palette=True)
        self.assertEqual(decode(unrestricted).getpixel((2,1)),(0,40,100,255))
        self.assertEqual(decode(restricted).getpixel((2,1)),(255,255,255,255))


    def test_palette_alpha_and_layout_roundtrip(self):
        im=Image.new('RGBA',(8,4))
        im.putdata([(255,0,0,255) if x%2 else (0,80,255,0) for x in range(32)])
        for layout in (0,0x60000000):
            original=self.fixture(layout)
            packed=encode(original,im)
            self.assertEqual(packed[:64],original[:64])
            self.assertEqual(decode(packed).tobytes(),im.tobytes())


class BonusLayout(unittest.TestCase):
    def test_two_native_rows_keep_six_values_without_line_breaks(self):
        root=Path(__file__).parent
        overrides=json.loads((root/'vita_text_overrides.json').read_text(encoding='utf8'))
        metrics=json.loads((root/'vita_font_metrics.json').read_text())
        for address,count in [('0x128ac8',4),('0x128b04',2)]:
            text=overrides[address]['english']
            self.assertEqual(text.count('%d'),count)
            self.assertNotIn('\n',text)
            self.assertLessEqual(sum(int(metrics[c]['advance']*38+metrics[c].get('adjust_px',0))
                                     for c in text % tuple([99]*count)),800)


if __name__=='__main__':unittest.main()
