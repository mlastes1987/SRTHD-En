"""Repack decrypted fixed-address PCSG00260 SELF segments.

PCSG00260 is ET_SCE_EXEC (0xfe00). Its final segment is SCE comment data,
not an ARM relocation stream. Runtime pointers use the fixed segment VAs.
"""
import struct
from vita_text import segments


def repack(source,payloads,memsizes=None):
    """Replace segment payloads by index, preserving VAs and header metadata."""
    memsizes=memsizes or {}
    segs=segments(source)
    header_size=struct.unpack_from('<Q',source,0x10)[0]
    elf_off,ph_off,si_off=(struct.unpack_from('<Q',source,p)[0] for p in (0x40,0x48,0x58))
    if struct.unpack_from('<H',source,elf_off+16)[0]!=0xfe00:
        raise ValueError('This packer requires fixed-address ET_SCE_EXEC')
    real_ph=struct.unpack_from('<I',source,elf_off+28)[0]
    first_offset=min(struct.unpack_from('<I',source,ph_off+i*32+4)[0] for i in range(len(segs)))
    out=bytearray(source[:header_size]+source[header_size:header_size+first_offset])
    for i,s in enumerate(segs):
        payload=payloads.get(i,source[s['off']:s['off']+s['size']])
        ph=list(struct.unpack_from('<8I',source,ph_off+i*32))
        align=max(ph[7],16)
        relative=(len(out)-header_size+align-1)//align*align
        out.extend(b'\0'*(header_size+relative-len(out)))
        ph[1]=relative;ph[4]=len(payload)
        if s['type']==1:ph[5]=memsizes.get(i,max(ph[5],len(payload)))
        struct.pack_into('<8I',out,ph_off+i*32,*ph)
        struct.pack_into('<8I',out,header_size+real_ph+i*32,*ph)
        struct.pack_into('<4Q',out,si_off+i*32,header_size+relative,len(payload),1,2)
        out.extend(payload)
    struct.pack_into('<QQ',out,0x18,len(out)-header_size,len(out))
    segments(out)
    return bytes(out)
