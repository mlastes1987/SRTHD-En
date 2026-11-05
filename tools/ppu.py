#!/usr/bin/env python3
"""Read the PPU (PowerPC) code in the decrypted ELF.

The PS3 code section has no symbols, so this walks it with capstone and finds
the places that touch a chosen address range -- which is how you get from "this
table holds the text" to "this function lays the text out".

Needs `pip install capstone`.  The clang toolchain on this machine has no
PowerPC target, so llvm-objdump only names the file format and refuses to
disassemble it; capstone is what actually reads the code.

  python tools/ppu.py refs 0x47be00 0x47f000      # code that touches a range
  python tools/ppu.py dis 0x123456 --len 0x200    # disassemble around an address
  python tools/ppu.py find --imm 0x200 --imm 0x10 # instructions with constants
  python tools/ppu.py window --around 0x123456    # the function holding it

Addresses are ELF virtual addresses (what a disassembler prints), the same
numbers the strings and descriptor tables in the docs use.
"""
import os
import struct
import sys

import capstone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from project_paths import ORIGINAL
ELF = str(ORIGINAL / "USRDIR/EBOOT.elf")


def load(path=ELF):
    """Return (image, base, segments) for the ELF, with vaddr -> file offset."""
    d = open(path, "rb").read()
    if d[:4] != b"\x7fELF" or d[4] != 2:
        raise SystemExit("not a 64-bit ELF: %s" % path)
    e_phoff, = struct.unpack_from(">Q", d, 0x20)
    e_phentsize, e_phnum = struct.unpack_from(">HH", d, 0x36)
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, = struct.unpack_from(">I", d, off)
        if p_type != 1:                       # PT_LOAD only
            continue
        p_offset, p_vaddr, _p_paddr, p_filesz = struct.unpack_from(">QQQQ", d, off + 8)
        segs.append((p_vaddr, p_offset, p_filesz))
    segs.sort()
    return d, segs


def to_off(segs, addr):
    for vaddr, off, size in segs:
        if vaddr <= addr < vaddr + size:
            return off + (addr - vaddr)
    return None


def code_range(segs):
    """The executable segment(s) as (start, end) virtual addresses."""
    return [(v, v + s) for v, _o, s in segs]


def md():
    m = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_64 |
                    capstone.CS_MODE_BIG_ENDIAN)
    m.detail = True
    return m


def insns(segs, start=None, end=None):
    """Yield instructions over the code, resyncing past words that do not decode.

    capstone stops the whole run at the first undecodable word, and the first
    segment begins with the ELF header, so a plain `disasm` on a segment yields
    nothing at all.  Step the scan forward instead: decode as far as it goes,
    then skip one word and carry on.
    """
    m = md()
    d = open(ELF, "rb").read()
    for vaddr, off, size in segs:
        if not size:
            continue
        lo = vaddr if start is None else max(vaddr, start)
        hi = vaddr + size if end is None else min(vaddr + size, end)
        lo += (4 - (lo % 4)) % 4
        if lo >= hi:
            continue
        chunk = d[off + (lo - vaddr):off + (hi - vaddr)]
        pos = 0
        while pos + 4 <= len(chunk):
            advanced = False
            for ins in m.disasm(chunk[pos:], lo + pos):
                yield ins
                pos = ins.address - lo + ins.size
                advanced = True
            if not advanced:
                pos += 4


# --- the little constant tracker that makes `refs` work ---------------------
# PPC forms an address as `lis rD, hi` then `addi rD, rD, lo`, so a bare
# immediate never shows the address.  Track the values that are provably
# constant and resolve the ones used as a base address.

def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def scan(segs, start=None, end=None, want=None, imms=None):
    """Walk the code, tracking constant registers; report useful hits.

    Returns a list of dicts: kind ('ref' or 'imm'), addr, target, text, regs.
    """
    regs = {}
    hits = []
    stats = {"insn": 0, "resolved": 0}
    for ins in insns(segs, start, end):
        text = "%s %s" % (ins.mnemonic, ins.op_str)
        ops = ins.operands
        stats["insn"] += 1

        # 1) immediates first: every branch below returns early, and hunting a
        #    constant is the common case, so it must not sit behind a continue
        if imms:
            for op in ops:
                if op.type == capstone.ppc.PPC_OP_IMM and \
                        (op.imm & 0xFFFFFFFF) in imms:
                    hits.append(dict(kind="imm", addr=ins.address,
                                     target=op.imm & 0xFFFFFFFF, text=text))

        # 2) keep the constant registers straight, and check them
        mn = ins.mnemonic
        if mn in ("li", "lis", "la") and len(ops) >= 2 \
                and ops[0].type == capstone.ppc.PPC_OP_REG:
            r = ins.reg_name(ops[0].reg)
            if ops[1].type == capstone.ppc.PPC_OP_IMM:
                imm = ops[1].imm & 0xFFFFFFFF
                if mn == "lis":
                    regs[r] = (imm << 16) & 0xFFFFFFFF
                else:
                    regs[r] = imm & 0xFFFF
                    if regs[r] & 0x8000:
                        regs[r] |= 0xFFFF0000
                if want and want[0] <= regs[r] <= want[1]:
                    hits.append(dict(kind="ref", addr=ins.address,
                                     target=regs[r], text=text))
            else:
                mem = ops[1].mem
                b = ins.reg_name(mem.base) if mem.base else "0"
                if b == "0":
                    regs[r] = 0xFFFF & _s16(mem.disp)
                elif b in regs:
                    regs[r] = (regs[b] + _s16(mem.disp)) & 0xFFFFFFFF
                else:
                    regs.pop(r, None)
                if want and r in regs and want[0] <= regs[r] <= want[1]:
                    hits.append(dict(kind="ref", addr=ins.address,
                                     target=regs[r], text=text))
            continue
        if mn in ("addi", "addic", "addic.", "addis") and len(ops) >= 3 \
                and ops[0].type == capstone.ppc.PPC_OP_REG:
            d = ins.reg_name(ops[0].reg)
            a = ins.reg_name(ops[1].reg) if ops[1].type == capstone.ppc.PPC_OP_REG else "0"
            v = ops[2].imm & 0xFFFF
            base = 0 if a == "0" else regs.get(a)
            if base is not None:
                regs[d] = (base + (_s16(v) if mn != "addis" else (v << 16))) & 0xFFFFFFFF
                if want and want[0] <= regs[d] <= want[1]:
                    hits.append(dict(kind="ref", addr=ins.address,
                                     target=regs[d], text=text))
            else:
                regs.pop(d, None)
            continue
        if mn in ("ori", "oris") and len(ops) >= 3 \
                and ops[0].type == capstone.ppc.PPC_OP_REG:
            d = ins.reg_name(ops[0].reg)
            a = ins.reg_name(ops[1].reg) if ops[1].type == capstone.ppc.PPC_OP_REG else "0"
            v = ops[2].imm & 0xFFFF
            base = 0 if a == "0" else regs.get(a)
            if base is not None:
                regs[d] = (base | (v if mn == "ori" else (v << 16))) & 0xFFFFFFFF
            else:
                regs.pop(d, None)
            continue
        if mn.startswith("b"):
            if mn in ("blr", "bctr", "bctrl", "b", "bl"):
                regs = {}                   # control flow: values are gone
            continue

        # 3) a load or store: resolve the effective address
        mem = None
        for op in ops:
            if op.type == capstone.ppc.PPC_OP_MEM:
                mem = op.mem
                break
        if mem is not None:
            b = ins.reg_name(mem.base) if mem.base else None
            if b in regs:
                addr = (regs[b] + _s16(mem.disp)) & 0xFFFFFFFF
                stats["resolved"] += 1
                if want and want[0] <= addr <= want[1]:
                    hits.append(dict(kind="ref", addr=ins.address,
                                     target=addr, text=text))
            if b and b.startswith("r"):
                regs.pop(ins.reg_name(ops[0].reg), None) if ops[0].type == capstone.ppc.PPC_OP_REG else None
    hits.append(dict(kind="stats", addr=0, target=0,
                     text="%d instructions, %d loads/stores resolved"
                          % (stats["insn"], stats["resolved"])))
    return hits


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    d, segs = load()
    cmd = argv[0]
    if cmd == "refs":
        lo, hi = int(argv[1], 0), int(argv[2], 0)
        hits = scan(segs, want=(lo, hi))
        print("%d references to 0x%x-0x%x" % (len(hits) - 1, lo, hi))
        seen = set()
        for h in hits:
            if h["kind"] == "stats":
                print("  (%s)" % h["text"])
                continue
            if h["addr"] in seen:
                continue
            seen.add(h["addr"])
            print("  0x%08x -> 0x%08x   %s" % (h["addr"], h["target"], h["text"]))
        return 0
    if cmd == "dis":
        start = int(argv[1], 0)
        n = 0x100
        if "--len" in argv:
            n = int(argv[argv.index("--len") + 1], 0)
        for ins in insns(segs, start, start + n):
            print("0x%08x  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
        return 0
    if cmd == "find":
        imms = {int(argv[i + 1], 0) for i, a in enumerate(argv) if a == "--imm"}
        hits = scan(segs, imms=imms)
        stats = [h for h in hits if h["kind"] == "stats"]
        hits = [h for h in hits if h["kind"] != "stats"]
        print("%d instructions with those immediates" % len(hits))
        for h in hits[:40]:
            print("  0x%08x  imm 0x%-6x %s" % (h["addr"], h["target"], h["text"]))
        for s in stats:
            print("  (%s)" % s["text"])
        return 0
    if cmd == "window":
        # crude function window: back to the previous bctr/blr + alignment
        around = int(argv[argv.index("--around") + 1], 0)
        back = 0x1000
        addrs = [(i.address, "%s %s" % (i.mnemonic, i.op_str))
                 for i in insns(segs, around - back, around + back)]
        for a, t in addrs:
            mark = ">>" if abs(a - around) < 8 else "  "
            print("%s 0x%08x  %s" % (mark, a, t))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
