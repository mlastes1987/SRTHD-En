#!/usr/bin/env python3
"""Rewrite the `38.0` floats in the UI descriptor tables.  Kept for the record.

  python tools/narrow_text.py --list                       # show the sites
  python tools/narrow_text.py --size 30 --install          # patch + install
  python tools/narrow_text.py --restore                    # rebuild clean

The problem: the engine draws every character on a fixed advance, whatever its
ink width, so Latin reads "H i t   R a t e" even though an 'l' is ~4 px of ink
and an 'S' ~21 px.  Any fix has to change that advance for half-width
characters, and it would apply to every line already translated.

Why this tool is *not* that fix.  The 81 values look like a font size only
because the pitch was once assumed to be 38; it is measured at 35.0 px now (see
docs/TRANSLATION.md), and the record around a site is a run of x/y/width/height
numbers -- 785.0, 1058.0, 1.0, 0.0, 16.0, 102.0, 30.0, 298.0, 36.0, 38.0,
24.0, 304.0 at 0x4dd5c0 -- so it is most likely layout geometry that the patch
*moves*.  Patching to 30.0 was reported as moving the pitch "38 -> 35", which
is just the measured value: probably nothing moved at all.  The 16.0 build is
installed to settle it.

If it is tried again, measure instead of eyeballing:
`python tools/spacing.py measure <screenshot>` returns the pitch, and
`python tools/width_check.py --pitch N` says what a pitch would buy.

This only touches float data in the UI descriptor tables, never string bytes or
pointers, so `verify_build.py` still covers everything it covered before.
"""
import argparse
import os
import re
import shutil
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as buildtool  # noqa: E402  (reuse the install paths)

IMAGE = os.path.join(ROOT, "build", "EBOOT.BIN")
FROM = 38.0
VADDR_DELTA = 0x10000


def find_sites(d, value):
    pat = struct.pack(">f", value)
    return [m.start() for m in re.finditer(re.escape(pat), d)]


def label_for(d, site):
    """Nearest string pointer before the site, for a human-readable name."""
    for off in range(site, site - 224, -4):
        if off < 0:
            break
        v = struct.unpack_from(">I", d, off)[0]
        if 0x480000 <= v <= 0x4E44A8:
            start = v - VADDR_DELTA
            end = d.find(b"\x00", start)
            if 0 < end - start < 80:
                try:
                    s = d[start:end].decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if s.strip():
                    return s.replace("\n", " / ")[:30]
    return "?"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=None,
                    help="new font size for the descriptor tables")
    ap.add_argument("--from", dest="frm", type=float, default=FROM,
                    help="size to replace (default %g)" % FROM)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args(argv[1:])

    if args.restore:
        return buildtool.main(["--install"])

    if not os.path.exists(args.image):
        print("no image at", args.image, "- run tools/build.py first")
        return 2
    d = bytearray(open(args.image, "rb").read())
    sites = find_sites(d, args.frm)

    if args.list or args.size is None:
        print("%d site(s) holding %.1f in %s" % (len(sites), args.frm, args.image))
        for s in sites[:40]:
            print("  %#08x  %s" % (s, label_for(d, s)))
        if len(sites) > 40:
            print("  ... and %d more" % (len(sites) - 40))
        if args.size is None:
            return 0

    pat = struct.pack(">f", args.size)
    for s in sites:
        d[s:s + 4] = pat
    open(args.image, "wb").write(bytes(d))
    print("patched %d site(s): %.1f -> %.1f in %s"
          % (len(sites), args.frm, args.size, args.image))

    if args.install:
        dst = os.path.join(buildtool.RPCS3_GAME, "EBOOT.BIN")
        shutil.copy2(args.image, dst)
        print("installed ->", dst)
        play = os.path.join(ROOT, "build", "game", "USRDIR", "EBOOT.BIN")
        if os.path.exists(play):
            shutil.copy2(args.image, play)
            print("refreshed test copy ->", play)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
