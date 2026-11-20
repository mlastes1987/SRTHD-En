# Vita playtest installation — PCSG00260

Current Vita package: **0.1.3-vita-preview** for the Japanese **PCSG00260 v1.00**
game. Builds and feedback are coordinated through
[Discord](https://discord.gg/DwR2jxj5b).

The filename is:

```text
SRW-HD-Vita-PCSG00260-English-0.1.3-vita-preview-rePatch.zip
```

This is a Vita replacement-file ZIP. The PS3 preview uses a separate Windows
patcher package named `SRWT1-HD-English-0.1.2-preview.zip`.

## Package contents

```text
README-PLAYTEST.txt
manifest.json
SHA256SUMS.txt
rePatch/
  PCSG00260/
    eboot.bin
    DATA/
      kurodata/
        KDataVITA.cpk
```

The two game files are modified replacements for your own installed copy.
Game installation data, license files, modules, emulators, and plugins are not
bundled. Keep `manifest.json` with the extracted folder if using the checked
developer installer. The ZIP has a separate `.zip.sha256` checksum; the
included `SHA256SUMS.txt` lists checksums for extracted files.

## Vita hardware / rePatch

Hardware execution of this build has **not been verified**. This layout is
provided for playtesting.

1. Close the game and back up any existing `PCSG00260` overlay.
2. Start with a working rePatch installation. Follow the
   [plugin's setup instructions](https://github.com/dots-tb/rePatch-reDux0/wiki/)
   for its requirements and configuration.
3. Extract the Vita ZIP and copy its `rePatch` folder to `ux0:`. The final paths
   must be `ux0:rePatch/PCSG00260/eboot.bin` and
   `ux0:rePatch/PCSG00260/DATA/kurodata/KDataVITA.cpk`.
4. Launch your installed Japanese `PCSG00260` game.

To disable this overlay, close the game and move its `PCSG00260` folder out of
`ux0:rePatch`. Keep any prior overlay backup until the new build is confirmed.

## Vita3K — manual replacement

1. Close the game and locate its installed `ux0/app/PCSG00260` directory.
2. Back up that directory's `eboot.bin` and `DATA/kurodata/KDataVITA.cpk`.
3. Copy the **contents of `rePatch/PCSG00260`** from the extracted ZIP into
   the installed `ux0/app/PCSG00260` directory, preserving the `DATA` structure.
4. Launch the game normally. Restore the two original backups to uninstall.

These instructions use the same installed-file replacement method as the
maintainer's current Vita3K test setup.

## Optional checked Vita3K installation

Use the public tools checkout with Python 3.10 or newer. The installer itself
uses the Python standard library and does not require Pillow or a compiler.
From the repository root, substitute your extracted package and installed game:

```powershell
python tools/vita_install.py --manifest "D:/Vita playtest/manifest.json" --target "D:/Vita3K/ux0/app/PCSG00260"
python tools/vita_install.py --manifest "D:/Vita playtest/manifest.json" --target "D:/Vita3K/ux0/app/PCSG00260" --restore
```

The tool validates every input before writing, accepts supported originals or
recognized installed previews, verifies copied files, and keeps originals under
`PCSG00260/.srw-vita-english/original`. Keep that backup directory and its
`installed.json` record for later upgrades. A manually modified installation
may need its original files restored before this checked installer accepts it.

## What needs testing

Automated checks cover the translated text, pointers, native buffer limits,
ARM instruction behavior, archive contents, package hashes, installation, and
restoration. The latest spacing/paging changes still need in-game confirmation.

- Long attack and counterattack quotes, including both pages and closing quotes.
- Multi-unit attacks, fast-forward, page timing, and transitions back to the map.
- Title selections, Objectives, Level Up!, team/hero banners, and Allies/Enemies.
- Terrain names, save/load dialogs, missing glyphs, clipping, and overlaps.
- Boot and save/load behavior on Vita hardware, if testing rePatch there.

Report platform, title ID, package version, Vita3K version or Vita firmware,
episode/unit/attack or menu, expected behavior, and reproduction steps on
[Discord](https://discord.gg/DwR2jxj5b) or
[GitHub Issues](https://github.com/mlastes1987/SRTHD-En/issues/new?template=bug_report.yml).
