"""Two-page battle quote support, after the proportional font patch.

Native balloons expose a pointer at battle+0x3e4 (normal) or +0x150
(multi-unit), backed by two or four 121-byte quote buffers respectively.
Split a third display line into a second NUL-terminated page
after the native quote copies. Reserve unused tail bytes 104/105 for its
offset/timer. Hold the battle state machine for 120 ticks per page, while
retaining its normal render path. No new text control codes or global memory.
"""
from pathlib import Path
import json
import struct
from proportional_font import Code, BASE, ROOT

CAVE = 0x4BDD00
DELTA = 0x10000
BUFFERS = (0x3E8, 0x461)
MULTI_BUFFERS = (0x154, 0x1CD, 0x246, 0x2BF)
TICKS = 120


class Asm(Code):
    def branch(self, target, condition=None, link=False):
        super().branch(target, None, link)
        if condition:
            self.fixups[-1] = (*self.fixups[-1][:2], condition, link)

    def finish(self):
        conditions = {'eq': 0x419E0000, 'ne': 0x409E0000,
                      'lt': 0x419C0000, 'ge': 0x409C0000}
        for index, target, cond, link in self.fixups:
            target = self.labels[target] if isinstance(target, str) else target
            distance = target - (self.start + index*4)
            assert distance % 4 == 0
            if cond:
                assert -32768 <= distance < 32768
                self.words[index] = conditions[cond] | (distance & 0xfffc)
            else:
                assert -(1 << 25) <= distance < (1 << 25)
                self.words[index] = 0x48000000 | (distance & 0x3fffffc) | int(link)
        return b''.join(struct.pack('>I', w) for w in self.words)

    def cmp(self, reg, value):
        self.emit(0x2F800000 | reg << 16 | value & 0xffff)

    def cmpreg(self, a, b):
        self.emit(0x7F800000 | a << 16 | b << 11)


def assemble():
    c = Asm(CAVE + DELTA)
    hooks = {}

    # All init/update sites are after prologues that already saved the caller's
    # LR, so the shared workers can use bl/blr without another stack frame.
    for site, base, buffers, displaced in (
            (0x11AA88, 31, BUFFERS, (32,29,31,0x6c0)),
            (0x11ECD8, 30, MULTI_BUFFERS, (14,0,0,1))):
        hooks[site] = c.pc
        for buf in buffers:
            c.d(14,9,base,buf)
            c.branch('split_buffer',link=True)
        c.d(*displaced)
        c.branch(site+4)

    def find(buffers, pointer):
        c.d(32,8,12,pointer)
        c.d(14,9,12,buffers[0])
        c.d(14,7,0,len(buffers))
        c.branch('find_buffer',link=True)
        c.cmp(10,0)

    for prefix, site, buffers, pointer, ticks, resume, render in (
            ('single',0x11B64C,BUFFERS,0x3e4,0x28,0x11B650,0x11B758),
            ('multi',0x11FB80,MULTI_BUFFERS,0x150,0x14,0x11FB84,0x11FBE4)):
        hooks[site] = c.pc
        c.or_(12,31,31)
        find(buffers,pointer)
        c.branch(prefix+'_resume','eq')
        c.d(34,11,9,105)
        c.cmp(11,TICKS*2)
        c.branch(prefix+'_resume','ge')
        c.d(32,0,12,ticks)
        c.add(11,11,0)
        c.d(38,11,9,105)
        c.cmp(11,TICKS)
        c.branch(prefix+'_hold','lt')
        c.add(10,9,10)
        c.d(36,10,12,pointer)
        c.label(prefix+'_hold')
        if prefix == 'single':
            c.d(14,0,0,0)
            c.d(36,0,12,0x768)
        else:
            # Multi-unit rendering normally lives inside each state. Draw it
            # explicitly while holding the state, then take the running return.
            c.d(14,3,0,0)
            c.branch(0x11F058,link=True)
            c.d(14,30,0,0)
        c.branch(render)
        c.label(prefix+'_resume')
        c.d(32,9 if prefix=='single' else 0,31,0x24 if prefix=='single' else 0x2c)
        c.branch(resume)

    for prefix,site,buffers,pointer,toc in (
            ('single_draw',0x1195A0,BUFFERS,0x3e4,-0x3ab4),
            ('multi_draw',0x11F058,MULTI_BUFFERS,0x150,-0x3a28)):
        hooks[site] = c.pc
        # These hooks precede the native LR save. Preserve it across find().
        c.emit(0x7CC802A6)  # mflr r6
        c.d(32,12,2,toc)
        find(buffers,pointer)
        c.branch(prefix+'_resume','eq')
        c.d(34,11,9,105)
        c.cmp(11,TICKS)
        c.branch(prefix+'_resume','lt')
        c.add(10,9,10)
        c.d(36,10,12,pointer)
        c.label(prefix+'_resume')
        c.emit(0x7CC803A6)  # mtlr r6
        if prefix=='single_draw':
            c.cmp(3,2)
        else:
            c.d(62,1,1,-0xe0)
            c.words[-1] |= 1  # displaced stdu, including DS update bit
        c.branch(site+4)

    c.label('split_buffer')
    c.d(14,8,0,0)
    c.d(38,8,9,104)
    c.d(38,8,9,105)
    c.d(14,10,0,0)
    c.d(14,11,0,0)
    c.label('scan')
    c.emit((31<<26)|(12<<21)|(9<<16)|(11<<11)|(87<<1))
    c.cmp(12,0)
    c.branch('split_end','eq')
    c.cmp(12,10)
    c.branch('scan_next','ne')
    c.d(14,10,10,1)
    c.cmp(10,2)
    c.branch('scan_next','ne')
    c.emit((31<<26)|(8<<21)|(9<<16)|(11<<11)|(215<<1))
    c.d(14,11,11,1)
    c.d(38,11,9,104)
    c.branch('split_end')
    c.label('scan_next')
    c.d(14,11,11,1)
    c.cmp(11,104)
    c.branch('scan','lt')
    c.label('split_end')
    c.emit(0x4E800020)  # blr

    c.label('find_buffer')
    c.d(34,10,9,104)
    c.cmp(10,0)
    c.branch('find_next','eq')
    c.cmpreg(8,9)
    c.branch('find_end','eq')
    c.add(11,9,10)
    c.cmpreg(8,11)
    c.branch('find_end','eq')
    c.label('find_next')
    c.d(14,9,9,121)
    c.d(14,7,7,-1)
    c.cmp(7,0)
    c.branch('find_buffer','ne')
    c.d(14,10,0,0)
    c.label('find_end')
    c.emit(0x4E800020)
    blob = c.finish()
    assert CAVE + len(blob) <= 0x4BE000
    return blob, hooks


def patch(image):
    d = bytearray(image.read_bytes())
    source = BASE.read_bytes()
    blob, hooks = assemble()
    assert not any(d[CAVE:CAVE+len(blob)]), 'page cave occupied'
    d[CAVE:CAVE+len(blob)] = blob
    for site, target in hooks.items():
        off = site - DELTA
        assert d[off:off+4] == source[off:off+4], hex(site)
        branch = Asm(site)
        branch.branch(target)
        d[off:off+4] = branch.finish()
    image.write_bytes(d)
    report = dict(cave=hex(CAVE+DELTA), code_bytes=len(blob),
                  ticks_per_page=TICKS,
                  normal_buffers=[hex(b) for b in BUFFERS],
                  multi_buffers=[hex(b) for b in MULTI_BUFFERS],
                  hooks={hex(k):hex(v) for k,v in hooks.items()})
    (ROOT / 'work/text/battle_pages_patch.json').write_text(json.dumps(report, indent=2))
    print('Battle pages:', report)


if __name__ == '__main__':
    patch(ROOT / 'build/EBOOT.BIN')
