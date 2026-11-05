#!/usr/bin/env python3
"""Check that a built ELF really contains the translations.

  python tools/verify_build.py [built.elf]

`srwtext.py extract` only reports strings with Japanese in them, so it cannot
see translated rows -- it would happily report "not found" for every line we
wrote.  This checks the bytes directly instead:

  * in-place rows: the bytes at the original offset must decode to the English
  * relocated rows: every 32-bit reference must point at a copy of the English
  * every reference must still resolve (no dangling pointer), and the ELF load
    segment must cover the whole file
"""
import csv
import json
import os
import struct
import sys
from srwtext import load_segments, trusted_refs
from project_paths import ORIGINAL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, "work", "text", "text_banks.json")
CSV = os.path.join(ROOT, "work", "text", "translation.csv")
OUT = os.path.join(ROOT, "build", "EBOOT.BIN")
VADDR_DELTA = 0x10000


def read_cstr(d, off):
    end = d.find(b"\x00", off)
    return d[off:end if end >= 0 else len(d)]


def main(argv):
    path = argv[1] if len(argv) > 1 else OUT
    d = open(path, "rb").read()
    loads = load_segments(d)

    def mapped_offset(va):
        for _, _, off, addr, _, filesz, _ in loads:
            if addr <= va < addr + filesz:
                return off + va - addr
        return None

    # Overflow must not occupy any original BSS or overlap another load.
    source = (ORIGINAL / "USRDIR/EBOOT.elf").read_bytes()
    original_loads = load_segments(source)
    layout_bad = 0
    for _, _, off, va, _, filesz, _ in loads:
        if off + filesz > len(d):
            print("!! load extends beyond file")
            layout_bad += 1
        for _, _, _, oldva, _, oldfilesz, oldmemsz in original_loads:
            if filesz and oldmemsz > oldfilesz and va < oldva + oldmemsz and va + filesz > oldva + oldfilesz:
                print("!! file-backed text/data overlaps original BSS")
                layout_bad += 1
    ents = {e["id"]: e for e in json.load(open(TEXT, encoding="utf-8"))}

    rows = []
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["english"].strip():
                rows.append(r)

    inplace = moved = bad = 0
    for r in rows:
        e = ents[int(r["id"])]
        want = r["english"]
        try:
            raw = want.encode(e["enc"]) + b"\x00"
        except UnicodeEncodeError:
            bad += 1
            print("!! %s: unencodable in %s: %r" % (r["offset"], e["enc"], want))
            continue
        body = raw[:-1]
        in_place = read_cstr(d, e["off"]) == body
        refs = trusted_refs(e)
        ok = in_place or bool(refs)
        # Check pointers even for in-place strings: another row's false
        # file-offset reference used to silently redirect these to wrong text.
        for ref in refs:
            v = struct.unpack_from(">I", d, ref["pos"])[0]
            tgt = mapped_offset(v)
            if tgt is None or read_cstr(d, tgt) != body:
                ok = False
                break
        if ok:
            if in_place:
                inplace += 1
            else:
                moved += 1
        else:
            bad += 1
            print("!! %s (%s): expected %r, found %r"
                  % (r["offset"], r["id"], want, read_cstr(d, e["off"])[:60]))

    # Resolve trusted virtual addresses through PT_LOAD, including the new
    # overflow segment, whose address no longer equals file offset + 0x10000.
    dangling = 0
    ambiguous = 0
    for e in ents.values():
        for ref in trusted_refs(e):
            v = struct.unpack_from(">I", d, ref["pos"])[0]
            hits = [mapped_offset(v)] if mapped_offset(v) is not None else []
            if not hits:
                dangling += 1
                print("!! dangling ref: id %s pos %#x value %#x (off %#x)"
                      % (e["id"], ref["pos"], v, e["off"]))
            elif len(hits) == 2:
                ambiguous += 1

    print("verified %d translated rows: %d in place, %d relocated, %d bad; "
          "%d dangling refs, %d ambiguous refs; file %d bytes"
          % (len(rows), inplace, moved, bad, dangling, ambiguous, len(d)))
    return 1 if (bad or dangling or layout_bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
