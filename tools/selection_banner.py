"""Fix the English team header's duplicate shared suffix in a local CPK.

python tools/selection_banner.py CURRENT_KDATAPS3.CPK REPLACEMENT_DIRECTORY
Then rebuild only entry 32 with tools/cpk.py, using that current CPK template.
"""
from pathlib import Path
import struct
import sys
from cpk import Cpk, crilayla_decompress
from ssad import chunks, decode_name, parse


def main():
    if len(sys.argv)!=3:
        raise SystemExit(__doc__)
    archive,out=map(Path,sys.argv[1:])
    cpk=Cpk(str(archive))
    row=next(r for r in cpk.files if int(r['FileName'].split('.')[0])==32)
    original=cpk.payload(row)
    if original.startswith(b'CRILAYLA'):
        original=crilayla_decompress(original)
    data=bytearray(original)
    pane=''; changes=0
    for tag,payload,offset in chunks(original):
        if tag=='NAME':
            pane=decode_name(payload)
        if pane=='part 4' and tag=='POSX':
            value=struct.unpack_from('<i',payload,16)[0]
            if value not in (219000,271000):
                raise ValueError('Unsupported team-label origin')
            struct.pack_into('<i',data,offset+24,271000)
            changes+=1
        if pane=='part 5' and tag=='TRAN':
            if len(payload)!=32 or struct.unpack_from('<i',payload,16)[0] not in (0,1000):
                raise ValueError('Unsupported shared-suffix opacity track')
            struct.pack_into('<i',data,offset+24,0)
            changes+=1
    if changes!=2 or parse(original)!=parse(bytes(data)):
        raise ValueError('Unexpected team selector layout')
    out.mkdir(parents=True,exist_ok=True)
    (out/'00032.bin').write_bytes(data)
    print('Prepared entry 32: centered full label and hidden duplicate suffix.')


if __name__=='__main__':
    main()
