#!/usr/bin/env python3
"""Find the UI boxes in a screenshot by their pixels, not by arithmetic.

The width of a text panel is the one number that decides how many characters
fit in it, and it used to be inferred (880 px was derived from a 25-character
line times the pitch).  This tool measures the box itself: it quantises the
frame into small blocks, takes the *modal* brightness of each block -- the
background wins even when a glyph covers a third of the block -- and groups
blocks of the same level into rectangles.  Panels come out of that as
high-coverage rectangles, text and all.

A styled box rarely has one flat colour inside it: the game shades its dialogs
in bands, so the raw rectangles arrive as a stack of strips sharing an x-span.
Those are merged back into the one box they are, as long as the strips touch or
overlap (a real gap between two separate panels is left alone).  `--raw` reports
the strips instead, which is what to use when a merge looks wrong.

    python tools/panels.py find <shot.png> [--min-width N] [--top N] [--raw]
    python tools/panels.py fit  <shot.png> --band y0 y1 [--pitch 28] [--raw]
    python tools/panels.py selftest

`find` lists rectangles as x0,y0-x1,y1 with their size and how much of the
bounding box the panel actually fills (`cover`, 1.0 = a perfect rectangle), plus
how many bands were merged into it (`parts`).

`fit` answers the question the boxes exist for: which panel holds a line of
text, how wide it is in pixels, and -- given the pitch measured by
`tools/spacing.py measure` -- how many cells fit across it and how many pixels
are left over.  Run `selftest` after touching the detector; it renders panels of
known size (flat, bordered, banded, stacked-apart, noise) and checks what comes
back.
"""
import os
import sys
from typing import NamedTuple

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = 16              # brightness is quantised to this many levels
BLOCK = 4                # ... over blocks of this many pixels
MIN_WIDTH = 120          # narrower than this is a widget, not a panel
MIN_HEIGHT = 16
MIN_COVER = 0.72         # how much of the bounding box must be the same level
MIN_BLOCKS = 40
FILL_LIMIT = 0.97        # a region filling the frame is the background
MERGE_GAP = 4            # px: stacked bands this close are one box
MERGE_X_TOL = 6          # px: ...when their left and right edges agree this well


class Rect(NamedTuple):
    x0: int
    y0: int
    x1: int
    y1: int
    w: int
    h: int
    cover: float
    level: int
    parts: int = 1


def block_modes(im, block=BLOCK, levels=LEVELS):
    """Modal brightness of every block: the panel colour survives glyphs."""
    g = im.convert("L")
    px = g.load()
    w, h = g.size
    bw, bh = w // block, h // block
    modes = []
    for by in range(bh):
        row = []
        for bx in range(bw):
            counts = [0] * levels
            x0, y0 = bx * block, by * block
            for y in range(y0, y0 + block):
                for x in range(x0, x0 + block):
                    counts[px[x, y] * levels // 256] += 1
            row.append(counts.index(max(counts)))
        modes.append(row)
    return modes, bw, bh


def components(modes, bw, bh):
    """4-connected groups of blocks that share a level."""
    seen = [[False] * bw for _ in range(bh)]
    out = []
    for by in range(bh):
        for bx in range(bw):
            if seen[by][bx]:
                continue
            level = modes[by][bx]
            stack = [(bx, by)]
            seen[by][bx] = True
            cells = []
            while stack:
                x, y = stack.pop()
                cells.append((x, y))
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < bw and 0 <= ny < bh and not seen[ny][nx] \
                            and modes[ny][nx] == level:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            out.append((level, cells))
    return out


def merge_stacked(rs, gap=MERGE_GAP, x_tol=MERGE_X_TOL, min_cover=MIN_COVER):
    """Fold strips that share an x-span and touch vertically into one box.

    Repeat until nothing changes, so three bands become one on the first pass
    and stay one on the next.  The x edges must agree within `x_tol`, which is
    what keeps a narrow label next to a wide panel from being swallowed.
    """
    rs = list(rs)
    changed = True
    while changed:
        changed = False
        out = []
        used = [False] * len(rs)
        for i, first in enumerate(rs):
            if used[i]:
                continue
            cur = first
            for j in range(i + 1, len(rs)):
                if used[j]:
                    continue
                other = rs[j]
                if abs(cur.x0 - other.x0) > x_tol or \
                        abs(cur.x1 - other.x1) > x_tol:
                    continue
                # negative when they overlap
                ygap = max(other.y0 - cur.y1, cur.y0 - other.y1)
                if ygap > gap:
                    continue
                x0, x1 = min(cur.x0, other.x0), max(cur.x1, other.x1)
                y0, y1 = min(cur.y0, other.y0), max(cur.y1, other.y1)
                w, h = x1 - x0 + 1, y1 - y0 + 1
                solid = (cur.cover * cur.w * cur.h) + \
                        (other.cover * other.w * other.h)
                cover = solid / float(w * h)
                if cover < min_cover:
                    continue
                cur = cur._replace(x0=x0, y0=y0, x1=x1, y1=y1, w=w, h=h,
                                   cover=cover, parts=cur.parts + other.parts)
                used[j] = True
                changed = True
            out.append(cur)
        rs = out
    rs.sort(key=lambda r: r.w * r.h, reverse=True)
    return rs


def rects(im, min_width=MIN_WIDTH, min_height=MIN_HEIGHT,
          min_cover=MIN_COVER, min_blocks=MIN_BLOCKS, allow_fill=False,
          merge=True):
    """Boxes in the frame, widest area first.

    The screen background is a region too, and on a dark screen it is the
    biggest one; a box that fills the whole frame is dropped by default, since
    nothing containing text is measured against the frame edge.
    """
    modes, bw, bh = block_modes(im)
    found = []
    for level, cells in components(modes, bw, bh):
        if len(cells) < min_blocks:
            continue
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
        bwid, bhei = bx1 - bx0 + 1, by1 - by0 + 1
        if not allow_fill and bwid >= bw * FILL_LIMIT and \
                bhei >= bh * FILL_LIMIT:
            continue
        cover = len(cells) / float(bwid * bhei)
        w, h = bwid * BLOCK, bhei * BLOCK
        if w < min_width or h < min_height or cover < min_cover:
            continue
        found.append(Rect(bx0 * BLOCK, by0 * BLOCK, (bx1 + 1) * BLOCK - 1,
                          (by1 + 1) * BLOCK - 1, w, h, cover, level))
    if merge:
        return merge_stacked(found, min_cover=min_cover)
    found.sort(key=lambda r: r.w * r.h, reverse=True)
    return found


def cells_across(width, pitch):
    """How many cells of `pitch` px fit across `width`, and what is spare."""
    n = int(width // pitch)
    return n, width - n * pitch


def cmd_find(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    min_width = MIN_WIDTH
    top = 12
    if "--min-width" in argv:
        min_width = int(argv[argv.index("--min-width") + 1])
    if "--top" in argv:
        top = int(argv[argv.index("--top") + 1])
    im = Image.open(path)
    found = rects(im, min_width=min_width, merge="--raw" not in argv)
    print("%s  %dx%d  %d rectangle(s)"
          % (os.path.basename(path), im.size[0], im.size[1], len(found)))
    print("  x0,y0 - x1,y1         w x h    cover  level  parts")
    for r in found[:top]:
        print("  %4d,%3d - %4d,%3d  %4d x %3d   %.2f   %2d     %d"
              % (r.x0, r.y0, r.x1, r.y1, r.w, r.h, r.cover, r.level, r.parts))
    return 0


def cmd_fit(argv):
    if not argv or "--band" not in argv:
        print(__doc__)
        return 2
    path = argv[0]
    i = argv.index("--band")
    band = (int(argv[i + 1]), int(argv[i + 2]))
    pitch = None
    if "--pitch" in argv:
        pitch = float(argv[argv.index("--pitch") + 1])
    im = Image.open(path)
    mid = (band[0] + band[1]) / 2.0
    mine = [r for r in rects(im, merge="--raw" not in argv)
            if r.y0 <= mid <= r.y1]
    if not mine:
        print("no panel spans rows %d-%d.  Text there is drawn straight on the "
              "background, so only its pitch applies -- `python "
              "tools/spacing.py measure` reads that.  `find` lists the boxes "
              "this frame does have." % band)
        return 1
    # the box that holds the line is the tightest one around it
    mine.sort(key=lambda r: r.w * r.h)
    b = mine[0]
    print("%s  panel x %d-%d, y %d-%d  =  %d x %d px  (cover %.2f%s)"
          % (os.path.basename(path), b.x0, b.x1, b.y0, b.y1, b.w, b.h, b.cover,
             ", %d bands merged" % b.parts if b.parts > 1 else ""))
    if pitch:
        n, spare = cells_across(b.w, pitch)
        print("  at pitch %.2f px: %d cells fit, %d px left over "
              "(the next cell would need %.0f px)"
              % (pitch, n, spare, (n + 1) * pitch - b.w))
    return 0


def _draw_case(path, box, bg, fg, bars=True, border=None, pitch=28,
               size=(1280, 720)):
    w, h = size
    im = Image.new("L", (w, h), bg)
    dr = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    dr.rectangle([x0, y0, x1, y1], fill=fg)
    if border:
        dr.rectangle([x0, y0, x1, y1], outline=border, width=3)
    if bars:
        # glyph-like marks on a `pitch` grid inside the box
        x = x0 + 6
        while x + 3 < x1 - 4:
            dr.rectangle([x, y0 + 12, x + 3, y1 - 12], fill=bg)
            x += pitch
    im.save(path)


def _draw_bands(path, bands, bg, size=(1280, 720)):
    """A dialog shaded in bands, the way the game draws one."""
    im = Image.new("L", size, bg)
    dr = ImageDraw.Draw(im)
    for x0, y0, x1, y1, fill in bands:
        dr.rectangle([x0, y0, x1, y1], fill=fill)
    im.save(path)


def cmd_selftest(argv):
    out = os.path.join(ROOT, "work", "tex_view")
    os.makedirs(out, exist_ok=True)
    ok = True

    def check(name, got, want, tol):
        good = abs(got - want) <= tol
        print("  %-46s %6.1f  want %d +-%d  %s"
              % (name, got, want, tol, "ok" if good else "FAIL"))
        return good

    # 1) an 880 px panel on a dark screen, text inside it, 28 px pitch
    p1 = os.path.join(out, "panel_case_880.png")
    _draw_case(p1, (222, 44, 222 + 879, 44 + 119), bg=24, fg=196)
    r1 = rects(Image.open(p1))
    wide = max((r.w for r in r1), default=0)
    ok &= check("880 px panel, detected width", wide, 880, 8)
    if r1:
        n, _ = cells_across(wide, 28.0)
        ok &= check("cells across it at 28 px", n, 31, 0)

    # 2) a bordered panel: the interior is what text is drawn in
    p2 = os.path.join(out, "panel_case_border.png")
    _draw_case(p2, (100, 100, 100 + 599, 100 + 199), bg=16, fg=200,
               border=90, bars=False)
    r2 = [r for r in rects(Image.open(p2)) if r.w > 400]
    ok &= check("bordered 600 px panel, interior width",
                r2[0].w if r2 else 0, 594, 12)

    # 3) a texture, not a panel: must not report a wide rectangle
    p3 = os.path.join(out, "panel_case_texture.png")
    im = Image.new("L", (1280, 720))
    px = im.load()
    seed = 12345
    for y in range(720):
        for x in range(1280):
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            px[x, y] = (seed >> 16) & 0xFF
    im.save(p3)
    r3 = [r for r in rects(Image.open(p3)) if r.w >= 300]
    ok &= check("no wide rectangle in noise", len(r3), 0, 0)

    # 4) a dialog shaded in three overlapping bands: one box, not three strips
    p4 = os.path.join(out, "panel_case_bands.png")
    _draw_bands(p4, [(208, 240, 1071, 315, 144),
                     (208, 312, 1071, 419, 176),
                     (208, 416, 1071, 471, 208)], bg=24)
    r4 = rects(Image.open(p4))
    top = r4[0] if r4 else None
    ok &= check("banded dialog, merged width", top.w if top else 0, 864, 8)
    ok &= check("banded dialog, merged height", top.h if top else 0, 232, 12)
    ok &= check("banded dialog, bands merged", top.parts if top else 0, 3, 0)
    raw4 = [r for r in rects(Image.open(p4), merge=False) if r.w > 700]
    ok &= check("banded dialog, strips without merge", len(raw4), 3, 0)

    # 5) two separate panels with a real gap must stay two
    p5 = os.path.join(out, "panel_case_gap.png")
    _draw_bands(p5, [(200, 100, 799, 299, 180),
                     (200, 340, 799, 539, 180)], bg=24)
    r5 = [r for r in rects(Image.open(p5)) if r.w > 400]
    tallest = max((r.h for r in r5), default=0)
    ok &= check("gapped panels, count", len(r5), 2, 0)
    ok &= check("gapped panels, no merge (max height)", tallest, 200, 12)

    # 6) the cell arithmetic itself
    n, spare = cells_across(880, 28.0)
    print("  880 px / 28 px = %d cells, %d px spare (32 would need 896)"
          % (n, spare))
    ok &= (n == 31 and spare == 12)
    print("selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main(argv):
    if not argv or argv[0] not in ("find", "fit", "selftest"):
        print(__doc__)
        return 2
    return {"find": cmd_find, "fit": cmd_fit,
            "selftest": cmd_selftest}[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
