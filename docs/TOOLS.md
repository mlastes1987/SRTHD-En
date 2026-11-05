# Tool usage guide

This guide describes the tools actually included in the public repository.
Examples use PowerShell and run from the repository root. Replace example
drive paths with your own paths.

**Playing on PS3 / RPCS3?** Get the PS3 test build from
[Discord](https://discord.gg/DwR2jxj5b), extract the complete ZIP, close RPCS3,
and run **SRW English Patcher.exe**. See [Player installation](#player-installation).

**Playing on Vita / Vita3K?** Use the separately named Vita rePatch ZIP and
the [Vita installation guide](VITA_INSTALL.md). Full details of the native
Vita build and its current test coverage are in [VITA_PORT.md](VITA_PORT.md).

**Contributing to tools or builds?** Start with [Setup](#setup), then choose a
workflow below. A clean clone contains source and screenshots, not the
maintainer's working translation or a complete build kit.

## Contents

- [Player installation](#player-installation)
- [Setup](#setup)
- [What works in a clean clone](#what-works-in-a-clean-clone)
- [Local inputs and folders](#local-inputs-and-folders)
- [Extract and edit text](#extract-and-edit-text)
- [Build and validate the maintained translation](#build-and-validate-the-maintained-translation)
- [Review wrapping and text fit](#review-wrapping-and-text-fit)
- [Inspect and rebuild archives](#inspect-and-rebuild-archives)
- [Decode and re-encode textures](#decode-and-re-encode-textures)
- [Inspect layouts and fix the selection banner](#inspect-layouts-and-fix-the-selection-banner)
- [Inspect PowerPC code](#inspect-powerpc-code)
- [Package and test an installer](#package-and-test-an-installer)
- [Build and package the Vita port](#build-and-package-the-vita-port)
- [Tool reference](#tool-reference)
- [Troubleshooting](#troubleshooting)

## Player installation

1. Install your own Japanese **NPJB00514** game in RPCS3 and confirm it boots.
2. Download the current preview from [Discord](https://discord.gg/DwR2jxj5b).
3. Close RPCS3 and extract the complete ZIP. Keep the executable, manifest and
   `patches` folder together.
4. Launch **SRW English Patcher.exe**. Browse to `rpcs3.exe` and the installed
   game folder, usually `RPCS3\dev_hdd0\game\NPJB00514`.
5. Optionally use **Check files**, then click **Install English patch**.
6. Wait for the completion message and launch the game normally in RPCS3.

The patcher validates the original files, builds and verifies all replacements,
and preserves originals under `NPJB00514/.srwt1-english/backups`. Keep that
folder for future upgrades and restoration. To uninstall, close RPCS3 and use
**Restore originals**. It will refuse to overwrite unknown later edits.

For an encrypted original executable, the patcher uses your own RPCS3 to
decrypt a temporary copy. If that fails, use RPCS3's **File > Decrypt PS3
Binaries** on your original EBOOT, then select the resulting `EBOOT.elf` in
the patcher's optional field. The ELF must match the supported original;
an already translated ELF is not a valid original source.

The installer is currently a Windows preview. Python is not needed by players.
Other regions and revisions are not supported merely because their filenames
look similar; the file hashes must match.

## Setup

Use Python 3.10 or newer. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
$py = (Resolve-Path .venv\Scripts\python.exe).Path
```

The remaining examples use `& $py` so activation and PowerShell execution-policy
changes are unnecessary. Set `$py` again in a new shell. Pillow handles image
data; Capstone is used by the PowerPC inspection tool. Windows installer
compilation additionally uses the Windows .NET Framework C# compiler.

## What works in a clean clone

```powershell
& $py -m unittest discover -s tools -p "test_*.py"
& $py tools/panels.py selftest
& $py tools/panels.py find docs/screenshots/episode-briefing.png --top 5
& $py tools/fit_check.py probe docs/screenshots/episode-briefing.png --y0 20 --y1 180
```

The test suite currently discovers 12 tests. Without the maintainer's quote
report, two exhaustive quote-scan tests skip; the other ten run on synthetic
fixtures and emitted paging instructions. The panel self-test creates ignored
diagnostic PNGs under `work/tex_view`.

These tests do not boot the game or prove runtime compatibility. Installer
integration tests and full translation builds require the private local
inputs below.

## Local inputs and folders

Configure the original installation and, optionally, a development RPCS3:

```powershell
$env:SRW_ORIGINAL_DIR = "D:\Originals\NPJB00514"
$env:SRW_RPCS3_DIR = "D:\Emulators\RPCS3"
New-Item -ItemType Directory -Force work/text, work/tabata, build, shots | Out-Null
```

`SRW_ORIGINAL_DIR` points to the game root containing `PARAM.SFO` and `USRDIR`,
not to `USRDIR` itself. Its default is `local/original` inside the checkout.
`SRW_RPCS3_DIR` points to the folder containing `rpcs3.exe`; it is required only
by direct developer `--install` operations. These variables are read when a
tool starts and are not the player-facing patcher's configuration.

```text
local/original/                       # optional default original location
  PARAM.SFO
  USRDIR/EBOOT.BIN                    # original encrypted executable
  USRDIR/EBOOT.elf                    # original decrypted executable
  USRDIR/DATA/...                     # original CPK archives
work/text/text_banks.json             # reviewed maintained metadata
work/text/translation.csv             # maintained translation CSV
work/tabata/00000.bin                 # original extracted font atlas
build/KDATAPS3.translated.CPK          # approved accumulated UI archive
build/PIECE1STPS3.translated.CPK        # approved unit graphics archive
```

All those inputs and generated binaries are ignored by Git. Obtain maintained
translation data and approved art archives from the maintainer before trying
to reproduce a project release. Fresh extraction is useful for research, but
does not recreate the manual metadata repairs, stable translation IDs or art.

## Extract and edit text

Use a separate research directory so fresh extraction does not overwrite
reviewed build data:

```powershell
New-Item -ItemType Directory -Force work/research | Out-Null
$elf = Join-Path $env:SRW_ORIGINAL_DIR "USRDIR/EBOOT.elf"
& $py tools/srwtext.py extract $elf work/research/text.json
& $py tools/banks.py $elf work/research/text.json work/research/text_banks.json
& $py tools/csvtool.py export work/research/text_banks.json work/research/translation.csv
```

The CSV has `id`, `bank`, `index`, `offset`, `enc`, `japanese`, and `english`
columns. Edit the `english` column, preserving IDs, encodings, format tokens
such as `%s`/`%d`, and intentional layout where applicable. Use a CSV-aware
editor: dialogue fields can contain actual newlines and quoted text.

Import a research CSV into a separate output:

```powershell
& $py tools/csvtool.py apply work/research/text_banks.json work/research/translation.csv work/research/tr.json
& $py tools/srwtext.py import $elf work/research/tr.json build/research-EBOOT.elf
```

`banks.py` attaches pointer-table context; it is a historical research helper,
not a substitute for reviewed pointer metadata. It still considers both
file-offset and virtual-address patterns when grouping banks. The importer
uses trusted, aligned virtual-address references to avoid false aliases.
Do not replace the maintained `work/text/text_banks.json` or reuse fresh IDs
against the maintained CSV without reconciling them.

## Build and validate the maintained translation

With the maintained local inputs present:

```powershell
& $py tools/build.py --proportional
& $py tools/verify_build.py
```

The build performs CSV application, text import and relocation, proportional
font patching, and normal/multi-unit paging. It writes `build/EBOOT.BIN`; the
file is a decrypted ELF with the filename expected by this RPCS3 workflow.
The verifier checks translated bytes, mapped references and ELF load layout.
It is configured for the maintained CSV/metadata, not the research files in
the preceding example.

Always use `--proportional` for the current project build. A plain build does
not apply proportional spacing or the paging hooks. An optional local
`work/text/text_size.txt` activates the older descriptor-size experiment;
leave it absent for the normal workflow.

Optional developer installation, with RPCS3 closed:

```powershell
& $py tools/build.py --proportional --install
```

This copies EBOOT only, keeps a first-use `EBOOT.BIN.orig` backup, and refreshes
an existing `build/game/USRDIR/EBOOT.BIN` test copy. It does not install artwork
archives or create the player patcher's managed backups. `--test` together
with `--install` starts a brief headless boot smoke test; it is not a gameplay
test. The public repository does not contain the old `restore-original.bat`
mentioned in historical notes.

The lower-level steps are available for debugging:

```powershell
& $py tools/proportional_font.py --image build/EBOOT.BIN
& $py tools/battle_pages.py
```

Run them only on a suitable freshly built image, in that order. Normally
`build.py --proportional` already ran both. They guard their original
instructions and code space and will reject an already patched image; rebuild
from the original instead of patching it twice. `battle_pages.py` targets
`build/EBOOT.BIN` and has no alternate-image CLI option.

## Review wrapping and text fit

After a proportional build has generated glyph metrics:

```powershell
& $py tools/battle_dialogue.py
& $py tools/reflow.py --check
& $py tools/fit_check.py --spirits
```

- `battle_dialogue.py` scans the maintained battle-quote range and writes
  `work/text/battle_dialogue_report.json`, including proposed before/after
  layouts and page counts. Without `--apply`, it leaves the CSV unchanged.
- `reflow.py --check` reports proposed wrapping and fixed-label issues without
  changing the CSV. Its output is informational; a zero exit code alone does
  not mean it proposed no changes.
- `fit_check.py --spirits` uses measured glyph advances for spirit names.

To apply reviewed wrapping changes:

```powershell
Copy-Item work/text/translation.csv work/text/translation.before-layout.csv
& $py tools/battle_dialogue.py --apply
& $py tools/build.py --proportional
& $py tools/verify_build.py
```

`--apply` changes the maintained CSV. The battle tool also creates a backup
under a fixed historical filename if that backup does not already exist;
keep your own versioned backup for subsequent passes. Rebuilding applies the
new CSV and refreshes the metrics and binary hooks.

Running `reflow.py` without `--check` also rewrites the CSV. It uses measured
battle wrapping when metrics exist, and special rules for fixed labels and
other text. Review its proposed changes rather than applying a blanket width
to every screen. An optional `work/text/glossary.csv` supplies locked terms
for the general wrapper.

Other fit diagnostics:

```powershell
& $py tools/fit_check.py --list
& $py tools/fit_check.py --inferred
& $py tools/panels.py fit docs/screenshots/episode-briefing.png --band 20 180
```

`--list` and `--inferred` still need the maintained CSV. Most general fit
checks use historical fixed-cell estimates; they are not a complete
proportional-font or two-line-height validator. `--inferred` is a worklist,
not proof of clipping. Screenshot probes work without game files and are
most useful at the 1280x720 reference resolution. Keep screenshots at their
original scale when comparing pixel measurements.

## Inspect and rebuild archives

```powershell
$originalUi = Join-Path $env:SRW_ORIGINAL_DIR "USRDIR/DATA/KURODATA/KDATAPS3.CPK"
& $py tools/cpk.py list $originalUi
& $py tools/cpk.py extract $originalUi work/kuro
```

Extraction writes numbered payload files into the output directory. Use the
same procedure on TABATA's `TPACKPS3.CPK` to obtain the original font payload;
the measured-font code expects entry `00000.bin` at `work/tabata/00000.bin`.

Prepare a dedicated replacement directory with only the edited entries. For
example, `work/logo_replacement/00119.bin` replaces entry 119:

```powershell
$currentUi = "build/KDATAPS3.translated.CPK"
& $py tools/cpk.py build work/logo_replacement build/KDATAPS3.next.CPK --template $currentUi --only 119
```

Use the **current accumulated English archive** as the template when adding a
new art edit. Rebuilding against the Japanese original would discard the other
English artwork. The output must be a different file from the template.

The builder checks untouched payloads and round-trips replacements. Keep only
one file per numeric ID in the replacement directory: a name such as
`00119.original.bin` also matches entry 119 and can override the intended file.
`--only 119` limits IDs, not duplicate names for the same ID.

To compare two archives explicitly:

```powershell
& $py tools/cpk.py verify build/KDATAPS3.translated.CPK build/KDATAPS3.next.CPK
```

This compares all payloads. Intentional replacements are reported as
differences and produce a nonzero result; use the build command's untouched
entry verification to assess a targeted edit. The advanced `--recompress-all`
option changes storage for every payload and is unnecessary for a normal
one-entry UI edit.

Prefer the player patcher for installation. CPK's developer `--install`
requires `SRW_RPCS3_DIR` and infers its destination from a canonical template
name or a path under `USRDIR`; custom template names outside that structure
are not automatically mapped. It uses separate `.orig` backups.

## Decode and re-encode textures

```powershell
New-Item -ItemType Directory -Force work/previews | Out-Null
& $py tools/gcm_texture.py work/kuro/00119.bin work/previews/title-logo.png
```

The CLI decodes one extracted texture to PNG. It supports native ARGB formats
`0x85` (Morton-swizzled) and `0xA5` (linear), reading actual dimensions from the
header. It is not a universal decoder for all game assets. In particular,
the G8B8 font atlas is handled separately by `proportional_font.py`.

Encoding is exposed as a Python function, not a CLI command. A local script
can use it after artwork is edited at exactly the native dimensions:

```python
from pathlib import Path
import sys
from PIL import Image

sys.path.insert(0, "tools")
from gcm_texture import decode, encode

original = Path("work/kuro/00119.bin").read_bytes()
edited = Image.open("work/previews/title-logo-edited.png").convert("RGBA")
assert edited.size == decode(original).size
replacement = encode(original, edited)
assert decode(replacement).tobytes() == edited.tobytes()
out = Path("work/logo_replacement")
out.mkdir(parents=True, exist_ok=True)
(out / "00119.bin").write_bytes(replacement)
```

The encoder preserves the original header and trailing data. Preserve atlas
regions used by other sprites; a visually correct PNG alone does not prove
that the game's UV rectangles and animation layout will display it correctly.
The historical individual artwork-generation/packing scripts and approved
source images are not all included in this tools checkout.

## Inspect layouts and fix the selection banner

```powershell
& $py tools/ssad.py dump work/kuro/00032.bin --all
& $py tools/ssad.py list work/kuro
& $py tools/ssad.py trees work/kuro
```

SSAD files describe panes, UV rectangles, origins and animation properties;
they are not bitmap textures. These commands inspect them without editing.

For the known English team-header suffix problem:

```powershell
& $py tools/selection_banner.py build/KDATAPS3.translated.CPK work/team_header_replacement
& $py tools/cpk.py build work/team_header_replacement build/KDATAPS3.team-fixed.CPK --template build/KDATAPS3.translated.CPK --only 32
```

The helper prepares `00032.bin`, centers the complete team label and hides the
redundant shared suffix. It does not rebuild or install the archive by itself
and does not translate a Japanese atlas. Use it with the current English
archive. See [selection-banner notes](SELECTION_BANNERS.md).

## Inspect PowerPC code

`ppu.py` reads the original decrypted ELF selected by `SRW_ORIGINAL_DIR`:

```powershell
& $py tools/ppu.py dis 0x11B64C --len 0x80
& $py tools/ppu.py refs 0x47BE00 0x47F000
& $py tools/ppu.py find --imm 0x200 --imm 0x10
& $py tools/ppu.py window --around 0x11B64C
```

Addresses here are ELF **virtual addresses**, not file offsets. The `refs`
constant tracker and function-window display are research aids, not a full
symbolic execution engine or authoritative reference database. They do not
patch the executable.

`narrow_text.py` is a historical descriptor-float experiment, not the current
proportional-spacing solution. If researching it, start with its read-only
`--list` mode. Its `--size` mode changes a built image, and its `--restore`
path rebuilds through the older plain-build workflow; it is **not** the player
patcher's Restore originals function. Do not use it for normal releases.

## Package and test an installer

With maintained translation inputs and approved archives present:

```powershell
& $py tools/release_patch.py --version 0.1.2-preview
```

Use a new version label; this is an example, not a claim that 0.1.2 has been
released. Defaults are `build/KDATAPS3.translated.CPK` and
`build/PIECE1STPS3.translated.CPK`. For a different approved UI output:

```powershell
& $py tools/release_patch.py --version 0.1.2-preview --ui-archive build/KDATAPS3.team-fixed.CPK --unit-archive build/PIECE1STPS3.translated.CPK
```

Options include `--original GAME_ROOT`, `--output DIRECTORY`, `--ui-archive`
and `--unit-archive`. `--original` chooses original inputs for delta generation
and installer integration fixtures; the translation build still reads
`SRW_ORIGINAL_DIR`. Point both at the same supported original installation.

The builder rebuilds EBOOT, runs paging/importer/text checks, generates and
round-trips differences, compiles the Windows patcher, and runs installer
integration tests before creating the ZIP and checksum files. It consumes
finished art archives; it does not regenerate their artwork. If a build fails,
inspect the error before retrying; a partly prepared version folder may remain.

Explicit integration tests, using an existing release folder:

```powershell
& $py tools/test_release.py release/SRWT1-HD-English-0.1.1-preview
& $py tools/test_release_decrypt.py release/SRWT1-HD-English-0.1.1-preview "D:\Emulators\RPCS3\rpcs3.exe"
```

The first script checks actual C# install/restore behavior on temporary copies,
using a known decrypted ELF. An optional second positional argument selects
its original game root. The second tests automatic decryption with your RPCS3,
then installs and restores a temporary game copy. Close RPCS3 first. The
decryption test may update RPCS3's normal logs, but neither script patches the
live game. See [the release pipeline](PATCHING_PIPELINE.md) for recovery and
patch-format details.

## Build and package the Vita port

The Vita target is Japanese **PCSG00260 v1.00**. Its fixed-address ARM SELF,
native GXT textures, and runtime hooks use a separate pipeline from PS3.
Keep your original Vita installation and decrypted SELF under ignored `local/`
or `work/` directories. Export the original with Vita3K's **Other > Decrypt All
SELF** action; these tools do not supply game files or keys.

```powershell
& $py -m pip install -r requirements-vita.txt
& $py -m unittest discover -s tools -p 'test_vita*.py' -v
& $py tools/vita_build.py --game local/vita/original --self local/vita/eboot.original.self
& $py tools/vita_verify.py --source local/vita/eboot.original.self
& $py tools/vita_release.py --version 0.1.2-vita-preview
```

Provide an ARM-capable clang with ld.lld and llvm-objcopy on PATH or beside
clang. The build also needs the maintained `work/text/translation.csv` and
the approved PNG artwork listed in [VITA_PORT.md](VITA_PORT.md). A clean clone
includes the font measurements and reviewed Vita overrides; full translation
tables, original files, and finished artwork are still local maintainer inputs.

`vita_build.py` writes two staged files and a build manifest under `build/vita`,
plus detailed reports under `work/vita`. It enables proportional spacing,
attack/counter paging, moved strings, reviewed overrides, and the team-banner
fix by default. `--basic` reproduces the first in-place-only port. Optional
`--csv`, `--art`, `--work`, and `--output` arguments select local inputs/outputs.
The build does not modify your installed game.

The release command creates a clearly labeled **Vita-PCSG00260** rePatch
folder, ZIP, and checksum sidecar under ignored `release/`. The ZIP contains
full replacement files, a relative-path manifest, checksums, and player
instructions. See [VITA_INSTALL.md](VITA_INSTALL.md) for hardware overlay,
manual Vita3K replacement, and checked Python installation/restore commands.
The latest runtime changes and hardware compatibility still need playtesting.

For low-level texture work:

```powershell
& $py tools/vita_gxt.py decode work/vita/kuro/00118.bin work/vita/menu-preview.png
& $py tools/vita_gxt.py encode work/vita/kuro/00118.bin work/vita/replacements/00118.bin --image work/ui_edit/title_menu_faithful_native.png
```

Create the destination directory first. The GXT tool supports this game's
single-texture P8 layout, including palette alpha and linear/swizzled pixels;
unsupported formats are rejected. Keep each numbered archive replacement
in its own payload directory, with previews and backups elsewhere. `cpk.py`
now rejects duplicate numeric IDs instead of silently selecting a later file.

Runtime tests execute the emitted ARM code without an emulator or game data.
They skip with a stated reason if Unicorn or the LLVM tools are missing.
Static build verification additionally requires your maintained local build.
Both successful static checks and runtime instruction tests leave actual
in-game compatibility as a separate test step.

## Tool reference

| Tool | Role | Main inputs / effects |
|---|---|---|
| `project_paths.py` | Shared local path configuration | Reads environment variables; imported by other tools |
| `srwtext.py` | Extract/import executable text | ELF and metadata; writes JSON or a new executable |
| `banks.py` | Research pointer-bank grouping | ELF and extracted JSON; writes contextual JSON |
| `csvtool.py` | Export/apply translations | Metadata/CSV; writes CSV or translated JSON |
| `build.py` | Maintained EBOOT build | Reviewed local inputs; writes build outputs; optional install |
| `verify_build.py` | Check translated bytes and mapped references | Built ELF, original ELF, maintained CSV/metadata |
| `proportional_font.py` | Apply measured spacing and faction origins | Original font/ELF and fresh build; modifies image, writes metrics/specimen |
| `battle_dialogue.py` | Scan/wrap battle quotes | Metrics and CSV; writes report, optional CSV update |
| `battle_pages.py` | Apply both runtime paging paths | Fresh proportional build; modifies EBOOT, writes patch report |
| `reflow.py` | General/fixed-label wrapping review | Metadata/CSV, optional metrics/glossary; check or CSV rewrite |
| `fit_check.py` | Label-fit estimates and screenshot probing | Maintained data or a screenshot; reports diagnostics |
| `panels.py` | Measure screenshot panel geometry | Screenshots; reports rectangles, self-test writes diagnostic images |
| `cpk.py` | List/extract/build/compare archives | CPKs and numbered replacements; writes payloads or archives |
| `gcm_texture.py` | Native ARGB texture conversion | Extracted texture; CLI writes PNG, Python API encodes |
| `ssad.py` | Inspect pane/animation layouts | Extracted SSAD files; read-only display |
| `selection_banner.py` | Prepare known team-header correction | Current English UI CPK; writes entry 32 replacement |
| `ppu.py` | Disassemble and inspect original PPU code | Original decrypted ELF; read-only display |
| `narrow_text.py` | Legacy descriptor-size experiment | Built image; research-only, can modify/install |
| `release_patch.py` | Build a distributable preview | Maintained build inputs and original files; writes release ZIP/checksums |
| `test_text_import.py` | Synthetic importer regression tests | No game files required |
| `test_battle_pages.py` | Execute emitted paging instructions in tests | Synthetic fixtures; two additional scans need local quote report |
| `test_release.py` | C# integration tests | Release folder and local originals; uses disposable copies |
| `test_release_decrypt.py` | Automatic RPCS3 decryption/install/restore test | Release folder, original game, RPCS3; uses disposable copies |

### Vita tools and shared archive checks

| Tool | Role | Main inputs / effects |
|---|---|---|
| `vita_build.py` | Build and verify Vita text, ARM hooks, GXT UI and team banner | Original Vita data, decrypted SELF, maintained CSV/art; writes staged build and manifest |
| `vita_text.py` | Import Vita strings and optional overflow pool | Decrypted SELF/CSV; optional reviewed overrides and pointer/instruction rewrites |
| `vita_arm.py` | Thumb-2 branch/immediate and address-pair helpers | Imported by Vita tools; fixed PCSG00260 addresses |
| `vita_self.py` | Repack plain fixed-address Vita SELF segments | Preserves segment VAs and comment data; initializes the original BSS to zero |
| `vita_runtime.py` / `vita_runtime.s` | Assemble/apply ARM spacing, paging and faction-label hooks | LLVM tools, measured metrics, fresh staged SELF; writes runtime report |
| `vita_font_metrics.json` | Portable 95-glyph measurements | Numeric advances, bearings, glyph/SJIS indices and k/s adjustments; no bitmap |
| `vita_text_overrides.json` | Reviewed Vita source mappings | Exact original text/offset guards, translations, inline-record capacities and review notes |
| `vita_gxt.py` | Decode/encode native Vita P8 textures | GXT and PNG; palette quantization, alpha, layout preservation |
| `vita_verify.py` | Check every staged text/reference/hook change | Original SELF, staged SELF, generated reports and portable metrics |
| `vita_install.py` | Checked Vita3K install, upgrade and restoration | Build or extracted-package manifest and installed PCSG00260; original backups and hash checks |
| `vita_release.py` | Create private Vita rePatch folder/ZIP/checksums | Verified build manifest; only two supported replacement paths; no source publication |
| `test_vita_port.py` | Text and texture safety tests | Synthetic fixtures; no game data |
| `test_vita_self.py` | SELF packing and BSS tests | Synthetic segments; no game data |
| `test_vita_runtime.py` | Execute spacing/paging/faction ARM hooks | Included metrics, Unicorn and LLVM; no game data |
| `test_vita_install.py` | Install/upgrade/restore/preflight tests | Temporary synthetic game directories and manifests |
| `test_vita_release.py` | rePatch package structure and integrity tests | Temporary synthetic builds; private-path removal and hash refusal |
| `test_cpk_replacements.py` | Reject conflicting numeric replacement IDs | Temporary binary/preview fixtures |

## Troubleshooting

| Symptom | What to check |
|---|---|
| Missing `translation.csv` / `text_banks.json` | A clean clone lacks maintained working data. Obtain it before building; do not overwrite it with fresh extraction. |
| Missing original ELF | Check `SRW_ORIGINAL_DIR` and decrypt your original EBOOT with RPCS3. The tools do not supply a game executable. |
| Missing font atlas | Extract original TPACKPS3.CPK and place entry 0 at `work/tabata/00000.bin`. |
| Missing metrics/report | Run a maintained proportional build before battle layout diagnostics; run the quote scanner for its report. |
| Font/paging cave occupied or unexpected instruction | Rebuild from the supported original. Do not apply binary hooks twice. |
| Labels fit the width but still disappear | Check line count and presentation mode. A fixed one-line UI field and a two-line battle balloon have different constraints. |
| Japanese graphics return after an art edit | Check that the template was the current accumulated English CPK, not the pristine original. |
| Wrong replacement was packed | Use a dedicated directory and remove duplicate numeric IDs, including digit-prefixed backup names. |
| Patcher reports unsupported/modified files | Use a supported clean installation or managed originals; a matching title ID alone is insufficient. |
| Installer cannot restore a later edit | Preserve that edit separately; restoration deliberately refuses unknown modifications. |
| C# compiler not found | Build the Windows installer on Windows with the .NET Framework compiler available. Python-only research tools are separate. |

Report runtime issues with the build and RPCS3 versions, episode, unit/attack or
menu, reproduction steps, and screenshots. The [changelog](../CHANGELOG.md)
records current validation limits; [Discord](https://discord.gg/DwR2jxj5b)
hosts the current test build.

### Vita atlas region replacement

`vita_gxt.encode_region(original, image, box)` replaces a rectangular P8
region using the original 256-color palette. `image` must match the box size;
coordinates are left, top, right, bottom. Palette, metadata, and pixels outside
the region are preserved. The Vita builder uses it for the four reviewed menu-heading regions in
entry 133, listed in `vita_ui.MENU_REGIONS`. `use_region_palette=True` restricts
color matching to the original colors used in that region, keeping dark frame
colors out of cyan glows. The original palette and all outside pixels remain
unchanged. `vita_ui.team_banner` applies checked, named SSAD changes for a
centered, uniformly enlarged team label without the duplicated suffix.
