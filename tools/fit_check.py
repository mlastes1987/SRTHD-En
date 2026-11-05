#!/usr/bin/env python3
"""Check short UI labels against the panel they are drawn inside.

The engine neither clips nor shrinks a string: it draws the whole line from the
panel's text origin, so anything wider than the panel runs out over the frame
edge.  That is how "Spirit search" (13 cells) and "Start Battle" (12) shipped
past a 317 px box, and why the unit list's "Great Mazinger" ran into the HP
column.

The panel widths below are measured, not inferred: the cyan border of each
panel was scanned out of a 1280x720 RPCS3 capture (the same idea as
`tools/panels.py`, but reading a border colour instead of a fill level), and
the capacity is that width divided by the advance stored in the EBOOT.  At the
stock 35 px the narrow menus hold 9 cells; at the installed 28 px they hold 11,
which is what the current wording is written to.

    pane                 capture     x0..x1     px   cells@35  cells@28
    command menu         18:59:33    911..1231  321       9        11
    turn box             18:59:33    911..1231  321       9        11
    intermission menu    19:22:12     48..365   318       9        11
    battle confirm box   19:02:04    480..797   318       9        11
    unit-list names      19:06:04    169..620   452      13        16

The name column's right edge is the first pixel of the HP figures (624), not a
box border -- the game draws the whole name and lets it run into that column,
which is what "Great Mazinge39/42" was.

The dialogue boxes are not checked here: they wrap (`tools/reflow.py`) and are
measured separately in docs/TRANSLATION.md.

    python tools/fit_check.py               # against the installed 28 px pitch
    python tools/fit_check.py --pitch 35    # what the stock build allows
    python tools/fit_check.py --list        # capacities only
    python tools/fit_check.py probe a.png b.png c.png   # measure new captures
    python tools/fit_check.py --inferred     # worklist for a screen with none

The `probe` mode measures any 1280x720 capture and prints ready-to-paste
`PANES` rows, so a screen that has not been looked at yet needs one command
rather than arithmetic by hand.  It finds boxes three ways, because no single
one covers the UI:

* the **cyan frames** of the menu panels (a border scan down each column),
* the **grey frames** of the status boxes, same scan, neutral colour,
* the **fill level** for boxes whose left frame sits over the character art and
  so never forms a column at all (`panels.py`'s method).

One box reports itself several ways -- outer bevel, inner line, flat plate -- so
a candidate lying inside a wider one is dropped as the same box, and the widest
survives.  The raw border columns are printed above the panes, so an inner line
is still readable when the outer bevel is not the edge that matters.

It then splits each pane into **text columns**: for every x it counts pixels
brighter than that row's own median, and cuts where *no* row has ink.  A gap
between letters is empty in one row; a gap between columns is empty in every
row, which is what separates a list's name column from its values.  Narrow the
band to a single row (`--y0/--y1`) when rows overlap their neighbours.
"""
import argparse
import csv
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "work", "text", "translation.csv")
PITCH = 28.0          # installed advance (`tools/pitch_patch.py --to 28`)

# Screenshot 2026-10-28 20:41:32: right spirit column starts at x=746,
# SP cost begins at x=910. The glyph draw size is 38 px.
SPIRIT_NAME_IDS = {5454, 5456, 5458, 5460, 5462, 5465, 5468, 5471,
                   5473, 5475, 5478, 5480, 5483, 5485, 5487, 5490,
                   5493, 5496, 5498, 5500, 5502, 6861}


def spirit_names():
    with open(os.path.join(ROOT, "work/text/proportional_metrics.json"), encoding="utf-8") as f:
        metrics = json.load(f)["metrics"]
    bad = 0
    rows = [r for r in load() if int(r["id"]) in SPIRIT_NAME_IDS]
    for r in rows:
        text = r["english"]
        width = sum(int(metrics[c]["advance"] * 38 + metrics[c].get("adjust_px", 0))
                    for c in text if c in metrics)
        unsupported = any(c not in metrics for c in text)
        over = width > 164 or unsupported
        bad += int(over)
        if over or int(r["id"]) == 5502:
            print("%s id=%s %r: %d / 164 px%s" %
                  ("OVER" if over else "OK", r["id"], text, width,
                   " (unsupported glyph)" if unsupported else ""))
    print("spirit names: %d checked, %d over their measured field" % (len(rows), bad))
    return int(bool(bad))

# name, capture time, x0, x1, row ids and/or file-offset ranges of the rows
# drawn in that panel.
PANES = [
    ("command menu", "18:59:33", 911, 1231,
     ["6584", "6585", "6586", "6587", "6588", "6589", "6590"], []),
    ("turn box", "18:59:33", 911, 1231,
     ["6591", "6592"], []),
    ("intermission menu", "19:22:12", 48, 365,
     ["6265", "6266", "6267", "6268", "6269", "6270", "6271", "6272"], []),
    ("battle confirm box", "19:02:04", 480, 797,
     ["6200", "6201", "6202", "6203", "6204"], []),
    # the unit name column of the squad list; the names are the rows that sit
    # in this offset window (cp932 table, so romaji only)
    ("unit-list names", "19:06:04", 169, 620, [], [(0x47E600, 0x47F200)]),
    # the label half of a stat box on the hero/team panel (ids 6352-6359 are
    # the HP / SP / Atk / Def / Speed / Loyal / Charm / Move set that capture
    # shows).  The field is 149 px, not the 640 px box: five cells at 28 px,
    # four at the stock 35 -- which is why "Attack" printed as "Attac25".
    ("status label column", "16:18:54", 692, 841,
     ["6352", "6353", "6354", "6355", "6356", "6357", "6358", "6359"],
     []),
]


def load():
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def in_pane(row, ids, ranges):
    if row["id"] in ids:
        return True
    off = int(row["offset"], 16)
    return any(lo <= off <= hi for lo, hi in ranges)


INK = 0.75            # a glyph's ink as a fraction of its advance


def widest(row):
    """The longest display line, in cells (one advance per character)."""
    return max(len(line) for line in row["english"].rstrip().split("\n"))


def drawn(cells, pitch):
    """Pixels a line actually covers.

    Characters step by a fixed advance, but the last cell only paints its ink,
    so an n-cell line is (n-1) advances plus one glyph, not n advances.  That
    is worth a whole cell on a 411 px column: a 15-cell name still clears the
    HP figures, a 16-cell one does not.
    """
    return max(0, cells - 1) * pitch + INK * pitch


CYAN = lambda c: c[2] > 110 and c[1] > 85 and c[2] > c[0] + 35
GREY = lambda c: max(c) - min(c) < 34 and 120 < c[0] < 245


def border_columns(im, test, y0, y1, frac=0.35):
    """Columns that are a panel border over most of the band."""
    px = im.load()
    need = (y1 - y0) * frac
    out = []
    for x in range(im.size[0]):
        n = 0
        for y in range(y0, y1):
            if test(px[x, y]):
                n += 1
                if n > need:
                    out.append(x)
                    break
    return out


def group(xs, gap=3):
    out, cur = [], []
    for x in xs:
        if cur and x - cur[-1] > gap:
            out.append((cur[0], cur[-1]))
            cur = []
        cur.append(x)
    if cur:
        out.append((cur[0], cur[-1]))
    return out


def fill_panes(im, y0, y1, min_w=120, min_h=40, top=8):
    """Boxes found by their fill, not their frame (`panels.py`).

    The cyan menus are bordered by a line, but the status and list boxes are a
    flat grey plate inside a bevelled frame whose left edge sits over the
    character art, so a border scan misses them and the fill level does not.
    """
    try:
        import panels
    except ImportError:
        return []
    return [r for r in panels.rects(im, min_width=min_w, min_height=min_h,
                                    merge=True)[:top]
            if not (r.y1 < y0 or r.y0 > y1)]


def ink_profile(im, x0, x1, y0, y1, thr=40):
    """Pixels per column that are brighter than their own row's median.

    The row median is the local background, so the count is glyph ink whatever
    the panel is shaded like.  This is what finds a list's columns: a gap
    between letters is empty in *one* row, a gap between columns is empty in
    every row.
    """
    g = im.convert("L")
    px = g.load()
    prof = [0] * (x1 - x0 + 1)
    for y in range(y0, y1):
        row = [px[x, y] for x in range(x0, x1 + 1)]
        med = sorted(row)[len(row) // 2]
        for i, v in enumerate(row):
            if v > med + thr:
                prof[i] += 1
    return prof


def text_columns(prof, x0, pitch, min_ink=2, gap=None):
    """Column spans of a list, split at the x positions empty in every row."""
    gap = gap or max(20, int(pitch * 0.7))
    out, start, empty = [], None, 0
    for i, p in enumerate(prof):
        if p >= min_ink:
            if start is None:
                start = i
            empty = 0
        elif start is not None:
            empty += 1
            if empty >= gap:
                out.append((x0 + start, x0 + i - empty))
                start = None
    if start is not None:
        out.append((x0 + start, x0 + len(prof) - 1))
    return out


# Label blocks with no capture behind them.  Each is a table of short names or
# labels; the longest Japanese entry is the *lower bound* on the column, so an
# English row past it is a candidate overflow -- not a measured one.
BLOCKS = [
    ("item names + effects", 0x471300, 0x472100),
    ("weapon / attack names", 0x478E00, 0x479D00),
    ("options: button functions", 0x472100, 0x472400),
    ("options: settings + help", 0x47DB00, 0x47E100),
]


import re


def single_line(row):
    """A short name or label, as opposed to a help sentence or a rule.

    Sentences end with a full stop and wrap; the dash runs are separators drawn
to the width of the panel on purpose.  Neither is a label, and both would
inflate the budget of the block they sit in.
    """
    if "\n" in row["english"].rstrip() or "\n" in row["japanese"]:
        return False
    if re.search(r"%[dsx]", row["japanese"] + row["english"]):
        return False
    if row["japanese"].rstrip().endswith("。"):
        return False
    return not re.match(r"^[\u30fc\-\u2500\u2015\s]+$", row["japanese"])


def inferred(pitch, slack):
    """Rows that look too wide for a block whose column was never measured.

    The column of a Japanese list is at least as wide as the longest Japanese
    entry in it, and that Japanese was laid out at the stock 35 px advance --
    so the English budget in cells is `longest_jp * 35 / pitch`, not
    `longest_jp`.  Getting that wrong is a silent 25% error at the installed
    28 px.  The comparison is in cells because the box is fixed pixels; the
    same column holds a quarter more characters once the advance is patched.

    This is a worklist, not a verdict: rows within `slack` cells of the budget
    are left alone, nothing is changed by running it, and `--pitch 35` asks the
    strict question (what a pane that kept the stock advance could hold).
    """
    print("inferred budgets (no capture; English at %.0f px, columns measured "
          "at the stock 35 px, slack %d cells)" % (pitch, slack))
    rows = load()
    total = 0
    for name, lo, hi in BLOCKS:
        sel = [r for r in rows
               if lo <= int(r["offset"], 16) <= hi and r["english"]
               and single_line(r)]
        if not sel:
            continue
        jp = max(len(r["japanese"]) for r in sel)
        budget = jp * 35.0 / pitch
        over = [r for r in sel if len(r["english"]) > budget + slack]
        print("  %-28s %3d rows  longest jp %2d cells -> budget %5.1f cells  "
              "%d over" % (name, len(sel), jp, budget, len(over)))
        for r in sorted(over, key=lambda r: -len(r["english"])):
            print("    id=%s jp%2d en%2d  %s  ->  %s"
                  % (r["id"], len(r["japanese"]), len(r["english"]),
                     r["japanese"], r["english"]))
        total += len(over)
    print("inferred: %d candidate row(s); a capture is what turns these into "
          "measurements" % total)
    return 0


def probe(path, pitch, y0=None, y1=None, lo=120, hi=1200):
    """Print candidate panes and their text columns from one capture."""
    im = Image.open(path).convert("RGB")
    if y0 is None:
        y0 = 0
    if y1 is None:
        y1 = im.size[1]
    print("%s  %dx%d  rows %d..%d  pitch %.0f"
          % (os.path.basename(path), im.size[0], im.size[1], y0, y1, pitch))

    panes = []          # (how found, x0, x1)
    for name, test in (("cyan", CYAN), ("grey", GREY)):
        # a real frame is at least 3 px thick; single-pixel columns are glyph
        # strokes or map highlights and would invent panes out of nothing
        cols = [c for c in group(border_columns(im, test, y0, y1))
                if c[1] - c[0] >= 2]
        if not cols:
            continue
        print("  %s border columns: %s"
              % (name, ", ".join("%d-%d" % c for c in cols)))
        centres = [sum(c) // 2 for c in cols]
        for a, b in zip(centres, centres[1:]):
            if not lo <= b - a + 1 <= hi:
                continue
            if any(abs(a - p[1]) < 8 and abs(b - p[2]) < 8 for p in panes):
                continue
            panes.append((name + " frame", a, b))

    for r in fill_panes(im, y0, y1):
        panes.append(("fill level", r.x0, r.x1))

    # one box reports itself several ways -- outer frame, inner frame, fill --
    # so a candidate that sits inside a wider one is the same box, not another
    keep = []
    for p in sorted(panes, key=lambda p: -(p[2] - p[1])):
        if any(q[1] - 40 <= p[1] and p[2] <= q[2] + 40 for q in keep):
            continue
        keep.append(p)
    panes = sorted(keep, key=lambda p: p[1])

    if not panes:
        print("  no pane found -- pass --y0/--y1 to the band holding the boxes")
        return 0

    for how, a, b in panes:
        print("  pane  %4d..%-4d  %4d px  %5.1f cells   [%s]"
              % (a, b, b - a + 1, (b - a + 1) / pitch, how))
        print("        -> (\"<name>\", \"<capture>\", %d, %d, [...], [])" % (a, b))

    for how, a, b in panes:
        cols = text_columns(ink_profile(im, a + 2, b - 2, y0, y1), a + 2, pitch)
        if len(cols) < 2:
            continue            # one centred column: there is nothing to divide
        print("  text columns in %d..%d:" % (a, b))
        for i, (c0, c1) in enumerate(cols):
            nxt = cols[i + 1][0] if i + 1 < len(cols) else b + 1
            print("    %4d..%-4d  ink %3d px   field %4d..%-4d = %4d px  %5.1f cells"
                  % (c0, c1, c1 - c0 + 1, c0, nxt, nxt - c0, (nxt - c0) / pitch))
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitch", type=float, default=PITCH,
                    help="advance in pixels (default %.1f, the installed value)"
                    % PITCH)
    ap.add_argument("--list", action="store_true", help="print capacities only")
    ap.add_argument("--spirits", action="store_true",
                    help="check spirit names using measured proportional advances")
    ap.add_argument("--y0", type=int, help="probe: first row of the band")
    ap.add_argument("--y1", type=int, help="probe: last row of the band")
    ap.add_argument("--inferred", action="store_true",
                    help="list rows over the Japanese budget of an unmeasured "
                         "label block")
    ap.add_argument("--slack", type=int, default=4,
                    help="cells of room to grant an unmeasured column (4)")
    ap.add_argument("args", nargs="*")
    args = ap.parse_args(argv[1:])

    if args.spirits:
        return spirit_names()

    if args.inferred:
        return inferred(args.pitch, args.slack)

    if args.args and args.args[0] == "probe":
        if len(args.args) < 2:
            print("usage: fit_check.py probe <shot.png> [more.png ...] "
                  "[--y0 N --y1 N] [--pitch P]")
            return 2
        rc = 0
        for path in args.args[1:]:
            rc |= probe(path, args.pitch, args.y0, args.y1)
            print()
        return rc

    rows = load()
    if args.list:
        print("pane                  px wide  cells@%.0f  cell px" % args.pitch)
        for name, shot, x0, x1, _, _ in PANES:
            print("  %-18s %5d      %6.1f    %5.1f"
                  % (name, x1 - x0 + 1, (x1 - x0 + 1) / args.pitch, args.pitch))
        return 0

    bad = 0
    for name, shot, x0, x1, ids, ranges in PANES:
        width = x1 - x0 + 1
        cap = width / args.pitch
        hit = [r for r in rows if r["english"] and in_pane(r, ids, ranges)]
        over = [(r, widest(r)) for r in hit if drawn(widest(r), args.pitch) > width]
        print("%s  (%d px, %.1f cells at %.1f px, capture %s): %d row(s), %d over"
              % (name, width, cap, args.pitch, shot, len(hit), len(over)))
        for r, cells in sorted(over, key=lambda t: -t[1]):
            print("    id=%s %s  %d cells (%.0f px of %d): %r"
                  % (r["id"], r["offset"], cells, drawn(cells, args.pitch),
                     width, r["english"]))
        bad += len(over)
    print("fit: %d label(s) wider than their measured panel at %.1f px"
          % (bad, args.pitch))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
