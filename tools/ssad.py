#!/usr/bin/env python3
"""CRI SSAD animation/pane container reader for Super Robot Taisen 1 HD.

SSAD is what the game uses for every animated UI element.  It is not text and
not a texture: it is a tree of panes whose names are the only human-readable
thing in the CPKs.

    "SSAD" | u16 version (2) | u16 4 | u32 0 | u32 ? | u32 0
           | u32 ?        | u32 fps*? | u32 1000
    then a chunk stream from 0x20:
        tag(4) | size(u32 LE) | payload(size)

Chunk tags seen in this game: PART NAME AREA ORGX ORGY TBDT MYID PAID CHID
PCID SUCD PRIO POSX POSY ANGL SCAX SCAY TRAN HIDE FLPH FLPV UDAT PCOL PALT
VERT IMGX IMGY IMGW IMGH ORFX ORFY.

Every property chunk (`PRIO`, `POSX`, ...) is followed by an 8-byte keyframe
header (count, time) which is *not* counted in `size`; the parser therefore
resynchronises on the next known tag instead of trusting the size alone.  A
pane starts at a `PART` chunk and its `NAME` chunk carries the label.

Usage:
  python tools/ssad.py dump  <file> [--all]
  python tools/ssad.py list  <dir>
  python tools/ssad.py trees <dir>          # pane trees for every file
"""
import os
import struct
import sys

TAGS = ("PART NAME AREA ORGX ORGY TBDT MYID PAID CHID PCID SUCD PRIO POSX POSY "
        "ANGL SCAX SCAY TRAN HIDE FLPH FLPV UDAT PCOL PALT VERT IMGX IMGY "
        "IMGW IMGH ORFX ORFY").split()
TAGSET = {t.encode() for t in TAGS}


def chunks(data):
    """Yield (tag, payload, offset) for every chunk, resynchronising past the
    8-byte keyframe headers that follow property chunks."""
    out = []
    p = 0x20
    n = len(data)
    while p + 8 <= n:
        tag = data[p:p + 4]
        if tag not in TAGSET:
            p += 1
            continue
        size = struct.unpack_from("<I", data, p + 4)[0]
        if p + 8 + size > n or size > 0x100000:
            p += 1
            continue
        out.append((tag.decode(), data[p + 8:p + 8 + size], p))
        p += 8 + size
    return out


def decode_name(raw):
    """Pane names are ASCII in the newer UI files and Shift-JIS in the battle
    effect files (e.g. 残痕2, サーベルエフェクト1, 爆発1)."""
    raw = raw.split(b"\x00")[0]
    for enc in ("ascii", "cp932", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", "replace")


def u32(payload):
    return struct.unpack_from("<I", payload, 0)[0] if len(payload) >= 4 else None


def parse(data):
    """Return {'version','fps','panes':[...]} for an SSAD blob."""
    if data[:4] != b"SSAD":
        raise ValueError("not an SSAD file")
    info = {
        "version": struct.unpack_from("<H", data, 4)[0],
        "fps": struct.unpack_from("<I", data, 0x18)[0] if len(data) >= 0x1C else 0,
    }
    panes = []
    current = None
    for tag, payload, _off in chunks(data):
        if tag == "PART":
            current = {"part": u32(payload), "name": "", "myid": None,
                       "paid": None, "prio": None, "area": None,
                       "org": [None, None]}
            panes.append(current)
            continue
        if current is None:
            continue
        if tag == "NAME":
            current["name"] = decode_name(payload)
        elif tag == "MYID":
            current["myid"] = u32(payload)
        elif tag == "PAID":
            current["paid"] = struct.unpack_from("<i", payload, 0)[0]
        elif tag == "PRIO":
            current["prio"] = u32(payload)
        elif tag == "AREA":
            # four *integers*: the sprite's rectangle inside its atlas page.
            # Read as floats they are denormals and print as 0 -- which is how
            # kuro/00030's message-window pieces went unnoticed for so long.
            current["area"] = struct.unpack_from("<4I", payload, 0)
        elif tag == "ORGX":
            current["org"][0] = struct.unpack_from("<i", payload, 0)[0]
        elif tag == "ORGY":
            current["org"][1] = struct.unpack_from("<i", payload, 0)[0]
    info["panes"] = panes
    return info


def cmd_dump(path, all_panes):
    data = open(path, "rb").read()
    info = parse(data)
    print("%s  version=%d  panes=%d" % (path, info["version"], len(info["panes"])))
    limit = len(info["panes"]) if all_panes else 24
    for p in info["panes"][:limit]:
        if p["area"]:
            x0, y0, x1, y1 = p["area"]
            area = "%d,%d-%d,%d (%dx%d)" % (x0, y0, x1, y1, x1 - x0, y1 - y0)
        else:
            area = "-"
        print("  part %-3s %-24s org=%s,%s atlas=%s prio=%s"
              % (p["part"], p["name"], p["org"][0], p["org"][1], area,
                 p["prio"]))
    if len(info["panes"]) > limit:
        print("  ... %d more" % (len(info["panes"]) - limit))
    return 0


def cmd_list(directory):
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        data = open(path, "rb").read()
        if data[:4] != b"SSAD":
            continue
        info = parse(data)
        labels = [p["name"] for p in info["panes"]]
        print("%-12s %8d  panes=%3d  %s" % (name, len(data), len(labels),
                                            ", ".join(labels[:6]) +
                                            (" ..." if len(labels) > 6 else "")))
    return 0


def cmd_trees(directory):
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        data = open(path, "rb").read()
        if data[:4] != b"SSAD":
            continue
        info = parse(data)
        print("== %s (%d panes)" % (name, len(info["panes"])))
        for p in info["panes"]:
            print("   %3s %s" % (p["part"], p["name"]))
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "dump":
        return cmd_dump(argv[2], "--all" in argv)
    if cmd == "list":
        return cmd_list(argv[2])
    if cmd == "trees":
        return cmd_trees(argv[2])
    print("unknown command:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
