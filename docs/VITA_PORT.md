# Vita port development — PCSG00260

The initial Vita test build reuses the PS3 project's translation and approved
English artwork. This is an early development build, not a complete Vita release.

## Spacing and paging build — November 4, 2026

The latest test build contains **6,708 English string occurrences**: 6,492 fit
in place and 216 use added space after the original BSS. All 137 ambiguous
matches from the initial build are resolved. Another 37 source literals are
translated, including Vita save-data dialogs and fixed terrain-name records.
No unresolved source literals remain in the audited text regions. Textures
and untested game paths can still contain untranslated content.

The ARM font hooks use the same measured advances and left bearings as PS3,
including the one-pixel reductions for `k` and `s`. All 95 ASCII glyph bounds
match the Vita atlas exactly. Drawing and width measurement agree, centered
labels use measured width, and Allies/Enemies have a real 10-pixel gap in
either selection state.

Attack/counter dialogue supports two pages of two lines. Longer quotes split
at the second newline and remain visible for 120 native ticks per page. The
battle update holds while the pages are shown; fast-forward uses the native
delta. The renderer retains the second page if native code resets the quote
pointer. Short quotes retain their normal behavior. The quote audit covers
4,904 matched literal occurrences, including 28 two-page quotes, and checks
four-line, 800-pixel, and native-buffer byte limits.

The team-selection banner's two corrected SSAD properties are included. The
Vita and PS3 source panes were byte-identical. English title logo, title-menu
options, Objectives, and Level Up! graphics are retained. The bonus heading
now reads **Bonus Allocation**. Its confirmation uses two single-line rows with all six
stat values, removing inherited line breaks that overlapped the Yes/No controls.
Select Hero, Select Team, and Select Units are translated too. Only their
reviewed menu regions are changed, using each original region's palette colors.
The team label is centered at 160% uniform scale, with its shared suffix hidden.
Both colors of Attack/Counter and Quick Command/System are translated. The
Objectives text uses the native gray strip without an embedded second frame.
The map-save introduction stays on its own single native row.

Validation: **30 Vita tests pass**, including execution of the ARM hooks in
Unicorn. Two additional common archive tests check replacement-ID collisions.
The binary verifier checks all translations, 289 table-pointer updates,
51 instruction-address pairs, 12 branch hooks, the centered wrapper, original
BSS zero initialization, and the untouched SCE comment segment. Every changed
byte in the original loaded segments is accounted for. The UI CPK has six
verified replacements and 156 byte-identical untouched stored payloads.

This build is installed for Vita3K testing, with original backups preserved.
The new runtime behavior has not yet been checked in-game. Test long attacking
and counterattacking lines, multi-unit attacks, fast-forward, and returning to
the map. The traced Vita path has two global quote buffers; the PS3 four-buffer
multi-unit implementation cannot simply be copied. Multi-unit behavior is not
yet confirmed in-game.

## Initial build history

The first Vita build imported 6,319 in-place text occurrences and converted
the English logo, title-menu options, Objectives, and Level Up! graphics.
It left 137 ambiguous matches, 207 overlong translations, and eight strings
with interior references unresolved. The spacing/paging build above resolves
those cases and adds the audited Vita-specific source literals.

## Build

Run from the development workspace. Keep the original Vita files unchanged.
In Vita3K's game list, right-click PCSG00260 and select **Other → Decrypt All
SELF**. Use the exported `eboot.bin`, not the encrypted installed executable.
No license keys or decryption keys are included in these tools.

```powershell
python tools/vita_build.py --game local/vita/original --self local/vita/eboot.original.self
python -m unittest discover -s tools -p 'test_vita*.py' -v
python tools/vita_verify.py --source local/vita/eboot.original.self
```

The build needs `work/text/translation.csv` and these approved artwork files in
`work/ui_edit`: `title_menu_faithful_native.png`,
`super_robot_wars_title_texture_single_line.png`, `vita_menu_headers_133.png`
(512 × 992), `vita_battle_headers_135.png` (512 × 336), and
`vita_level_up_atlas_138.png` (512 × 512). The menu atlas imports only the four
regions listed in `tools/vita_ui.py`; unchanged pixels and palette bytes remain
identical. `--basic` instead uses the historical `level_up_atlas_138.png` and
omits these later banner changes.
Install the Python dependencies with `python -m pip install -r requirements-vita.txt`.
The runtime build also requires an ARM-capable clang, ld.lld, and llvm-objcopy
on PATH or beside clang. Runtime instruction tests require Unicorn; they skip
with a reason if Unicorn or the LLVM tools are unavailable. Synthetic text,
SELF, texture, installer, and packaging tests use no game files.

The font build uses the included `tools/vita_font_metrics.json`, measured from
PS3 and checked against all 95 matching Vita glyphs. Per-offset Vita source
overrides are in `tools/vita_text_overrides.json`. Outputs go to `build/vita`; texture previews and
the per-string report go to `work/vita`. `manifest.json` records both original
and output SHA-256 hashes. The build command does not install anything. It verifies text, pointer and
instruction updates, loaded-byte changes, BSS zero initialization, quote limits,
and archive preservation before writing its completed build manifest.
Spacing, paging, relocated text, reviewed Vita overrides, and the team-banner
fix are enabled by default. Use `--basic` to reproduce the initial build.

## Package a Vita rePatch playtest

After a verified build, run:

```powershell
python tools/vita_release.py --version 0.1.2-vita-preview
```

The output folder is `release/SRW-HD-Vita-PCSG00260-English-0.1.2-vita-preview-rePatch/`.
It contains `rePatch/PCSG00260/eboot.bin`,
`rePatch/PCSG00260/DATA/kurodata/KDataVITA.cpk`, player instructions,
an installable manifest with package-relative paths, and `SHA256SUMS.txt`.
The matching ZIP and `.zip.sha256` sidecar sit beside that folder.

The packager accepts only those two supported game paths, verifies the input
hashes, removes machine-specific paths from metadata, and tests every ZIP
entry after compression. It refuses an existing output folder or ZIP; choose
a new version or output directory. Hardware and runtime test status are
explicitly recorded. See the [Vita player guide](VITA_INSTALL.md).

These local playtest packages contain full modified replacement files. They
stay outside Git. The public repository contains the packager source and
documentation, not the payloads. No emulator, license, module, or plugin is
bundled. The PS3 Windows delta-patcher pipeline remains separate.

## Install and restore for testing

Close the game first. The Vita3K library window can stay open. Use the installed
`ux0/app/PCSG00260` directory as the target, rather than the source dump.

```powershell
python tools/vita_install.py --target C:/path/to/Vita3K/ux0/app/PCSG00260
python tools/vita_install.py --target C:/path/to/Vita3K/ux0/app/PCSG00260 --restore
```

The installer checks all files against the build manifest before writing,
backs up originals under `.srw-vita-english/original`, and verifies installed
hashes. It refuses unknown installed files or mismatched backups. These commands
are development tools; a public Vita installer has not been packaged. The
installer records the installed manifest to support later verified upgrades.
For migration from the initial installer, which did not record that state,
pass `--upgrade-from` with its reproduced build manifest. Upgrades keep the
original backups.

For the first runtime check, inspect the title logo, selected/unselected menu
options, Prelude, team selection, dialogue glyphs and spacing, Objectives, and
Level Up!. Report missing glyphs, overlaps, clipping, or a failure to boot before
continuing a longer playthrough.

## Format references

- [VitaSDK GXM definitions](https://github.com/vitasdk/vita-headers/blob/master/include/psp2/gxm.h)
- [Scarlet GXT structures](https://github.com/xdanieldzd/Scarlet/blob/master/Scarlet/Platform/Sony/PSVita.cs)
- [Vita3K SELF export](https://github.com/Vita3K/Vita3K/blob/master/vita3k/packages/src/sce_utils.cpp)
- [Vita3K ARM relocation handling](https://github.com/Vita3K/Vita3K/blob/master/vita3k/kernel/src/relocation.cpp)
