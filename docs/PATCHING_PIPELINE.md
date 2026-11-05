# Building a patch-only release

See the [tool usage guide](TOOLS.md#package-and-test-an-installer) for command
examples and the [changelog](../CHANGELOG.md) for the contents and validation
status of each preview.

This pipeline is for the maintainer's local build workspace. Players get the
current test build on [Discord](https://discord.gg/DwR2jxj5b) and use the
included Windows patcher; Python is not needed by players.

Prepare the ignored inputs listed in [DEVELOPMENT.md](DEVELOPMENT.md), then:

```powershell
python tools/release_patch.py --version 0.1.1-preview
```

Every release needs a new version label. The builder refuses to overwrite an
existing release folder. Override archive inputs if needed:

```powershell
python tools/release_patch.py --version 0.1.1-preview --ui-archive build/KDATAPS3.translated.CPK --unit-archive build/PIECE1STPS3.translated.CPK
```

The command rebuilds EBOOT with proportional spacing and both paging paths,
runs text/paging checks, makes and round-trips compressed binary differences,
compiles the C# patcher, and tests installation, rollback, upgrades and restore
on temporary game copies before packaging. The output is a ZIP and a SHA-256
sidecar under `release/`. The artwork archives are inputs; the command does
not regenerate art or replay historical texture edits.

Only these USRDIR files are patched:

- `EBOOT.BIN`
- `DATA/KURODATA/KDATAPS3.CPK`
- `DATA/PIECE/PIECE1STPS3.CPK`

The executable delta uses the original decrypted ELF as its source. On a
player's installation, the patcher validates the encrypted original, invokes
the player's RPCS3 `--decrypt` on a temporary copy, and checks the resulting
ELF before patching. An optional manually decrypted original ELF is supported.
No keys, emulator or complete translated binaries are included in the ZIP.

The patcher resolves the selected game folder, checks PARAM.SFO's title ID
and all file/payload hashes, and reconstructs and validates every replacement
before changing game files. Original backups and recovery state are kept in
`NPJB00514/.srwt1-english`. Writes use same-volume atomic replacements; a
failure rolls back completed writes. An interrupted installation can be
retried or restored. Unknown later modifications are not overwritten.

Automatic decryption and install/restore have passed on a disposable original
game copy with the development RPCS3 installation. GUI fields, layout and
missing-folder validation have also been inspected. Broader in-game testing
is still needed, especially for battle paging and menu layout.

Explicit integration tests:

```powershell
python tools/test_release.py release/SRWT1-HD-English-0.1.1-preview
python tools/test_release_decrypt.py release/SRWT1-HD-English-0.1.1-preview PATH_TO_RPCS3_EXE
```

The `.srwdiff` format is raw DEFLATE containing `SRWDIF01`, a little-endian
uint64 output size, and commands: `C` + uint32 source offset + uint32 length;
`A` + uint32 literal length + literal bytes; `E` ends the stream. Bounds checks
and final SHA-256 checks validate reconstructed files. Package hashes detect
corruption; they do not authenticate the publisher. The preview executable
is unsigned. Hosting, signing and publication are separate steps.

RPCS3 CLI behavior is documented by its official source:
[argument handling](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/rpcs3.cpp),
[binary decryption](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Crypto/decrypt_binaries.cpp).
