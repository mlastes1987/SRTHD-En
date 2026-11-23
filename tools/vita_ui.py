"""Reviewed native Vita banner regions and source-guarded team-pane correction."""
import struct
from ssad import chunks,decode_name
from vita_arm import immediate
from map_end import vita_changes as map_end_changes

MENU_REGIONS=((0,64,328,128),(336,64,508,128),(0,128,512,192),(0,192,512,256))


def playtest_layout_changes():
    # The deployment screen feeds pre-encoded two-byte glyphs to the raw draw calls.
    for pc in (0x8100f8ce, 0x8100f93a, 0x8100fe2c, 0x8100fe58, 0x8100fed6):
        yield pc, bytes.fromhex('0021'), bytes.fromhex('0121')

    # Both five-row weapon menus used to add the name width to the P icon's X.
    # Place the icon at X=672, before the Power column, regardless of name width.
    constant = bytes.fromhex('c4f25a00')
    for start, stride, delta, add, move in (
        (0x8106eb2c, 0x160, 0x18, '30ee010b', 'b0ee410b'),
        (0x81070240, 0x136, 0x20, '30ee023b', 'b0ee423b'),
    ):
        for index in range(5):
            pc = start + stride * index
            yield pc, constant, immediate(constant, 0x4085)
            yield pc + delta, bytes.fromhex(add), bytes.fromhex(move)

    yield from map_end_changes()


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
