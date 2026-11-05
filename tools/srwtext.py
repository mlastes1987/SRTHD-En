#!/usr/bin/env python3
"""Extract / reimport the text of Super Robot Wars HD (NPJB00514).

The text lives in the decrypted EBOOT.ELF as NUL-terminated, 8-byte-aligned
strings (mostly UTF-8, some Shift-JIS).  Every string is referenced from
tables of aligned 32-bit big-endian virtual addresses. File-offset matches
from the original extractor alias unrelated strings and must not be patched.

Commands:
  extract <EBOOT.elf> <text.json>
  import  <EBOOT.elf> <text.json> <new.elf>
"""
import json
import struct
import sys

TEXT_LO = 0x400000          # scan window for strings
TEXT_HI = 0x500000
DATA_LO = 0x3f7b04          # first data section: pointer tables live above this
VADDR_DELTA = 0x10000       # vaddr = file offset + this, for both load segments
ALIGN = 8


def jp_score(s):
    n = 0
    for ch in s:
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFF60:
            n += 1
    return n


def bad_chars(s):
    """Half-width katakana and private-use code points flag binary junk."""
    return any(0xFF61 <= ord(ch) <= 0xFF9F or 0xE000 <= ord(ch) <= 0xF8FF for ch in s)


def decode(blob):
    end = blob.find(b"\x00")
    raw = blob if end < 0 else blob[:end]
    for enc in ("utf-8", "cp932"):
        try:
            s = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if (jp_score(s) >= 1 and not bad_chars(s)
                and all(ch == "\n" or ch == "\t" or ch >= " " for ch in s)):
            return enc, s
    return None


def find_strings(d):
    """8-aligned, NUL-terminated Japanese strings, in file order."""
    out = []
    for off in range(TEXT_LO, min(TEXT_HI, len(d)), ALIGN):
        if off and d[off - 1] != 0:
            continue
        r = decode(d[off:off + 4000])
        if not r:
            continue
        enc, s = r
        out.append({"off": off, "enc": enc, "text": s})
    return out


def find_refs(d, offsets):
    """Locate aligned virtual-address pointers; returns dict off -> refs."""
    lut = {}
    for o in offsets:
        lut.setdefault(o + VADDR_DELTA, []).append(o)  # vaddr form
    refs = {o: [] for o in offsets}
    n = len(d)
    for pos in range(align_up(DATA_LO, 4), n - 3, 4):
        v = struct.unpack_from(">I", d, pos)[0]
        if v in lut:
            for o in lut[v]:
                refs[o].append({"pos": pos, "vaddr": v == o + VADDR_DELTA})
    return refs


def cmd_extract(src, out):
    d = open(src, "rb").read()
    strings = find_strings(d)
    refs = find_refs(d, [s["off"] for s in strings])
    for i, s in enumerate(strings):
        s["id"] = i
        s["end"] = s["off"] + len(s["text"].encode(s["enc"])) + 1
        s["refs"] = refs[s["off"]]
    for i, s in enumerate(strings):
        nxt = strings[i + 1]["off"] if i + 1 < len(strings) else s["end"]
        s["slot"] = max(0, nxt - s["off"])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(strings, f, ensure_ascii=False, indent=1)
    unref = sum(1 for s in strings if not s["refs"])
    print("strings: %d  (unreferenced: %d)  -> %s" % (len(strings), unref, out))


def load_segments(d):
    """PT_LOAD tuples: header offset, flags, file offset, VA, PA, filesz, memsz."""
    phoff = struct.unpack_from(">Q", d, 0x20)[0]
    size, count = struct.unpack_from(">HH", d, 0x36)
    out = []
    for i in range(count):
        pos = phoff + i * size
        typ, flags, off, va, pa, filesz, memsz, _ = struct.unpack_from(">IIQQQQQQ", d, pos)
        if typ == 1:
            out.append((pos, flags, off, va, pa, filesz, memsz))
    return out


def trusted_refs(e):
    # The old scan matched both off and off+0x10000 at every byte. The former
    # aliases a different virtual address; unaligned hits are binary accidents.
    return [r for r in e["refs"] if r["vaddr"] and r["pos"] % 4 == 0]


def safe_slot(source, e):
    """Only use NUL padding, never a neighbouring unextracted string/data."""
    end = e["end"]
    limit = min(len(source), e["off"] + (e["slot"] or ALIGN))
    while end < limit and source[end] == 0:
        end += 1
    return end - e["off"]


def cmd_import(src, json_path, dst):
    with open(src, "rb") as f:
        source = f.read()
    d = bytearray(source)
    with open(json_path, encoding="utf-8") as f:
        entries = json.load(f)
    by_off = {e["off"]: e for e in entries}
    order = sorted(by_off)
    # Appending to the writable segment puts text inside its existing BSS.
    # Runtime globals then overwrite it. Use an empty PT_LOAD after all memory.
    loads = load_segments(d)
    empty = next((p for p in loads if not p[5] and not p[6]), None)
    overflow_start = align_up(len(d), 0x10000)
    overflow_addr = align_up(max(p[3] + p[6] for p in loads), 0x10000)
    overflow_at = overflow_start
    overflow_used = False
    moved = 0
    changed = 0

    for i, off in enumerate(order):
        e = by_off[off]
        enc = e["enc"]
        text = e.get("translation", e["text"])
        try:
            raw = text.encode(enc) + b"\x00"
        except UnicodeEncodeError:
            raw = text.encode("utf-8") + b"\x00"
        slot = safe_slot(source, e)
        if len(raw) <= slot:
            cur = bytes(d[off:off + len(raw)])
            if cur != raw:
                old_end = e.get("end", off + len(raw))
                d[off:off + len(raw)] = raw
                if old_end > off + len(raw):
                    d[off + len(raw):old_end] = b"\x00" * (old_end - off - len(raw))
                changed += 1
            continue
        # does not fit: move to the overflow area
        refs = trusted_refs(e)
        if not refs:
            raise ValueError("cannot relocate unreferenced string at %#x" % off)
        if empty is None:
            raise ValueError("no empty PT_LOAD for translated overflow")
        new_off = align_up(overflow_at, ALIGN)
        overflow_at = new_off + len(raw)
        if new_off > len(d):
            d.extend(b"\x00" * (new_off - len(d)))
        d[new_off:new_off + len(raw)] = raw
        overflow_used = True
        moved += 1
        old_end = e.get("end", off + len(raw))
        d[off:old_end] = b"\x00" * (old_end - off)
        for r in refs:
            val = overflow_addr + new_off - overflow_start
            struct.pack_into(">I", d, r["pos"], val)

    if overflow_used:
        size = len(d) - overflow_start
        # Preserve Sony's segment-area flags; plain ELF flags alone request
        # PPU_PRIVATE in RPCS3 rather than this game's normal memory area.
        area_flags = next(p[1] & ~7 for p in loads if p[5] and p[1] & 1)
        struct.pack_into(">IIQQQQQQ", d, empty[0], 1, area_flags | 4, overflow_start,
                         overflow_addr, overflow_addr, size, size, 0x10000)
    with open(dst, "wb") as f:
        f.write(d)
    print("entries: %d, changed: %d, moved: %d, out: %s"
          % (len(entries), changed, moved, dst))


def align_up(v, a):
    return (v + a - 1) // a * a


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    if argv[1] == "extract":
        cmd_extract(argv[2], argv[3])
    elif argv[1] == "import":
        cmd_import(argv[2], argv[3], argv[4])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
