"""Execute Vita font hooks in Unicorn; no emulator UI or game process needed."""
import json
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path('work/vita/deps').resolve()))
try:
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
    from unicorn.arm_const import *
    HAS_UNICORN=True
except ImportError:
    HAS_UNICORN=False
from vita_runtime import assemble,CAVE,HOOKS,FONT_METRICS,toolchain


def bits(v):return struct.unpack('<I',struct.pack('<f',v))[0]
def floating(v):return struct.unpack('<f',struct.pack('<I',v))[0]


@unittest.skipUnless(HAS_UNICORN,'Install Unicorn to execute ARM runtime tests')
class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:toolchain()
        except FileNotFoundError as exc:raise unittest.SkipTest(str(exc))
        cls.blob,cls.labels=assemble(Path('work/vita'))
        cls.metrics=json.loads(FONT_METRICS.read_text(encoding='utf8'))

    def machine(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x81000000,0x400000)
        u.mem_map(0x70000000,0x20000)
        u.mem_write(CAVE,self.blob)
        u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000)
        u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
        return u

    def execute(self,u,label,end):
        u.reg_write(UC_ARM_REG_SP,0x70010000)
        for reg in (UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R12,UC_ARM_REG_LR):u.reg_write(reg,0x12345678)
        u.reg_write(UC_ARM_REG_APSR,0x60000000)
        u.emu_start(self.labels[label]|1,end,count=500)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),end)
        self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x70010000)
        for reg in (UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R12,UC_ARM_REG_LR):self.assertEqual(u.reg_read(reg),0x12345678)
        self.assertEqual(u.reg_read(UC_ARM_REG_APSR)&0xf0000000,0x60000000)

    def test_every_ascii_glyph_measurement_matches_ps3(self):
        for size in (12,22,30,38):
            for ch,m in self.metrics.items():
                expected=int(m['advance']*size+m['adjust_px'])
                for label,field,end in [('measure_class',0x48,0x81009cd0),
                                        ('measure_default',0x38,0x81009cd6),
                                        ('measure_plain',0x14,0x81009ce8)]:
                    u=self.machine()
                    u.reg_write(UC_ARM_REG_R11,0x70001000)
                    u.mem_write(0x70001000+field,struct.pack('<f',size))
                    u.reg_write(UC_ARM_REG_R2,m['sjis'])
                    self.execute(u,label,end)
                    self.assertEqual(floating(u.reg_read(UC_ARM_REG_S3)),expected,(ch,size,label))

    def test_draw_advance_and_bearing_match_ps3(self):
        for ch,m in self.metrics.items():
            u=self.machine();u.reg_write(UC_ARM_REG_R8,m['glyph'])
            u.reg_write(UC_ARM_REG_S18,bits(100));u.reg_write(UC_ARM_REG_S19,bits(38))
            self.execute(u,'draw_bearing',0x81009522)
            self.assertAlmostEqual(floating(u.reg_read(UC_ARM_REG_S0)),100-m['left']*38)
            self.execute(u,'draw_advance',0x81009568)
            self.assertEqual(floating(u.reg_read(UC_ARM_REG_S18)),100+int(m['advance']*38+m['adjust_px']))

    def test_japanese_glyph_keeps_native_advance(self):
        u=self.machine();u.reg_write(UC_ARM_REG_R8,1000)
        u.reg_write(UC_ARM_REG_S18,bits(100));u.reg_write(UC_ARM_REG_S21,bits(35))
        self.execute(u,'draw_advance',0x81009568)
        self.assertEqual(floating(u.reg_read(UC_ARM_REG_S18)),135)

    def call_worker(self,u,name):
        end=0x81001000
        u.reg_write(UC_ARM_REG_SP,0x70010000)
        u.reg_write(UC_ARM_REG_LR,end|1)
        u.emu_start(self.labels[name]|1,end,count=2000)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),end)
        self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x70010000)

    def test_deployment_button_labels_get_independent_origins(self):
        overrides = json.loads(FONT_METRICS.with_name('vita_text_overrides.json').read_text(encoding='utf8'))
        for label, literal, expected in (
            ('draw_deploy_choices', '0xd5250', [(508, 'Ｃｏｎｆｉｒｍ'), (720, 'Ｂａｃｋ')]),
            ('draw_deploy_start', '0xd52c0', [(236, 'Ｄｅｐｌｏｙ')]),
        ):
            u=self.machine()
            raw=overrides[literal]['english'].encode('cp932')+b'\0'
            u.mem_write(0x70002000,raw)
            u.mem_write(0x81009d18,b'\x70\x47') # bx lr
            calls=[]
            def capture(machine, address, size, state):
                pointer=machine.reg_read(UC_ARM_REG_R0)
                text=bytes(machine.mem_read(pointer,20)).split(b'\0',1)[0].decode('cp932')
                calls.append((floating(machine.reg_read(UC_ARM_REG_S0)),text))
                self.assertEqual(machine.reg_read(UC_ARM_REG_R1),1)
                self.assertEqual(machine.reg_read(UC_ARM_REG_R2),0)
                self.assertEqual(floating(machine.reg_read(UC_ARM_REG_S1)),85)
                self.assertEqual(floating(machine.reg_read(UC_ARM_REG_S2)),36)
                machine.reg_write(UC_ARM_REG_S1,bits(0))
                machine.reg_write(UC_ARM_REG_S2,bits(0))
            u.hook_add(UC_HOOK_CODE,capture,begin=0x81009d18,end=0x81009d18)
            u.reg_write(UC_ARM_REG_R0,0x70002000)
            u.reg_write(UC_ARM_REG_R1,1)
            u.reg_write(UC_ARM_REG_R2,0)
            u.reg_write(UC_ARM_REG_S1,bits(85))
            u.reg_write(UC_ARM_REG_S2,bits(36))
            self.call_worker(u,label)
            self.assertEqual(calls,expected)

    def prepare_pages(self,u,base):
        raw='「First line\n　Second line\n　Third line\n　Last line」'.encode()
        self.assertLess(len(raw),104)
        u.mem_write(base,raw+b'\0'*(121-len(raw)))
        u.reg_write(UC_ARM_REG_R0,base)
        self.call_worker(u,'split_buffer')
        page=u.mem_read(base+104,1)[0]
        self.assertGreater(page,0)
        self.assertEqual(u.mem_read(base+page-1,1),b'\0')
        self.assertEqual(u.mem_read(base+105,1),b'\0')
        u.mem_write(0x8125d0cc,struct.pack('<I',base))
        return page

    def test_both_native_quote_buffers_get_two_complete_pages(self):
        for base in (0x8125cdf4,0x8125cdf4+121):
            for delta in (1,2):
                u=self.machine();page=self.prepare_pages(u,base)
                for ticks in range(delta,241,delta):
                    u.reg_write(UC_ARM_REG_R3,delta)
                    self.call_worker(u,'page_tick')
                    self.assertEqual(u.reg_read(UC_ARM_REG_R0),1)
                    pointer=struct.unpack('<I',u.mem_read(0x8125d0cc,4))[0]
                    self.assertEqual(pointer,base+(page if ticks>=120 else 0))
                self.assertEqual(u.mem_read(base+105,1),bytes([240]))
                u.reg_write(UC_ARM_REG_R3,delta)
                self.call_worker(u,'page_tick')
                self.assertEqual(u.reg_read(UC_ARM_REG_R0),0)

    def test_short_quotes_and_unrelated_pointers_do_not_hold_battle(self):
        u=self.machine();base=0x8125cdf4
        u.mem_write(base,b'One line\nTwo lines\0')
        u.reg_write(UC_ARM_REG_R0,base);self.call_worker(u,'split_buffer')
        self.assertEqual(u.mem_read(base+104,2),b'\0\0')
        u.mem_write(0x8125d0cc,struct.pack('<I',base))
        u.reg_write(UC_ARM_REG_R3,1);self.call_worker(u,'page_tick')
        self.assertEqual(u.reg_read(UC_ARM_REG_R0),0)
        self.prepare_pages(u,base)
        u.mem_write(0x8125d0cc,struct.pack('<I',0x81250000))
        u.reg_write(UC_ARM_REG_R3,1);self.call_worker(u,'page_tick')
        self.assertEqual(u.reg_read(UC_ARM_REG_R0),0)

    def test_dialogue_rows_are_copied_once_and_stop_at_the_next_row(self):
        examples = [
            ("I'll let you shoot me now. What's", "　wrong? Are you afraid?"),
            ("Damn! As if Boss Borot would be", "　beaten so easily!"),
            ("A pretty girl's invitation, tempting,", "　but no!"),
            ("First page", "Second row", "Next page", "Final row"),
            ("Only one line",),
        ]
        for lines in examples:
            u = self.machine()
            source = 0x70002000
            u.mem_write(source, ("\n".join(lines) + "\0").encode("utf-8"))
            u.reg_write(UC_ARM_REG_R4, source)
            u.emu_start(self.labels['split_quote_rows'] | 1, 0x81017464, count=2000)
            self.assertEqual(u.reg_read(UC_ARM_REG_PC), 0x81017464)
            for index, (staging, display) in enumerate(((0x811f6a40, 0x811f6978), (0x811f6b40, 0x811f69d8))):
                expected = (lines[index] if index < len(lines) else "").encode("utf-8")
                u.mem_write(display, b'x' * 96)
                u.reg_write(UC_ARM_REG_R0, staging)
                u.reg_write(UC_ARM_REG_R1, display)
                u.reg_write(UC_ARM_REG_R2, 96)
                self.call_worker(u, 'copy_quote_row')
                actual = bytes(u.mem_read(display, 96)).split(b'\0', 1)[0]
                self.assertEqual(actual, expected)
                self.assertEqual(bytes(u.mem_read(staging, 96)).rstrip(b'\0'), expected)

    def test_native_update_hook_uses_delta_and_returns_running(self):
        u=self.machine();base=0x8125cdf4;self.prepare_pages(u,base)
        for elapsed in range(1,241):
            u.reg_write(UC_ARM_REG_SP,0x70010000)
            u.reg_write(UC_ARM_REG_LR,1) # native update's delta register
            u.reg_write(UC_ARM_REG_R4,0x87654321)
            u.emu_start(self.labels['page_update']|1,0x81079d0e,count=1000)
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x81079d0e)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),0)
            self.assertEqual(u.reg_read(UC_ARM_REG_R4),0x87654321)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x70010000)
            self.assertEqual(u.mem_read(base+105,1),bytes([elapsed]))
        u.emu_start(self.labels['page_update']|1,0x810779ca,count=1000)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x810779ca)
        self.assertEqual(u.reg_read(UC_ARM_REG_R0),0xd18c)

    def test_render_hook_keeps_second_page_after_native_pointer_reset(self):
        u=self.machine();base=0x8125cdf4;page=self.prepare_pages(u,base)
        u.mem_write(base+105,bytes([180]))
        u.reg_write(UC_ARM_REG_SP,0x70010000)
        u.emu_start(self.labels['page_render']|1,0x81077102,count=1000)
        self.assertEqual(struct.unpack('<I',u.mem_read(0x8125d0cc,4))[0],base+page)

    def test_faction_labels_have_real_gap_in_both_selection_states(self):
        positions={}
        for label in ('faction_ally_big','faction_enemy_small','faction_ally_small','faction_enemy_big'):
            u=self.machine();u.reg_write(UC_ARM_REG_SP,0x70010000)
            end=next(pc+4 for pc,name in HOOKS.items() if name==label)
            u.emu_start(self.labels[label]|1,end,count=20)
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),end)
            positions[label]=floating(u.reg_read(UC_ARM_REG_S0))
        def width(text,size):return sum(int(self.metrics[c]['advance']*size+self.metrics[c]['adjust_px']) for c in text)
        for ally,enemy,a_size,e_size in [('faction_ally_big','faction_enemy_small',38,30),
                                        ('faction_ally_small','faction_enemy_big',30,38)]:
            right=positions[ally]+width('Allies /',a_size)/2
            left=positions[enemy]-width('Enemies',e_size)/2
            self.assertEqual(left-right,10)


if __name__=='__main__':unittest.main()
