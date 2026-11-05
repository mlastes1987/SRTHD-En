# Working with the tools

For complete command examples and a reference for every script, see the
[tool usage guide](TOOLS.md). The [changelog](../CHANGELOG.md) explains what
each preview changed and which runtime checks are still pending.

The public repository is a tools/source checkout. It deliberately excludes
original game files, extracted textures, working translation tables, final
translated archives, and release payloads. Get the current playable test
build through [Discord](https://discord.gg/DwR2jxj5b).

## Basic setup and tests

Use Python 3.10 or newer. The Windows patcher compiler is the .NET Framework
C# compiler supplied with Windows; installer compilation is Windows-only.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tools -p "test_*.py"
```

The synthetic importer and paging-instruction tests work without game data.
The exhaustive quote-scan tests skip if the maintainer's generated dialogue
report is absent. Release/decryption integration tests are explicit scripts
that require local original files; they are not run on import.

## Local inputs

Put your original installation under `local/original/`, or point the tools at
it with an environment variable. The folder must contain `PARAM.SFO` and
`USRDIR`, including your original decrypted `EBOOT.elf` when building text.

```powershell
$env:SRW_ORIGINAL_DIR = "D:\My original NPJB00514"
$env:SRW_RPCS3_DIR = "D:\Emulators\RPCS3"
```

`SRW_RPCS3_DIR` is needed only for optional direct developer installation;
building a patch or running the portable tests does not require it. The
player-facing patcher uses its own Browse fields instead of these variables.

The maintained build needs these ignored working inputs:

| Input | Purpose |
|---|---|
| `work/text/text_banks.json` | Reviewed text offsets, slot sizes, encodings and trusted references |
| `work/text/translation.csv` | Current maintained English translations |
| `work/tabata/00000.bin` | Original extracted font texture for measured advances |
| `build/KDATAPS3.translated.CPK` | Approved accumulated English UI artwork archive |
| `build/PIECE1STPS3.translated.CPK` | Approved unit graphics archive |

Obtain the maintained working data from the project maintainer if you are
contributing to builds. Extracting fresh text alone does not reproduce the
reviewed translation metadata or the accumulated artwork.

Useful standalone tools:

```powershell
New-Item -ItemType Directory -Force work/text | Out-Null
python tools/srwtext.py extract PATH_TO_EBOOT.elf work/text/text.json
python tools/cpk.py list PATH_TO_ARCHIVE.CPK
python tools/gcm_texture.py PATH_TO_EXTRACTED_TEXTURE.bin preview.png
python tools/ssad.py dump PATH_TO_EXTRACTED_LAYOUT.bin --all
```

For a maintained workspace, build with:

```powershell
python tools/build.py --proportional
python tools/verify_build.py
```

`--proportional` also applies normal and multi-unit dialogue paging. The
optional `--install` copies EBOOT into the configured RPCS3 installation and
requires that `SRW_RPCS3_DIR` is set. Close RPCS3 first.

The release builder reads the approved archive inputs above, runs checks and
installer integration tests, then emits a patch-only ZIP under `release/`.
See [PATCHING_PIPELINE.md](PATCHING_PIPELINE.md).

## Vita development

The Vita tools target **PCSG00260 v1.00**. Install their Python dependencies
with `python -m pip install -r requirements-vita.txt`. Runtime assembly also
needs ARM-capable clang, ld.lld, and llvm-objcopy. Synthetic tests run without
game files; the ARM tests require those tools plus Unicorn and skip explicitly
when they are absent.

The Vita builder takes explicit `--game` and `--self` paths. It uses its own
`build/vita` and `work/vita` outputs, portable glyph metrics, reviewed overrides,
and native ARM/GXT tools. PS3 path environment variables retain their existing
meaning. Follow [VITA_PORT.md](VITA_PORT.md) for the complete build/verification/
packaging workflow, and [VITA_INSTALL.md](VITA_INSTALL.md) for player setup.

## Contributions

For player testing, report the platform/title ID, build version, emulator version or Vita firmware, episode, unit,
attack or menu, expected behavior, and reproduction steps. Screenshots are
especially useful for spacing and paging issues. Share no game dumps, license
keys, or save files containing private information in issues or commits.

For tooling changes, explain the behavior change and validation. Asset/layout
fixes should preserve unrelated atlas pixels and archive entries. Update the
public screenshots only with clean real captures and record their provenance.
