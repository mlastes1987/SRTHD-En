"""Reviewed native Vita banner regions and source-guarded team-pane correction."""
import struct
from ssad import chunks,decode_name

MENU_REGIONS=((0,64,328,128),(336,64,508,128),(0,128,512,192),(0,192,512,256))


def team_banner(original):
    """Render the complete English team label once, centered and readable."""
    data=bytearray(original);pane='';found=set()
    changes={('part 4','POSX'):(219000,271000),
             ('part 4','SCAX'):(1000,1600),('part 4','SCAY'):(1000,1600),
             ('part 5','TRAN'):(1000,0)}
    for tag,payload,offset in chunks(original):
        if tag=='NAME':pane=decode_name(payload)
        key=(pane,tag)
        if key not in changes:continue
        before,after=changes[key]
        if len(payload)!=32 or struct.unpack_from('<i',payload,16)[0]!=before:
            raise ValueError('Team banner source changed: '+str(key))
        if key in found:raise ValueError('Duplicate team banner property')
        struct.pack_into('<i',data,offset+24,after);found.add(key)
    if found!=set(changes):raise ValueError('Missing team banner properties')
    return bytes(data)
