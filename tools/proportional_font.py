"""Experimental proportional advances using this game's actual bitmap glyphs.

python tools/proportional_font.py [--image build/EBOOT.BIN]
Use build.py --proportional to apply after rebuilding the translation.
"""
import argparse
import json
from pathlib import Path
import struct

from PIL import Image, ImageChops, ImageDraw
from srwtext import load_segments

ROOT = Path(__file__).resolve().parents[1]
from project_paths import ORIGINAL
BASE = ORIGINAL / "USRDIR/EBOOT.elf"
CAVE = 0x4BDA00
TABLE = 0x4BE000
DELTA = 0x10000
ADVANCE_ADJUST_PX = {"k": -1.0, "s": -1.0}


def word(op, rt, ra, imm):
    return (op << 26) | (rt << 21) | (ra << 16) | (imm & 65535)


class Code:
    def __init__(self, va):
        self.start = va
        self.words = []
        self.labels = {}
        self.fixups = []

    @property
    def pc(self):
        return self.start + 4 * len(self.words)

    def emit(self, w):
        self.words.append(w)

    def d(self, op, rt, ra, imm):
        self.emit(word(op, rt, ra, imm))

    def label(self, name):
        self.labels[name] = self.pc

    def branch(self, target, condition=None, link=False):
        self.fixups.append((len(self.words), target, condition, link))
        self.emit(0)

    def finish(self):
        for index, target, cond, link in self.fixups:
            target = self.labels[target] if isinstance(target, str) else target
            distance = target - (self.start + index * 4)
            if cond is None:
                assert -(1 << 25) <= distance < (1 << 25) and distance % 4 == 0
                self.words[index] = 0x48000000 | (distance & 0x3FFFFFC) | int(link)
            else:
                assert -32768 <= distance < 32768 and distance % 4 == 0
                # beq cr7 / bgt cr7
                self.words[index] = (0x419E0000 if cond == "eq" else 0x419D0000) | (distance & 0xFFFC)
        return b"".join(struct.pack(">I", w) for w in self.words)

    def slwi(self, dst, src, shift):
        self.emit((21 << 26) | (src << 21) | (dst << 16) | (shift << 11) | ((31-shift) << 1))

    def or_(self, dst, a, b):
        self.emit((31 << 26) | (a << 21) | (dst << 16) | (b << 11) | (444 << 1))

    def add(self, dst, a, b):
        self.emit((31 << 26) | (dst << 21) | (a << 16) | (b << 11) | (266 << 1))

    def fp(self, kind, dst, a, b):
        # Single-precision arithmetic. Multiply uses FRC rather than FRB.
        if kind == "mul":
            self.emit((59 << 26) | (dst << 21) | (a << 16) | (b << 6) | (25 << 1))
        else:
            self.emit((59 << 26) | (dst << 21) | (a << 16) | (b << 11) | ((21 if kind == "add" else 20) << 1))


def atlas_and_metrics():
    data = (ROOT / "work/tabata/00000.bin").read_bytes()
    # GCM linear G8B8 (0xAB), width=4096, height=1120. The two channels
    # contain the glyph and its effect coverage; include both to avoid collisions.
    width, height = struct.unpack_from(">HH", data, 0x20)
    assert (width, height) == (4096, 1120) and data[0x18] == 0xAB
    raw = data[0x80:]
    assert len(raw) == width * height * 2
    im = ImageChops.lighter(Image.frombytes("L", (width, height), raw[::2]),
                            Image.frombytes("L", (width, height), raw[1::2]))
    source = BASE.read_bytes()
    metrics = {}
    for ch in "".join(chr(c) for c in range(32, 127)):
        # sjishan2zen uses the standard full-width ASCII equivalents. Quotes
        # use Japanese curly quote cells, since FF02/FF07 aren't in this font.
        special = {" ": 0x8140, '"': 0x8168, "'": 0x8166,
                   "\\": 0x815F, "~": 0x8160, "-": 0x817C}
        sjis = special.get(ch)
        if sjis is None:
            sjis = struct.unpack_from(">H", source, 0x4E4498 + 0x40 + 2 * (ord(ch)+0xFEE0))[0]
        assert 0x8100 <= sjis < 0x8300, (ch, hex(sjis))
        glyph = (sjis + (0x7EC0 if sjis >> 8 == 0x81 else 0x7E80)) & 65535
        x, y = glyph % 128 * 32, glyph // 128 * 32
        cell = im.crop((x, y, x+32, y+32))
        box = cell.point(lambda v: 255 if v >= 40 else 0).getbbox()
        if ch == " ":
            advance, left = 0.40, 0.0
        else:
            if box is None:
                raise ValueError("empty glyph for " + repr(ch))
            advance = (box[2] - box[0] + 2) / 32
            left = box[0] / 32
        metrics[ch] = dict(sjis=sjis, glyph=glyph, box=box,
                           advance=advance, left=left,
                           adjust_px=ADVANCE_ADJUST_PX.get(ch, 0.0))
    return im, metrics


def emit_lookup(c, fallback, encoded=False):
    # r10 = code; leave r8/r11 intact for the original measuring loop.
    if encoded:
        c.d(40, 10, 1, 0xC0)  # lhz original glyph code
    else:
        c.slwi(10, 8, 8)
        c.or_(10, 10, 11)
    c.d(14, 10, 10, -32768)
    c.d(14, 10, 10, -256)
    c.emit((10 << 26) | (7 << 23) | (10 << 16) | 511)  # cmplwi cr7
    c.branch(fallback, "gt")
    c.slwi(10, 10, 4)
    c.d(15, 0, 0, (TABLE+DELTA) >> 16)
    c.d(24, 0, 0, (TABLE+DELTA) & 65535)
    c.add(10, 10, 0)
    c.d(32, 0, 10, 0)
    c.emit((11 << 26) | (7 << 23))  # cmpwi cr7,r0,0
    c.branch(fallback, "eq")


def patch(image):
    d = bytearray(image.read_bytes())
    source = BASE.read_bytes()
    im, metrics = atlas_and_metrics()
    code = Code(CAVE + DELTA)
    patches = {}
    # Both character classes and the non-classified path in the width routine.
    for site, default in [(0x13CB4, 11), (0x13CE0, 12), (0x13D6C, 13)]:
        patches[site] = code.pc
        tag = "measure_%x" % site
        emit_lookup(code, tag)
        code.d(48, 9, 10, 0)
        code.d(48, 10, 7, 0x38 if default != 13 else 0x14)
        code.fp("mul", 10, 10, 9)
        code.d(48, 9, 10, 8)
        code.fp("add", 10, 10, 9)
        code.fp("add", 0, 0, 10)
        code.branch(site+4)
        code.label(tag)
        code.fp("add", 0, 0, default)
        code.branch(site+4)

    # Remove the left bearing from the quad's X position, without changing UVs.
    patches[0x14D70] = code.pc
    code.d(62, 10, 1, 0xD8)
    code.emit(0x7C000026)  # mfcr r0
    code.d(36, 0, 1, 0xCC)
    code.d(48, 12, 1, 0x84)
    emit_lookup(code, "bearing_end", encoded=True)
    code.d(48, 9, 10, 4)
    code.d(48, 10, 1, 0x9C)
    code.fp("mul", 10, 10, 9)
    code.fp("sub", 12, 12, 10)
    code.label("bearing_end")
    code.d(32, 0, 1, 0xCC)
    code.emit(0x7C001120)  # mtcrf 1,r0 (CR7)
    code.d(58, 10, 1, 0xD8)
    code.branch(0x14D74)

    patches[0x14DF8] = code.pc
    emit_lookup(code, "advance_default", encoded=True)
    code.d(48, 9, 10, 0)
    code.d(48, 10, 1, 0x9C)
    code.fp("mul", 13, 10, 9)
    code.d(48, 9, 10, 8)
    code.fp("add", 13, 13, 9)
    # The original measuring loop accumulates integer pixels. Match its
    # truncation in drawing so centered/right-aligned labels agree exactly.
    code.emit((63 << 26) | (13 << 21) | (13 << 11) | (15 << 1))
    code.d(54, 13, 1, 0xD0)
    code.d(32, 0, 1, 0xD4)
    code.d(62, 0, 1, 0xD0)
    code.d(50, 13, 1, 0xD0)
    code.emit((63 << 26) | (13 << 21) | (13 << 11) | (846 << 1))
    code.emit((63 << 26) | (13 << 21) | (13 << 11) | (12 << 1))
    code.branch(0x14DFC)
    code.label("advance_default")
    code.d(48, 13, 1, 0x94)
    code.branch(0x14DFC)

    # Replace the centered draw wrapper's character-count shortcut with the
    # same width routine used by right alignment. Preserve all draw arguments.
    patches[0x14FD4] = code.pc
    code.d(62, 1, 1, -0xB0 | 1)  # stdu r1,-0xb0(r1)
    code.emit(0x7C0802A6)  # mflr r0
    code.d(62, 0, 1, 0xC0)
    for reg, off in [(3, 0x70), (7, 0x78), (8, 0x80)]:
        code.d(62, reg, 1, off)
    for reg, off in [(1, 0x88), (2, 0x90), (3, 0x98)]:
        code.d(54, reg, 1, off)
    code.or_(5, 7, 7)
    code.d(14, 4, 0, 0)
    code.branch(0x13BBC, link=True)
    code.emit((31 << 26) | (3 << 21) | (0 << 16) | (986 << 1))  # extsw r0,r3
    code.d(62, 0, 1, 0xA0)
    code.d(50, 0, 1, 0xA0)
    code.emit((63 << 26) | (0 << 21) | (0 << 11) | (846 << 1))  # fcfid f0,f0
    code.emit((63 << 26) | (0 << 21) | (0 << 11) | (12 << 1))  # frsp f0,f0
    for reg, off in [(1, 0x88), (2, 0x90), (3, 0x98)]:
        code.d(50, reg, 1, off)
    code.fp("add", 1, 1, 0)
    for reg, off in [(3, 0x70), (7, 0x78), (8, 0x80)]:
        code.d(58, reg, 1, off)
    code.d(58, 0, 1, 0xC0)
    code.emit(0x7C0803A6)  # mtlr r0
    code.d(14, 1, 1, 0xB0)
    code.branch(0x145A4)

    # Pause-menu faction selector: the original layers aligned through spaces.
    # Proportional spaces cannot serve as layout columns, especially as the
    # selected label is 38 px and the inactive label is 30 px. Center the two
    # labels as a group, with a real 10 px gap, for both selection states.
    def text_width(text, size):
        return sum(int(metrics[ch]["advance"] * size + metrics[ch]["adjust_px"])
                   for ch in text)

    ally_big, ally_small = (text_width("Allies /", s) for s in (38, 30))
    enemy_big, enemy_small = (text_width("Enemies", s) for s in (38, 30))
    origins = {
        0x10F29C: 1072 - (enemy_small + 10) / 2,  # Allies selected (38)
        0x10F2F8: 1072 + (ally_big + 10) / 2,    # Enemies inactive (30)
        0x10F24C: 1072 - (enemy_big + 10) / 2,   # Allies inactive (30)
        0x10F1F0: 1072 + (ally_small + 10) / 2,  # Enemies selected (38)
    }
    # r10 is dead at these call-argument setup sites; preserve the live color
    # registers r0/r9 and do not change CR flags.
    constants = []
    for site, x in origins.items():
        patches[site] = code.pc
        constants.append((len(code.words), x))
        code.emit(0)  # lis r10,constant@ha, resolved below
        code.emit(0)  # lfs f1,constant@l(r10)
        code.branch(site+4)
    constants_va = code.pc
    for index, (insn_index, x) in enumerate(constants):
        address = constants_va + index*4
        code.words[insn_index] = word(15, 10, 0, (address+0x8000) >> 16)
        code.words[insn_index+1] = word(48, 1, 10, address & 65535)

    blob = code.finish() + b"".join(struct.pack(">f", x) for _, x in constants)
    assert CAVE + len(blob) <= TABLE
    end = TABLE + 512 * 16
    assert not any(source[CAVE:end]), "code cave is not empty"
    if any(d[CAVE:end]):
        raise ValueError("font patch already applied or cave occupied; rebuild first")
    for va, target in patches.items():
        off = va - DELTA
        if d[off:off+4] != source[off:off+4]:
            raise ValueError("unexpected original instruction at %#x" % va)
        branch = Code(va)
        branch.branch(target)
        d[off:off+4] = branch.finish()
    d[CAVE:CAVE+len(blob)] = blob
    for metric in metrics.values():
        pos = TABLE + (metric["sjis"] - 0x8100) * 16
        struct.pack_into(">fff", d, pos, metric["advance"], metric["left"], metric["adjust_px"])
    first = load_segments(d)[0]
    assert end + DELTA <= load_segments(d)[1][3]
    struct.pack_into(">QQ", d, first[0]+32, end, end)
    image.write_bytes(d)
    report = dict(image=str(image), cave=hex(CAVE+DELTA), code_bytes=len(blob),
                  table=hex(TABLE+DELTA), patches={hex(k):hex(v) for k,v in patches.items()},
                  metrics=metrics, pause_faction_origins={hex(k):v for k,v in origins.items()})
    (ROOT / "work/text/proportional_metrics.json").write_text(json.dumps(report, indent=2))
    specimen(im, metrics)
    print("Proportional font: %d hooks, %d bytes code, measured %d ASCII glyphs" %
          (len(patches), len(blob), len(metrics)))


def specimen(atlas, metrics):
    out = Image.new("RGB", (1100, 370), (22, 26, 34))
    draw = ImageDraw.Draw(out)
    draw.text((20, 12), "ACTUAL GAME GLYPHS / fixed advance (35 px)", fill="white")
    draw.text((20, 190), "EXPERIMENT / measured glyph advance + 2 atlas-pixel gap", fill="white")
    for text, y in [("Hit Rate  |  William  |  iii WWW", 45),
                    ("Battle at the Lake", 100)]:
        for prop in [False, True]:
            x = 20.0
            for ch in text:
                m = metrics[ch]
                g = m["glyph"]
                tile = atlas.crop((g%128*32, g//128*32, g%128*32+32, g//128*32+32)).resize((38, 38))
                shift = m["left"] * 38 if prop else 0
                out.paste((240, 240, 245), (round(x-shift), y+(180 if prop else 0)), tile)
                x += int(m["advance"] * 38 + m["adjust_px"]) if prop else 35
    out.save(ROOT / "shots/proportional_font_specimen.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=ROOT / "build/EBOOT.BIN")
    patch(parser.parse_args().image)
