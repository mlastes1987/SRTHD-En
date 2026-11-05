SUPER ROBOT WARS HD - ENGLISH PATCH (PREVIEW)
Supported game: NPJB00514, matching the original Japanese files.
Windows 10/11. Uses the Windows .NET Framework; no Python installation needed.

1. Install the game in RPCS3 and confirm that the original game boots.
2. Close RPCS3. Extract this entire ZIP to a normal folder.
3. Run "SRW English Patcher.exe".
4. Browse to your rpcs3.exe and your NPJB00514 game folder if necessary.
   The usual location is RPCS3/dev_hdd0/game/NPJB00514.
5. Click Install English patch. Wait for the completion message, then launch
   the game normally in RPCS3.

The patcher checks all source files and builds all replacements before changing
the game. It backs up originals in NPJB00514/.srwt1-english/backups. Keep that
folder for Restore originals and future patch upgrades. Saved games and RPCS3
settings are not replaced. If a file is an unsupported version or has been
modified by another patch, the installer stops instead of guessing.

The original EBOOT is encrypted. The patcher uses your own RPCS3 executable's
--decrypt command on a temporary copy and verifies the decrypted result. No
keys are included. If automatic decryption fails, use RPCS3's File > Decrypt
PS3 Binaries on your original EBOOT.BIN, then select the resulting EBOOT.elf
in the optional Decrypted ELF field. Your RPCS3 installation must already be
able to run the game. Do not download an EBOOT from somebody else.

To remove the translation, close RPCS3 and click Restore originals in the same
patcher. Restoration validates the backups and refuses to overwrite unknown
later modifications. A partial interrupted install can be retried or restored.
Do not delete the backup folder while the patch is installed.

This is an unsigned preview installer. The translation and new battle paging
still need broader in-game testing. The package contains binary differences,
not a playable game, emulator, licenses, or full translated game archives.

Advanced command line:
  "SRW English Patcher.exe" --check --game "path to NPJB00514"
  "SRW English Patcher.exe" --install --game "path" --rpcs3 "path to rpcs3.exe"
  "SRW English Patcher.exe" --install --game "path" --elf "path to EBOOT.elf"
  "SRW English Patcher.exe" --restore --game "path"

Exit code 0 means success; nonzero means no successful operation. The patcher
writes an operation log inside .srwt1-english after an install/restore attempt.
