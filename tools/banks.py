#!/usr/bin/env python3
"""Attach pointer-table ("bank") context to the extracted text."""
import json
import struct
import sys

DATA_LO = 0x3f7b04
DELTA = 0x10000


def load_strings(path):
    ents = json.load(open(path, encoding="utf-8"))
    return ents


def main(elf, text_json, out_json):
    d = open(elf, "rb").read()
    ents = load_strings(text_json)
    offsets = {e["off"] for e in ents}
    vaddrs = {o + DELTA for o in offsets}
    valid = offsets | vaddrs

    # map: 4-byte value -> string offset
    def resolve(pos):
        v = struct.unpack_from(">I", d, pos)[0]
        if v in offsets:
            return v, False
        if v in vaddrs:
            return v - DELTA, True
        return None, None

    banks = {}
    seen = set()
    for e in ents:
        for r in e["refs"]:
            pos = r["pos"]
            if pos in seen:
                continue
            # extend left/right while entries resolve to strings
            start = pos
            while start - 4 >= DATA_LO and resolve(start - 4)[0] is not None:
                start -= 4
            end = pos
            while end + 4 <= len(d) - 4 and resolve(end + 4)[0] is not None:
                end += 4
            banks[start] = list(range(start, end + 1, 4))
            seen.update(banks[start])

    for e in ents:
        e["bank"] = None
        e["index"] = None
        for bstart, positions in banks.items():
            for i, p in enumerate(positions):
                t, isv = resolve(p)
                if t == e["off"]:
                    e["bank"] = bstart
                    e["index"] = i
                    break
            if e["bank"] is not None:
                break
    json.dump(ents, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("banks: %d, entries with bank: %d/%d"
          % (len(banks), sum(1 for e in ents if e["bank"] is not None), len(ents)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
