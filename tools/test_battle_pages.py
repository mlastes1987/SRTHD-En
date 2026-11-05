"""Execute the emitted paging instructions against simulated battle buffers.

This small interpreter is intentionally limited to the emitted PPC subset.
It checks the actual machine words, branch targets and byte writes, including
both native buffer alignments, rather than duplicating the paging algorithm.
"""
import struct
import unittest
from battle_pages import assemble, CAVE, DELTA, BUFFERS, MULTI_BUFFERS
from battle_dialogue import ROOT, flatten
import json


class CPU:
    def __init__(self):
        self.code, self.hooks = assemble()
        self.r = [0] * 32
        self.mem = {}
        self.compare = 0
        self.lr = 0xabc000
        self.r[1] = 0x100000
        self.multi = 0x613720
        self.rendered = []
        self.r[31] = 0x612fa8
        self.r[2] = 0x4f3e28
        self.store(self.r[2]-0x3ab4, self.r[31], 4)
        self.store(self.r[31]+0x28, 1, 4)
        self.store(self.r[2]-0x3a28,self.multi,4)
        self.store(self.multi+0x14,1,4)

    def store(self, address, value, size=1):
        for i in range(size):
            self.mem[address+i] = (value >> (8*(size-1-i))) & 255

    def load(self, address, size=1):
        return int.from_bytes(bytes(self.mem.get(address+i, 0) for i in range(size)), 'big')

    def string(self, address):
        out = bytearray()
        while self.load(address):
            out.append(self.load(address))
            address += 1
        return out.decode('utf-8')

    def run(self, site):
        pc = self.hooks[site]
        start = CAVE+DELTA
        for _ in range(10000):
            if not start <= pc < start+len(self.code):
                if pc == 0x11f058 and site == 0x11fb80:
                    # Opaque native draw call; the draw hook is exercised
                    # separately, including the native LR/stack prologue.
                    self.rendered.append(self.string(self.load(self.multi+0x150,4)))
                    pc = self.lr
                    continue
                return pc
            w = struct.unpack_from('>I', self.code, pc-start)[0]
            op, rt, ra, rb = w >> 26, (w >> 21)&31, (w >> 16)&31, (w >> 11)&31
            imm = w & 65535
            signed = imm - 65536 if imm & 32768 else imm
            nxt = pc+4
            base = self.r[ra] if ra else 0
            if op == 14:
                self.r[rt] = (base + signed) & 0xffffffff
            elif op in (32,34):
                self.r[rt] = self.load(base+signed, 4 if op == 32 else 1)
            elif op in (36,38):
                self.store(base+signed, self.r[rt], 4 if op == 36 else 1)
            elif op == 11:
                self.compare = (self.r[ra] > signed) - (self.r[ra] < signed)
            elif op == 31:
                xo = (w >> 1)&1023
                if xo == 0:
                    self.compare = (self.r[ra] > self.r[rb]) - (self.r[ra] < self.r[rb])
                elif xo == 87:
                    self.r[rt] = self.load(base+self.r[rb])
                elif xo == 215:
                    self.store(base+self.r[rb], self.r[rt])
                elif xo == 266:
                    self.r[rt] = (self.r[ra]+self.r[rb]) & 0xffffffff
                elif xo == 444:
                    self.r[ra] = self.r[rt] | self.r[rb]
                elif xo == 339:
                    self.r[rt] = self.lr
                elif xo == 467:
                    self.lr = self.r[rt]
                else:
                    raise AssertionError(hex(w))
            elif op == 18:
                distance = w & 0x3fffffc
                if distance & 0x2000000:
                    distance -= 0x4000000
                nxt = pc+distance
                if w & 1:
                    self.lr = pc+4
            elif w == 0x4e800020:
                nxt = self.lr
            elif op == 62:
                address = (base + (signed & ~3)) & 0xffffffff
                self.store(address,self.r[rt],8)
                if w & 3 == 1:
                    self.r[ra] = address
            elif op == 16:
                cond = w & 0xffff0000
                take = {0x419e0000: self.compare == 0,
                        0x409e0000: self.compare != 0,
                        0x419c0000: self.compare < 0,
                        0x409c0000: self.compare >= 0}[cond]
                if take:
                    nxt = pc + (signed & ~3)
            else:
                raise AssertionError(hex(w))
            pc = nxt
        raise AssertionError('instruction loop exceeded bound')


class BattlePages(unittest.TestCase):
    def init(self, text, other='Short quote.'):
        cpu = CPU()
        for buf, value in zip(BUFFERS, (text,other)):
            for i,b in enumerate(('「'+value+'」').encode('utf-8')+b'\0'):
                cpu.store(cpu.r[31]+buf+i,b)
        self.assertEqual(cpu.run(0x11aa88),0x11aa8c)
        return cpu

    def test_plain_quote_and_no_active_quote(self):
        cpu = self.init('First line\n\u3000Second line')
        for buf in BUFFERS:
            cpu.store(cpu.r[31]+0x3e4,cpu.r[31]+buf,4)
            self.assertEqual(cpu.run(0x11b64c),0x11b650)
            self.assertEqual(cpu.load(cpu.r[31]+buf+104),0)
        cpu.store(cpu.r[31]+0x3e4,0,4)
        self.assertEqual(cpu.run(0x11b64c),0x11b650)

    def test_both_buffers_full_pages_and_fast_forward(self):
        text = 'One\n\u3000Two\n\u3000Three\n\u3000Four'
        for buffer_index in (0,1):
            for tick in (1,2):
                cpu = self.init(text,text)
                cpu.store(cpu.r[31]+0x28,tick,4)
                buf = cpu.r[31]+BUFFERS[buffer_index]
                next_page = buf+cpu.load(buf+104)
                self.assertEqual(cpu.string(buf),'「One\n\u3000Two')
                self.assertEqual(cpu.string(next_page),'\u3000Three\n\u3000Four」')
                cpu.store(cpu.r[31]+0x3e4,buf,4)
                original = dict(cpu.mem)
                for _ in range(240//tick):
                    self.assertEqual(cpu.run(0x11b64c),0x11b758)
                    counter = cpu.load(buf+105)
                    self.assertEqual(cpu.load(cpu.r[31]+0x3e4,4),
                                     buf if counter<120 else next_page)
                self.assertEqual(cpu.run(0x11b64c),0x11b650)
                # Native state resets the pointer; drawing restores page 2.
                cpu.store(cpu.r[31]+0x3e4,buf,4)
                cpu.r[3] = 1
                self.assertEqual(cpu.run(0x1195a0),0x1195a4)
                self.assertEqual(cpu.r[3],1)
                self.assertEqual(cpu.load(cpu.r[31]+0x3e4,4),next_page)
                allowed = set(range(cpu.r[31]+0x3e4,cpu.r[31]+0x3e8))
                allowed |= set(range(cpu.r[31]+0x768,cpu.r[31]+0x76c))
                allowed.add(buf+105)
                self.assertFalse([a for a in set(original)|set(cpu.mem)
                                  if original.get(a,0)!=cpu.mem.get(a,0) and a not in allowed])

    def test_quote_reuse_resets_page_state(self):
        cpu = self.init('One\nTwo\nThree')
        buf = cpu.r[31]+BUFFERS[0]
        cpu.store(buf+105,240)
        data = '「New short quote」'.encode('utf-8')+b'\0'
        for i,b in enumerate(data):
            cpu.store(buf+i,b)
        cpu.run(0x11aa88)
        self.assertEqual(cpu.load(buf+104),0)
        self.assertEqual(cpu.load(buf+105),0)

    @unittest.skipUnless((ROOT / "work/text/battle_dialogue_report.json").exists(), "Maintainer quote report not supplied")
    def test_entire_quote_scan_preserves_text_and_visible_line_count(self):
        report = json.loads((ROOT / 'work/text/battle_dialogue_report.json').read_text(encoding='utf-8'))
        paged = 0
        for row in report:
            cpu = self.init(row['after'])
            buf = cpu.r[31]+BUFFERS[0]
            pages = [cpu.string(buf)]
            offset = cpu.load(buf+104)
            if offset:
                pages.append(cpu.string(buf+offset))
                paged += 1
            self.assertTrue(all(len(p.splitlines())<=2 for p in pages), row['id'])
            self.assertEqual(flatten(' '.join(pages)).strip('「」'),
                             flatten(row['after']),row['id'])
        self.assertEqual(paged,28)


class MultiBattlePages(unittest.TestCase):
    def init(self,texts):
        cpu = CPU()
        cpu.r[30] = cpu.multi
        for buf,text in zip(MULTI_BUFFERS,texts):
            for i,b in enumerate(('「'+text+'」').encode('utf-8')+b'\0'):
                cpu.store(cpu.multi+buf+i,b)
        self.assertEqual(cpu.run(0x11ecd8),0x11ecdc)
        self.assertEqual(cpu.r[0],1)
        cpu.r[31] = cpu.multi
        return cpu

    def test_all_four_speakers_normal_fast_and_pointer_resets(self):
        for index in range(4):
            for tick in (1,2):
                texts = ['Short.']*4
                texts[index] = 'One\n\u3000Two\n\u3000Three'
                cpu = self.init(texts)
                cpu.store(cpu.multi+0x14,tick,4)
                buf = cpu.multi+MULTI_BUFFERS[index]
                second = buf+cpu.load(buf+104)
                cpu.store(cpu.multi+0x150,buf,4)
                before = dict(cpu.mem)
                for frame in range(240//tick):
                    self.assertEqual(cpu.run(0x11fb80),0x11fbe4)
                    counter = cpu.load(buf+105)
                    expected = buf if counter<120 else second
                    self.assertEqual(cpu.load(cpu.multi+0x150,4),expected)
                    self.assertEqual(cpu.rendered[-1],cpu.string(expected))
                    self.assertEqual(cpu.r[30],0)  # keep sequence running
                self.assertEqual(len(cpu.rendered),240//tick)
                self.assertEqual(cpu.run(0x11fb80),0x11fb84)
                allowed = set(range(cpu.multi+0x150,cpu.multi+0x154))|{buf+105}
                self.assertFalse([a for a in set(before)|set(cpu.mem)
                                  if before.get(a,0)!=cpu.mem.get(a,0) and a not in allowed])
                # Native delay state writes first pointer; draw hook restores
                # page two and preserves caller LR and the draw argument.
                cpu.store(cpu.multi+0x150,buf,4)
                cpu.r[3],cpu.lr = 0,0xabc000
                stack = cpu.r[1]
                self.assertEqual(cpu.run(0x11f058),0x11f05c)
                self.assertEqual(cpu.lr,0xabc000)
                self.assertEqual(cpu.r[3],0)
                self.assertEqual(cpu.r[1],stack-0xe0)
                self.assertEqual(cpu.load(stack-0xe0,8),stack)
                self.assertEqual(cpu.load(cpu.multi+0x150,4),second)

    def test_short_and_empty_text_do_not_hold_sequence(self):
        cpu = self.init(['Short.','Two\nLines','','Last.'])
        for buf in MULTI_BUFFERS:
            cpu.store(cpu.multi+0x150,cpu.multi+buf,4)
            self.assertEqual(cpu.run(0x11fb80),0x11fb84)
        cpu.store(cpu.multi+0x150,0,4)
        self.assertEqual(cpu.run(0x11fb80),0x11fb84)
        self.assertFalse(cpu.rendered)

    def test_speaker_change_and_buffer_reuse(self):
        texts = ['One\nTwo\nThree']*4
        cpu = self.init(texts)
        for index,buf_offset in enumerate(MULTI_BUFFERS):
            buf = cpu.multi+buf_offset
            cpu.store(cpu.multi+0x150,buf,4)
            self.assertEqual(cpu.load(buf+105),0)
            self.assertEqual(cpu.run(0x11fb80),0x11fbe4)
            self.assertEqual(cpu.load(buf+105),1)
        # A new multi-unit attack reinitializes all four independent timers.
        cpu.r[30] = cpu.multi
        for buf in MULTI_BUFFERS:
            for i,b in enumerate(b'Fresh quote\0'):
                cpu.store(cpu.multi+buf+i,b)
        cpu.run(0x11ecd8)
        self.assertTrue(all(cpu.load(cpu.multi+buf+104)==0 and
                            cpu.load(cpu.multi+buf+105)==0 for buf in MULTI_BUFFERS))

    @unittest.skipUnless((ROOT / "work/text/battle_dialogue_report.json").exists(), "Maintainer quote report not supplied")
    def test_all_scanned_quotes_fit_in_each_multi_buffer(self):
        report = json.loads((ROOT/'work/text/battle_dialogue_report.json').read_text(encoding='utf-8'))
        for row in report:
            cpu = self.init([row['after']]*4)
            for buf_offset in MULTI_BUFFERS:
                buf = cpu.multi+buf_offset
                pages = [cpu.string(buf)]
                if cpu.load(buf+104):
                    pages.append(cpu.string(buf+cpu.load(buf+104)))
                self.assertTrue(all(len(p.splitlines())<=2 for p in pages),row['id'])
                self.assertEqual(flatten(' '.join(pages)).strip('「」'),
                                 flatten(row['after']),row['id'])


if __name__ == '__main__':
    unittest.main()
