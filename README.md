# Super Robot Wars HD — English Translation

An English fan translation of **Super Robot Taisen HD / Super Robot Wars HD**,
with a PS3 preview for **NPJB00514 / RPCS3** and an early Vita port for
**PCSG00260**.

**We're open for testing! Join [our Discord server](https://discord.gg/DwR2jxj5b)
for test builds and feedback.**

| Platform | Current preview | Playtest package |
|---|---|---|
| PS3 — NPJB00514 | **0.1.1-preview** | Windows RPCS3 patcher; `SRWT1-HD-English-0.1.1-preview.zip` |
| Vita — PCSG00260 | **0.1.2-vita-preview** | Replacement files in a `rePatch/PCSG00260` folder; filename begins `SRW-HD-Vita-PCSG00260-English-` and ends `-rePatch.zip` |

The Vita build has automated text, spacing, paging, and packaging checks. Its
latest runtime changes still need in-game confirmation, especially multi-unit
attacks. The rePatch layout is supplied for hardware playtesting; hardware
compatibility has not been verified.

![Current PS3 English title screen with the faithful menu artwork and Continue highlighted](docs/screenshots/title-screen.png)

## What's been done

The PS3 translation includes **6,898 validated entries**, English story and
battle dialogue, menus, descriptions, and unit information. It also includes:

- A single-line **Super Robot Wars** logo and faithful English title-menu artwork.
- Measured proportional spacing, episode-title corrections, and menu overlap fixes.
- English **Objectives** and **Level Up!** graphics.
- Pixel-aware battle wrapping and second pages, including PS3 multi-unit attacks.
- A Windows patcher with file checks, backups, upgrades, and restoration.

The Vita port reuses the translation and artwork, with **6,708 translated string
occurrences**, including 216 moved to added space rather than shortened. It adds:

- Native ARM spacing hooks matching the PS3's 95 measured ASCII glyphs, including tighter `k` and `s`.
- Two-page attack/counter dialogue support and native fast-forward timing.
- Reviewed Vita save-data messages, terrain names, and ambiguous shared labels.
- Allies/Enemies spacing and the team-selection banner correction.
- Faithful **Select Hero**, **Select Team**, **Select Units**, and **Bonus Allocation** headings.
- English Attack/Counter battle banners and corrected Objectives placement.
- Compact bonus confirmation rows preserving all six stat values, plus a corrected map-save prompt.
- Native Vita GXT artwork conversion, build verification, checked Vita3K installation, and rePatch packaging tools.

These are **work-in-progress test builds**. Passing checks does not mean every
scene, menu, attack, or hardware configuration has been verified in-game.

## Screenshots

### Translated prelude

![English prelude narration over Gilgilgan and the super robots](docs/screenshots/prelude.png)

### Episode title and mission briefing

![Episode 1 title card and English mission briefing](docs/screenshots/episode-briefing.png)

All screenshots shown here are **PS3 / RPCS3 captures**. The title image is the
latest approved title-menu capture from November 4, 2026, showing the faithful
English selections. [Capture details](docs/screenshots/README.md) record their
dates. Vita screenshots will be added after clean in-game captures are verified.

## Join the test

### PS3 / RPCS3

1. Install your own Japanese **NPJB00514** game and confirm it boots in RPCS3.
2. Get the PS3 test build through [Discord](https://discord.gg/DwR2jxj5b).
3. Close RPCS3, extract the complete patcher package, and run **SRW English Patcher.exe**.
4. Select RPCS3 and the installed game folder, then install the English patch.

Keep the patcher's backups for restoration and upgrades. PS3 players do not
need Python. See the [PS3 installation guide](docs/TOOLS.md#player-installation).

### Vita / PCSG00260

Use the **Vita rePatch ZIP** for this platform. It contains a standard
`rePatch/PCSG00260` tree, installation instructions, and checksums.

- **Vita hardware:** follow the [Vita playtest guide](docs/VITA_INSTALL.md) to place the overlay under `ux0:rePatch/PCSG00260` with a working rePatch plugin.
- **Vita3K:** back up the two original files, then copy the contents of `rePatch/PCSG00260` into the installed `ux0/app/PCSG00260` folder. The guide also covers optional checked installation with Python.

Please test long attack/counter quotes, multi-unit attacks, page transitions,
fast-forward, save/load dialogs, menu spacing, and return to the map. Include
the **platform, title ID, build version, emulator version or Vita firmware,
episode, unit/attack or menu, and reproduction steps** in reports. Screenshots
help with missing, cut-off, or overlapping text.

Feedback is welcome on [Discord](https://discord.gg/DwR2jxj5b) or through
[GitHub Issues](https://github.com/mlastes1987/SRTHD-En/issues/new?template=bug_report.yml).

## What's in this repository

| Location | Contents |
|---|---|
| [`tools/`](tools) | PS3 and Vita text, spacing, paging, archive/texture, validation, installation, and packaging tools |
| [`installer/`](installer) | PS3 Windows patcher source and integration-test harness |
| [`docs/`](docs) | Tool instructions, development notes, platform guides, and screenshots |

This is a **source/tools repository**. Game files, patched executables and
archives, release ZIPs, license keys, saves, and emulators are excluded from Git.
Vita glyph measurements and reviewed source-text overrides are included; full
working translation tables and approved artwork remain maintainer-local inputs.
A clean clone is not a complete translation build workspace.

Start with the [tool usage guide](docs/TOOLS.md), [development setup](docs/DEVELOPMENT.md),
[Vita developer guide](docs/VITA_PORT.md), [Vita player guide](docs/VITA_INSTALL.md),
or [PS3 release pipeline](docs/PATCHING_PIPELINE.md). The
[detailed changelog](CHANGELOG.md) records changes and remaining test coverage.

## Platform and license

Supported development targets are Japanese **PS3 NPJB00514** and **Vita
PCSG00260 v1.00**. Other regions and revisions have not been verified. The
PS3 installer is an unsigned Windows preview; the Vita rePatch ZIP is an
experimental playtest package.

Project code is distributed under the existing [MIT license](LICENSE). Game
artwork and screenshots belong to their respective rights holders and are not
covered by the code license. This is an unofficial fan project, unaffiliated
with the original developers or publishers.
