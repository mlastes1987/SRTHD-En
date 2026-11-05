# Battle quote overflow and Level Up! — 2026-11-04

User screenshot row 3739 contains the full translation, but the previous
20-character wrapper put it on three display lines; the battle balloon has
room for two. Its new layout is:

```
That attack won't work on this
　Super Alloy New Z body!
```

`tools/battle_dialogue.py --apply` scans 4,979 quote rows in the physical
UTF-8 quote range 0x422410..0x46f350. It uses the installed proportional font
metrics at 38px, an 800px advance budget including quote/indent space, and
preserves all words. 4,607 rows were rewrapped; 28 still need two pages.
`work/text/battle_dialogue_report.json` records every before/after layout.
`tools/reflow.py` now uses this wrapper for the quote range as well.

`tools/battle_pages.py` patches the normal attack/counterattack battle state
machine. After the native copies into battle+0x3e8 and +0x461 (121-byte
buffers), it replaces the second newline with NUL and records the next-page
offset and timer in unused bytes 104/105. The scan verifies quoted UTF-8
strings fit before that reserved tail. The text itself contains no new control
codes, and other string consumers retain ordinary newline handling.

The state update holds for 120 native ticks per page, keeping the existing
draw/return path active; the timer follows the native 1x/2x speed setting.
The draw hook restores the second-page pointer if a native delay state resets
it. Single-page quotes take the original state update path. Three guarded
hooks originally used 432 bytes at VA 0x4CDD00, after the font code and before its metric
table. `build.py --proportional` reapplies the font and pagination patches.

This is an initial runtime patch for user testing in RPCS3. Static checks and
emulated instruction tests pass; actual battle timing/rendering is not yet
confirmed. Multi-unit attack paging is now included by the follow-up below.
No claim is made that every game presentation has been tested.

Validation:

- `python -m unittest discover -s tools -p test_battle_pages.py`: four tests
  execute emitted PPC instructions, including all 4,979 quote strings, both
  buffers, page boundaries, pointer resets, reuse, fast-forward, and writes
  confined to the intended fields.
- `python -m unittest discover -s tools -p test_text_import.py`: four pass.
- `python tools/verify_build.py`: 6,898 translations, zero bad/dangling/ambiguous
  references.

The level-up label is artwork in KDATAPS3.CPK entry 138. The user selected
**Level Up!**. Built-in imagegen generated matching dark lettering with a
yellow outline, saved as `work/ui_edit/level_up_english_source.png`; the prompt
is `work/ui_edit/level_up_prompt.txt`. `work/edit_138_level_up.py` clears the
two Japanese sprite regions, fits and splits the English at their native
seam, and preserves every other atlas pixel, header, geometry and byte length.
In particular, the approved Objectives banner remains intact.

`build/KDATAPS3.translated.CPK` rebuilds only entry 138 using the current installed
archive. Its verifier confirms 161 untouched payloads identical and entry 138
round-trips. Native preview: `work/ui_edit/level_up_english_native.png`.

Rollback snapshots:

- `build/EBOOT.before_battle_pages_2026-11-04.BIN`
- `build/KDATAPS3.before_level_up_2026-11-04.CPK`
- `work/text/translation.csv.before_battle_pages_2026-11-04`

## Multi-unit paging follow-up — 2026-11-04

The multi-unit path uses the global object loaded from TOC -0x3A28, an active
quote pointer at +0x150, and four 121-byte buffers at +0x154, +0x1CD, +0x246,
and +0x2BF. All four are filled by native quote copies before VA 0x11ECD8;
the initialization hook splits and resets all four independently.

The multi-unit update hook at VA 0x11FB80 uses its native +0x14 tick increment
and the same 120 ticks per page. While holding the state it explicitly calls
the native renderer at 0x11F058, then returns through the running-sequence
path at 0x11FBE4 with r30=0. This differs from the normal battle path, which
already renders at its common update exit. The renderer hook restores the
selected page after native pointer assignments, preserves LR across the
shared lookup worker, and replays the original stack update instruction.

Normal and multi-unit hooks now share splitting and buffer lookup workers.
The full patch has six guarded hooks and occupies 512 bytes at 0x4CDD00,
ending at 0x4CDF00, below the proportional-font metric table at 0x4CE000.

Eight instruction-level paging tests pass, covering every scanned quote in
each of the four multi-unit buffers, normal/fast-forward timing, explicit
render calls on every held frame, independent speakers, pointer resets,
buffer reuse, confined writes, LR preservation and the native stack prologue.
The four text-import tests and all 6,898 translation/reference checks also
pass. Runtime timing and appearance still require RPCS3 testing.

The installed build changes EBOOT only; the Level Up! texture archive stays
as installed by the previous step. Pre-follow-up executable backup:
`build/EBOOT.before_multi_pages_2026-11-04.BIN`.
