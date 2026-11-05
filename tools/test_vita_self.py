"""SELF packing checks using synthetic segments, independent of game data."""
import struct
import unittest
from vita_self import repack
from vita_text import segments


def fixture():
    d=bytearray(0x11d0)
    d[:4]=b'SCE\0'
    for p,v in [(0x10,0x1000),(0x18,len(d)-0x1000),(0x20,len(d)),
                (0x40,0xa0),(0x48,0xe0),(0x58,0x300)]:struct.pack_into('<Q',d,p,v)
    d[0xa0:0xa6]=b'\x7fELF\x01\x01'
    struct.pack_into('<H',d,0xb0,0xfe00)
    struct.pack_into('<I',d,0xbc,52)
    struct.pack_into('<H',d,0xcc,3)
    d[0x1000:0x1034]=d[0xa0:0xd4]
    headers=[(1,0xa0,0x81000000,0,0x100,0x100,5,16),
             (1,0x1a0,0x81001000,0,0x20,0x500,6,16),
             (0x6fffff01,0x1c0,0,0,0x10,0,0,16)]
    for i,h in enumerate(headers):
        struct.pack_into('<8I',d,0xe0+i*32,*h)
        struct.pack_into('<8I',d,0x1034+i*32,*h)
        struct.pack_into('<4Q',d,0x300+i*32,0x1000+h[1],h[4],1,2)
    d[0x10a0:0x11a0]=b'A'*256
    d[0x11a0:0x11c0]=b'B'*32
    d[0x11c0:0x11d0]=b'C'*16
    return bytes(d)


class SelfTests(unittest.TestCase):
    def test_noop_preserves_every_segment(self):
        source=fixture();out=repack(source,{})
        for a,b in zip(segments(source),segments(out)):
            self.assertEqual(a,b)
            self.assertEqual(source[a['off']:a['off']+a['size']],out[b['off']:b['off']+b['size']])

    def test_code_growth_moves_files_without_moving_virtual_addresses(self):
        source=fixture();out=repack(source,{0:b'A'*256+b'CODE'*64})
        before,after=segments(source),segments(out)
        self.assertEqual([s['va'] for s in before],[s['va'] for s in after])
        self.assertEqual(after[0]['size'],512)
        self.assertEqual(after[1]['off'],before[1]['off']+256)
        self.assertEqual(out[after[1]['off']:after[1]['off']+32],b'B'*32)
        self.assertEqual(out[after[2]['off']:after[2]['off']+16],b'C'*16)

    def test_text_after_bss_preserves_zero_initialization(self):
        source=fixture();payload=b'B'*32+b'\0'*(0x500-32)+b'English\0'
        out=repack(source,{1:payload});s=segments(out)[1]
        self.assertEqual(s['size'],0x508);self.assertEqual(s['memsz'],0x508)
        self.assertEqual(out[s['off']+32:s['off']+0x500],b'\0'*(0x500-32))
        self.assertEqual(out[s['off']+0x500:s['off']+0x508],b'English\0')
        for i in range(3):
            self.assertEqual(out[0xe0+i*32:0xe0+(i+1)*32],out[0x1034+i*32:0x1034+(i+1)*32])


if __name__=='__main__':unittest.main()
