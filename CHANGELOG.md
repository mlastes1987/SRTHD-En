# Changelog

This records changes included in the current translation previews and the
public tooling. Earlier development was not tagged as a sequence of public
releases, so it is summarized under the first packaged preview rather than
assigned invented version numbers.

Current previews: **PS3 0.1.1-preview** (NPJB00514 / RPCS3) and
**Vita 0.1.1-vita-preview** (PCSG00260). Test builds and feedback are coordinated
through [Discord](https://discord.gg/DwR2jxj5b). Both remain work in progress;
the latest Vita runtime changes and hardware rePatch compatibility need
in-game confirmation.

## Vita 0.1.1-vita-preview — 2026-11-04

- Replaced the Japanese bonus-allocation heading with **Bonus**, retaining
  bold italic white lettering and a cyan glow in the native 512 × 64 atlas row.
- Added region-only P8 encoding using the existing palette. All other rows,
  palette bytes, and atlas metadata remain unchanged.
- Removed inherited multiline formatting from the bonus confirmation's two
  fixed native text rows. Compact Atk/Def/Spd labels keep all six `%d` values
  on two single-line rows, clear of the Yes/No options. Width checks cover
  two-digit values at the native 38-pixel font size.
- Verified five CPK replacements and 157 unchanged stored payloads. All 27
  Vita tests pass, including new region-preservation and confirmation tests.
- Rebuilt the separate Vita rePatch playtest ZIP. These two screen fixes
  still need in-game visual confirmation; hardware remains unverified.

## Vita 0.1.0-vita-preview — 2026-11-04

### Translation and overflow handling

- Imported 6,708 translated string occurrences: 6,492 in place and 216 in an
  added pool after the original BSS. Longer text is preserved rather than
  shortened to the Japanese byte length.
- Updated 289 table pointers and 51 Thumb MOVW/MOVT address pairs. Preserved
  segment virtual addresses and the original BSS's zero initialization.
- Resolved the first build's 137 ambiguous source matches using neighboring
  literal context and reviewed per-offset overrides. Added 37 audited source
  literals, including Vita-specific save/load messages and fixed terrain names.
- Added exact source-byte checks, per-entry reports, supported inline-record
  capacities, and checks for merged literals/interior references.

### Native spacing, layout, and paging

- Ported proportional spacing to native ARM hooks. All 95 ASCII glyph bounds
  match the Vita font atlas; advances/bearings match the PS3 measurements,
  including the one-pixel reductions for `k` and `s`.
- Synchronized drawing and width measurement and replaced the centered label's
  character-count shortcut with measured width.
- Added explicit Allies/Enemies origins with a 10-pixel gap in both selection
  states.
- Added two-page attack/counter dialogue support, splitting after the second
  newline, holding battle progression for 120 native ticks per page, and using
  the native delta for fast-forward. Rendering retains the second page if the
  normal path resets the quote pointer.
- Audited 4,904 matched quote occurrences, including 28 requiring two pages,
  against four-line, 800-pixel and native buffer byte limits.

### Graphics and packages

- Converted the approved single-line English logo, faithful title selections,
  Objectives, and Level Up! atlas to native Vita GXT P8, preserving palette
  transparency and linear/swizzled layout.
- Ported the two team-banner SSAD property corrections after confirming the
  PS3 and Vita originals were byte-identical.
- Verified four CPK replacements and 158 unchanged stored payloads.
- Added checked Vita3K installation/upgrades/restoration with original backups,
  all-file preflight, package-relative paths, and installed-build records.
- Added a separately named **Vita-PCSG00260 rePatch** folder/ZIP, player
  instructions, sanitized manifest, extracted-file checksums, and ZIP checksum.
  The package includes only the two supported modified game files.

### Public tools and verification

- Added native Vita text/SELF/Thumb/GXT/runtime/build/verification/installation/
  packaging tools, ARM assembly, portable glyph measurements, reviewed text
  overrides, and 25 synthetic/ARM/installer/package tests.
- Added a guard against duplicate numeric CPK replacement IDs, with two
  regression tests. A preview PNG or backup can no longer silently replace a
  binary payload with the same ID.
- Updated the README, platform-specific install/build guides, tool reference,
  developer setup, issue form, and CI dependency setup for both platforms.
- Kept the public PS3 tools' portable path configuration and existing installer
  source. Playtest payloads, game files, license data, modules and plugins remain
  excluded from Git.
- Verified every changed byte in the original loaded segments, all translated
  bytes and rewritten references, 12 branch hooks plus the centered wrapper,
  BSS zero initialization, and the unchanged SCE comment segment.

### Remaining playtesting

The new Vita spacing and paging changes have passed isolated ARM instruction
tests and static build checks, not a complete in-game playthrough. Test long
attack/counter quotes, multi-unit attacks, fast-forward, save/load dialogs,
map returns, and selection layouts. The traced Vita path uses two global
quote buffers; PS3's four-buffer multi-unit implementation is not a Vita
compatibility guarantee. Hardware rePatch execution is unverified.

All displayed public screenshots are still approved PS3/RPCS3 captures. This
Vita preview does not change the PS3 game-patch version.

## Unreleased — public documentation

### Added

- A [complete tool usage guide](docs/TOOLS.md), covering player installation,
  Python setup, local inputs, text extraction/editing, maintained builds,
  wrapping diagnostics, archive/texture/layout work, code inspection,
  packaging, testing, and troubleshooting.
- A command and input/output reference for every Python tool in the public
  repository, including research-only and legacy tools.
- This detailed changelog, separating shipped preview changes, earlier
  translation work, static/integration validation, and pending runtime checks.

### Clarified

- A clean clone is a tools checkout. Working translation tables, reviewed
  metadata, extracted assets and approved translated archives remain local
  maintainer inputs.
- Some commands write reports even in scan-only mode; CSV rewrites and direct
  developer install operations are identified explicitly.
- General fixed-cell estimates are not a replacement for measured
  proportional-font checks or in-game visual testing.

These documentation changes do not create a new game-patch version.

## 0.1.1-preview — 2026-11-04

### Fixed: team-selection banner assembly

- Found that the original team header combines a team-specific sprite and a
  shared Japanese selection suffix sampled from the hero-label region.
- The English atlas already contains the complete phrase **Select Team**.
  Drawing the shared suffix added the tail of **Select Hero**, producing the
  visible combined/overlapping label.
- Changed KDATAPS3.CPK entry **32** to hide that redundant suffix pane and
  center the complete team label at x=271 instead of the old partial-label
  origin x=219.
- Preserved pane geometry, atlas rectangles and the other 161 archive entries.
- Inspected the separate hero-selector layout in entry **33**; it uses one
  complete header sprite and has no separate shared suffix pane. This change
  does not claim a separately reproduced hero-screen defect was fixed.
- Added `selection_banner.py` so the known team-header correction can be
  prepared from a local current English archive.

### Updated test package

- Built a new **0.1.1-preview** Windows installer containing the corrected UI
  archive and the existing proportional text and normal/multi-unit paging.
- Verified that its three reconstructed target files match the installed
  development build.
- Passed install, repeat-install, upgrade, failure rollback, recovery and
  restoration checks on disposable game copies.

### Runtime status

- The banner correction was installed for testing and verified at the archive
  and layout-data level. A fresh in-game check of team and hero selection is
  still requested.
- Multi-unit paging and other presentation changes carried forward from the
  preceding preview still need broader gameplay testing.

## 0.1.0-preview — 2026-11-04

The first packaged Windows patcher preview combined the translation work
below with the new dialogue paging and installer pipeline. Internal packaging
revisions were development candidates, not separate documented public game
releases.

### Battle dialogue: wrapping and missing lines

- Investigated an attack quote that displayed only “That attack won't / work
  on this Super” while its remaining translation existed in the CSV.
- Identified the presentation mismatch: the old fixed character-count wrapper
  produced three or more lines for a battle balloon that displays two.
- Added a glyph-width-based scan over **4,979 battle quotes** using measured
  advances at the battle font size, with room for the quote/continuation
  indent inside an 800-pixel budget.
- Rewrapped **4,607 quotes**, preserving their words, rather than shortening
  every overlong sentence. The reported quote now uses:

  ```text
  That attack won't work on this
  　Super Alloy New Z body!
  ```

- Identified **28 quotes** that still need a second page after rewrapping.
- Added a before/after quote report and checks for native buffer capacity and
  visible line count.
- Updated the general reflow tool to retain measured battle wrapping when
  glyph metrics are available, so later text passes do not restore the old
  character-count layout in this range.

### Normal battle paging

- Added runtime support for a second page in the normal attack/counterattack
  presentation's two native 121-byte quote buffers.
- Split after the second display line without adding new control codes to
  the translation strings. Stored a next-page offset and timer in unused
  buffer-tail bytes.
- Hold the battle state for **120 native ticks per page**, keeping the native
  render path active. Timing follows the native normal/fast-forward increment.
- Restore the selected page when a native delay state reassigns the first-page
  pointer. Single-page quotes retain the normal state-advance path.

### Multi-unit battle paging

- Extended paging to the separate multi-unit path and all **four** of its
  quote buffers, with independent page offsets and timers.
- Reset all four buffers when the native quote copies complete, including
  after buffer reuse for a later sequence.
- Added an explicit native draw call while holding a multi-unit state, because
  that path normally renders inside its individual update states.
- Preserved the renderer's return address and native stack-update behavior.
- Shared splitting/lookup workers with the normal path. The combined paging
  patch uses six guarded hooks and 512 bytes of code, below the font metric
  table.
- Integrated both paths into `build.py --proportional`.

### Level-up graphic

- Confirmed that the untranslated level-up message was texture artwork rather
  than a missing executable string.
- Replaced it with **Level Up!**, following the requested shorter wording and
  the original dark lettering/yellow outline treatment.
- Packed the label across its two native sprite regions in KDATAPS3.CPK entry
  **138**, removing remaining Japanese edge pixels while preserving other
  atlas regions, including the existing **Objectives** banner.

### Windows installer and release pipeline

- Audited the original and translated USRDIR trees. The release modifies
  `EBOOT.BIN`, `DATA/KURODATA/KDATAPS3.CPK`, and
  `DATA/PIECE/PIECE1STPS3.CPK`; the other audited files matched.
- Added a Windows Forms patcher with Browse, Check files, Install English
  patch and Restore originals controls. Players do not need Python.
- Support selection of an RPCS3 root, dev_hdd0/game hierarchy, game root or
  USRDIR, with PARAM.SFO title-ID validation and exact file-hash checks.
- Reconstruct translated files from compressed copy/literal binary
  differences rather than distributing complete game executables/archives.
- For encrypted EBOOT, invoke the player's own RPCS3 `--decrypt` on a temporary
  copy, then verify the original ELF. Also support a manually decrypted
  original ELF through the optional field.
- Stage and verify all replacements before committing changes. Back up
  originals once, use same-volume atomic replacements, and roll back completed
  writes if a later write fails.
- Record installed and previous hashes for managed upgrades and interrupted
  installation recovery. Make repeat installation idempotent.
- Validate backups before restoration and refuse to erase unknown later
  modifications. Keep original backups after restoring.
- Refuse installation/restoration while RPCS3 is running. Preserve saved
  games, licenses and emulator settings outside the replacement list.
- Generate per-file checksums, a release ZIP and a ZIP SHA-256 sidecar.
- Carry forward the existing modified unit-graphics archive as an approved
  input; the installer does not itself create new unit graphics.

### Validation

- Eight paging instruction tests pass in the maintained workspace, including
  both normal buffers, all four multi-unit buffers, every scanned quote,
  speaker changes, pointer resets, buffer reuse, fast-forward, return-address
  preservation, stack setup and confined writes.
- Four importer regression tests pass.
- The maintained executable validator reports **6,898 translations**:
  **6,742 in place**, **156 relocated**, with zero bad, dangling or ambiguous
  references in the validated build.
- Installer integration tests cover wrong-source and damaged-payload
  rejection, exact target reconstruction, rollback/retry, repeat installation,
  upgrades, recovery, backup preservation, restoration refusal after later
  edits, complete restoration and path confinement.
- Automatic RPCS3 decryption, installation and byte-for-byte restoration
  passed on a temporary original game copy.
- Inspected the real installer window and missing-folder validation. The
  executable is unsigned; these tests are not a code-signing or compatibility
  certification.

## Earlier development included in the previews

These changes predate the first packaged installer. They are listed by
feature rather than assigned unrecorded release tags.

### Translation coverage and missing-text fixes

- Maintained English story, battle, menu, description and unit-information
  text, with a reviewed table of 6,898 translated entries.
- Repaired missing Episode 2 title display data: **Battle at the Lake** was
  translated, but its relocated text had been placed in writable runtime
  memory that could overwrite it.
- Moved overflow strings into a separate read-only ELF load segment beyond
  the original allocations, preserving Sony area flags and leaving the
  original writable segment unchanged.
- Replaced broad byte-pattern reference patching with trusted aligned
  virtual-address references, preventing file-offset aliases and unrelated
  binary values from being redirected.
- Limited in-place string capacity at nonzero neighboring data after the
  original terminator, protecting unextracted strings and other data.
- Extended extraction to accept single Japanese characters, and added missed
  short labels including **Res.**, **Air**, **Land**, **Sea** and **Space**.
- Repaired preview-title templates so a title such as **Twilight River** is
  quoted instead of displayed with the literal “time:” suffix.
- Refined briefing/preview wording, including the Forest warning about both
  woods and water reducing weapon power and accuracy.
- Preserved format specifiers and meaningful leading/trailing newlines during
  general reflow, and added exceptions for fields that draw one bank row per
  display line rather than wrapping an entire string.
- Checked all 26 episode-title table entries for nonempty single-line English;
  this was a static table check, not a complete visual pass through every episode.

### Proportional spacing and narrow menu labels

- Identified the actual original font atlas as a 4096x1120 two-channel G8B8
  texture, replacing the earlier incorrect universal-width interpretation.
- Measured 95 printable ASCII glyphs from the game font and patched drawing,
  measurement and centered-text paths to use their advances/bearings.
- Adjusted lowercase **k** and **s** advances by one additional display pixel.
- Replaced space-padding alignment in the pause menu's **Allies / Enemies**
  labels with explicit measured origins for both selected/inactive font sizes,
  retaining a ten-pixel gap and the existing selection colors.
- Shortened the spirit-command list label **Resonance** to **Reson.** so the
  name fits before its SP cost; measured all 22 spirit names against that field.
- Added font metrics/specimens and fit diagnostics. Historical fixed-pitch
  experiments remain research tools and are not the current spacing solution.

### English artwork and native texture handling

- Located the live logo at KDATAPS3.CPK entry **119**, rather than the
  background or thumbnail previously suspected.
- Added the gold/orange, dark-backed, silver-outlined **SUPER ROBOT WARS**
  wordmark, then revised it to one line after feedback.
- Replaced title-menu artwork at entry **118** with English **Start**, **Load**,
  **Continue**, **Episode 1**, **Episode 2**, **Network** and **Download** states.
  Selected options follow the original white/cyan glow and teal styling;
  inactive options use outlined silver-blue lettering and blue panels.
- Added the English **Objectives** banner in entry **138** while preserving
  the remaining atlas content.
- Added a native ARGB codec that reads header dimensions and distinguishes
  Morton-swizzled `0x85` from linear `0xA5` textures, instead of treating all
  textures as 512 pixels wide.
- Verified byte-identical no-edit texture round-trips and exact encoding of
  prepared replacements. Targeted CPK rebuilds validate untouched payloads
  and round-trip changed entries to preserve accumulated artwork changes.

### Public repository and testing materials

- Added the public toolchain and installer source under the existing MIT code
  license, with configurable local original/RPCS3 paths instead of developer
  account paths.
- Added a front-facing README showing the latest faithful title-menu capture,
  clean prelude and Episode 1 briefing screenshots, plus capture provenance.
- Added development/release notes, an issue template and Windows CI checks
  for portable tests and installer compilation.
- Pointed players to Discord for current test builds while excluding game
  files, license keys, working translation data and release payloads from Git.

## Known limits and current testing requests

- No full-game playthrough or exhaustive visual review is claimed. Report
  remaining missing text, overlaps, awkward wording, untranslated graphics,
  crashes and progression problems with reproduction details.
- Runtime page timing and visibility need confirmation across attacks,
  counterattacks and multi-unit sequences at normal and fast-forward speed.
- Team/hero selection should be checked again after the 0.1.1 banner correction.
- Several menus have static or measured fit checks, but passing those checks
  does not prove every font size or animation state displays correctly.
- Current support is the matching PS3 NPJB00514 files in RPCS3. No other-region,
  other-revision, real-hardware or Vita compatibility is asserted.
- A clean public clone skips two data-dependent paging scans without the
  maintainer's quote report. Full builds and installer integration tests need
  local original game files and maintained build inputs.
- The preview installer is unsigned. Checksums detect corruption and wrong
  versions; they do not authenticate a publisher.

See [tool instructions](docs/TOOLS.md), [battle implementation notes](docs/BATTLE_DIALOGUE.md),
[selection-banner notes](docs/SELECTION_BANNERS.md), and [the release pipeline](docs/PATCHING_PIPELINE.md).
