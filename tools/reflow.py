#!/usr/bin/env python3
"""Re-wrap translated lines to the width the game's boxes actually hold.

  python tools/reflow.py [--width 20] [--check]

The engine does not word-wrap: it prints the newlines that are in the string.
The Japanese proves the budget -- across the 5,061 script rows no display line
is longer than 19 cells, and the widest in the whole file is 24.  So every
display line here is kept at WIDTH (default 20) or less, and continuation lines
get the game's own leading ideographic space.

Multi-word glossary terms ("God Noah", "Jet Stream Attack") are kept whole: a
term split across a line break reads as two different terms and fails
glossary_check, which is right.

Run it after merging chunks; `translate_kit.py merge` calls it automatically.

  --check   report only, change nothing (for CI-style verification)
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, "work", "text", "text_banks.json")
CSV = os.path.join(ROOT, "work", "text", "translation.csv")
GLOSSARY = os.path.join(ROOT, "work", "text", "glossary.csv")

WIDTH = 20
INDENT = "\u3000"          # the game's continuation indent
SINGLE_LO, SINGLE_HI = 0x47BE00, 0x47F000   # fixed single-line screens
# Those screens never wrap, so their cap is not WIDTH: a screenshot showed a
# 32-character line fitting with room and a 34-character one clipping.
SINGLE_CAP = 32
# Fixed single-line labels *outside* that range.  They are drawn in a panel
# that never wraps, so the 20-cell dialogue budget does not apply and any
# newline in the English is a bug (the second line is simply never drawn).
# Each value is the character cap the panel holds, measured off a capture with
# `fit_check.py probe <shot> --y0 .. --y1`.
FIXED_LABELS = {
    0x4711B0: 23,   # intermission status bar ("Clear ep.N <M turns>"): 648 px
    0x478A08: 5,    # episode number, title screen ("Ep.N"): ~40 px pitch
    0x478A18: 16,   # quoted speaker/ending template ("%s")
    0x478A30: 16,   # "next time" title template ("%s":)
    0x47DAF0: 4,    # spirit/item detail label "Eff." (~129 px column)
    0x47DAF8: 4,    # spirit/item detail label "Tgt."
    0x47DB28: 4,
    0x47DB30: 4,
    0x47DB50: 4,
    0x47DB58: 4,
    0x47DB78: 4,
    0x47DB80: 4,
}
# Banks whose element draws exactly one bank row per display line.  A newline
# in such a row spills into the next row's slot and is overwritten, so the row
# must be a single line.  The briefings are a little wider than the previews.
FIXED_BANKS = {
    0x53601C: 22,   # mission briefing lines, title screen (x=585, ~30.5 px)
}
PREVIEW_BANK_LO, PREVIEW_BANK_HI = 0x53601C, 0x5367A0
BRIEFING_LO, BRIEFING_HI = 0x53601C, 0x536034
PREVIEW_CAP = 22    # next-episode preview, x=91, ~31 px italic outline
# Spirit-command detail descriptions (one bank row = one display line).
SPIRIT_OFF_LO, SPIRIT_OFF_HI = 0x473798, 0x474020
SPIRIT_CAP = 42     # value column x=249..1238 at ~23 px
MASK = "\x1f"              # stand-in for a space inside a locked term

SPEC = re.compile(r"%[-+ #0-9.]*[sdxXfgb]")


def load_terms():
    """Multi-word English glossary terms that must not be broken."""
    terms = set()
    if os.path.exists(GLOSSARY):
        with open(GLOSSARY, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                en = (row.get("english") or "").strip()
                if " " in en and MASK not in en:
                    terms.add(en)
    return sorted(terms, key=len, reverse=True)


TERMS = load_terms()


def mask(s):
    for t in TERMS:
        if t in s:
            s = s.replace(t, t.replace(" ", MASK))
    return s


def unmask(s):
    return s.replace(MASK, " ")


def tokens(s):
    """Split into atomic tokens: words, with glossary terms locked together.

    Splitting on spaces alone is deliberate.  An earlier version also cut each
    format specifier out as its own token, and the words either side of it then
    had a space inserted between them when the line was rejoined: `"%s"` came
    out as `" %s "`, and `%dbyte` as `%d byte`.  Words are never split here (a
    specifier lives inside its word), and `wrap` refuses to cut a specifier when
    a word really is longer than the box.
    """
    return [t for t in mask(s).split(" ") if t != ""]


def cut_point(tok, width):
    """A hard-split index that does not land inside a format specifier."""
    cut = width
    for m in SPEC.finditer(tok):
        if m.start() < cut < m.end():
            cut = m.start()
            break
    return cut or width


def wrap(text, width=WIDTH):
    """Greedy wrap into lines of at most `width` cells."""
    lines, cur = [], ""
    for tok in tokens(text):
        cand = tok if not cur else cur + " " + tok
        if len(cand) <= width:
            cur = cand
            continue
        if cur:
            lines.append(cur)
            cur = ""
        # a single token longer than the box: hard-split it
        while len(tok) > width:
            cut = cut_point(tok, width)
            lines.append(tok[:cut])
            tok = tok[cut:]
        cur = tok
    if cur:
        lines.append(cur)
    return [unmask(l) for l in lines]


def reflow(text, width=WIDTH):
    """Re-wrap, keeping one trailing newline if the string had one.

    The engine prints exactly the newlines in the string, so a leading or
    trailing ``\n`` is a real blank line and is not the wrapper's to drop.
    """
    leading, trailing = text.startswith("\n"), text.endswith("\n")
    logical = [l.lstrip(INDENT).strip() for l in text.split("\n")]
    out = []
    for l in logical:
        if not l:
            continue
        out.extend(wrap(l, width))
    body = "\n".join((out[0] if i == 0 else INDENT + l)
                     for i, l in enumerate(out))
    if not body:
        return body
    if leading:
        body = "\n" + body
    return body + "\n" if trailing else body


def cap_for(e):
    """Character cap for a row drawn by a one-line-per-row element, else None."""
    off = e["off"]
    if SINGLE_LO <= off <= SINGLE_HI:
        return SINGLE_CAP
    if off in FIXED_LABELS:
        return FIXED_LABELS[off]
    refs = e.get("refs") or []
    # Briefing and preview rows are also referenced from the script tables, so
    # test every pointer, not just the row's nominal bank.  Only vaddr-form
    # pointers can be trusted here: the same 32-bit value turns up as ordinary
    # data elsewhere in the preview tables.
    vrefs = [r for r in refs if r.get("vaddr")]
    if any(BRIEFING_LO <= r["pos"] < BRIEFING_HI for r in vrefs):
        return FIXED_BANKS[0x53601C]
    if any(PREVIEW_BANK_LO <= r["pos"] < PREVIEW_BANK_HI for r in vrefs):
        return PREVIEW_CAP
    if SPIRIT_OFF_LO <= off < SPIRIT_OFF_HI:
        return SPIRIT_CAP
    return None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=WIDTH)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv[1:])

    ents = {e["id"]: e for e in json.load(open(TEXT, encoding="utf-8"))}
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())

    changed = 0
    skipped = 0
    over = []
    split = []
    # Battle balloons have a two-line height limit as well as a width limit.
    # Keep subsequent translation merges consistent with the measured font.
    from battle_dialogue import wrap as wrap_battle
    metrics_path = os.path.join(ROOT, 'work', 'text', 'proportional_metrics.json')
    battle_metrics = json.load(open(metrics_path, encoding='utf-8'))['metrics'] if os.path.exists(metrics_path) else None
    for r in rows:
        en = r["english"].strip()
        if not en:
            continue
        e = ents[int(r["id"])]
        if battle_metrics and 0x422410 <= e['off'] < 0x46f350:
            new = wrap_battle(r['english'], battle_metrics)
            if new != r['english']:
                r['english'] = new
                changed += 1
            continue
        cap = cap_for(e)
        if cap is not None:
            # These screens never wrap; wrapping would hide the overflow.  The
            # width is measured on the raw line, because a leading ideographic
            # space is a full cell on screen: `str.strip()` eats it, which used
            # to let a 33-cell line pass as 32.  A fixed *label* must also be a
            # single line, so a newline is reported even when each line fits.
            lines = r["english"].rstrip().split("\n")
            worst = max(len(l) for l in lines)
            if len(lines) > 1 or worst > cap:
                over.append((r["offset"], r["id"], worst,
                             r["english"].rstrip()))
            continue
        # Deliberate layout: aligned label/value pairs and the separator
        # strings are spaced by hand, and re-wrapping would destroy them.
        if any("  " in l.lstrip(INDENT) or INDENT in l.lstrip(INDENT)
               for l in en.split("\n")):
            skipped += 1
            continue
        new = reflow(r["english"].strip(" \t"), args.width)
        # A locked term must sit inside one line.  The test is on the whole
        # wrapped string: if the term is still there verbatim, no break landed
        # inside it.  (An earlier version looked for a MASK anywhere on a line
        # and called every *other* term in a multi-term row broken.)
        joined = re.sub(r"\n[ \u3000]*", " ", en)
        flat = new.replace("\n", " ")
        for t in TERMS:
            if t in joined and t not in flat:
                split.append((r["offset"], r["id"], t))
        if new != r["english"]:
            r["english"] = new
            changed += 1

    if not args.check:
        with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    print("reflow: width=%d, rows rewrapped=%d, layout rows left alone=%d, "
          "single-line still too long=%d, terms broken=%d"
          % (args.width, changed, skipped, len(over), len(split)))
    for off, eid, worst, en in over[:10]:
        print("  %s id=%s %d chars: %s" % (off, eid, worst, en.replace("\n", " / ")))
    for off, eid, t in split[:10]:
        print("  %s id=%s broken term: %s" % (off, eid, t))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
