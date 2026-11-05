#!/usr/bin/env python3
"""Build the translated EBOOT from the CSV and optionally install it for RPCS3.

  python tools/build.py                     # build build/EBOOT.BIN
  python tools/build.py --install           # ... and copy it into RPCS3
  python tools/build.py --install --test    # ... and boot it headless
  python tools/build.py --proportional --install  # experimental glyph advances

The RPCS3 install is never modified without a backup: the original EBOOT.BIN is
kept as EBOOT.BIN.orig next to it and can be restored with
build/restore-original.bat.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from project_paths import ORIGINAL, RPCS3_DIR
BASE_ELF = str(ORIGINAL / "USRDIR/EBOOT.elf")
TEXT_JSON = os.path.join(ROOT, "work", "text", "text_banks.json")
CSV = os.path.join(ROOT, "work", "text", "translation.csv")
TR_JSON = os.path.join(ROOT, "work", "text", "tr.json")
OUT = os.path.join(ROOT, "build", "EBOOT.BIN")
RPCS3_GAME = str(RPCS3_DIR / "dev_hdd0/game/NPJB00514/USRDIR") if RPCS3_DIR else None
RPCS3_EXE = str(RPCS3_DIR / "rpcs3.exe") if RPCS3_DIR else None


def run(*args):
    print("+", " ".join(args))
    subprocess.run(list(args), check=True)


def main(argv):
    install = "--install" in argv
    test = "--test" in argv
    if (install or test) and RPCS3_DIR is None:
        raise SystemExit("Set SRW_RPCS3_DIR before using --install or --test.")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "shots"), exist_ok=True)

    run(sys.executable, os.path.join(ROOT, "tools", "csvtool.py"), "apply",
        TEXT_JSON, CSV, TR_JSON)
    run(sys.executable, os.path.join(ROOT, "tools", "srwtext.py"), "import",
        BASE_ELF, TR_JSON, OUT)

    # Optional letter-spacing tweak.  The engine advances one full cell per
    # character (advance == descriptor font size), so a smaller size is the only
    # lever that pulls the letters together.  Recorded in a file rather than a
    # flag so a plain rebuild cannot silently undo it.
    size_file = os.path.join(ROOT, "work", "text", "text_size.txt")
    if os.path.exists(size_file):
        size = open(size_file, encoding="utf-8").read().strip()
        if size:
            run(sys.executable, os.path.join(ROOT, "tools", "narrow_text.py"),
                "--size", size)

    if "--proportional" in argv:
        run(sys.executable, os.path.join(ROOT, "tools", "proportional_font.py"))
        run(sys.executable, os.path.join(ROOT, "tools", "battle_pages.py"))

    if install:
        dst_bin = os.path.join(RPCS3_GAME, "EBOOT.BIN")
        dst_orig = os.path.join(RPCS3_GAME, "EBOOT.BIN.orig")
        if not os.path.exists(dst_orig):
            shutil.copy2(dst_bin, dst_orig)
            print("backed up original ->", dst_orig)
        shutil.copy2(OUT, dst_bin)
        print("installed ->", dst_bin)

        # Keep the standalone test copy in step.  Leaving an old build sitting
        # in build/game is how a diagnostic ELF once got launched by mistake
        # after the real translation had been installed.
        playground = os.path.join(ROOT, "build", "game", "USRDIR", "EBOOT.BIN")
        if os.path.exists(playground):
            shutil.copy2(OUT, playground)
            print("refreshed test copy ->", playground)

    if test and install:
        try:
            subprocess.run([RPCS3_EXE, "--headless", "--no-gui",
                            os.path.join(RPCS3_GAME, "EBOOT.BIN")], timeout=45)
        except subprocess.TimeoutExpired:
            print("boot smoke test: ran 45s without exiting (expected)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
