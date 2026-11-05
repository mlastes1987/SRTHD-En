"""Verify automatic decryption/install on a disposable workspace game copy."""
from pathlib import Path
from project_paths import ORIGINAL
import json
import shutil
import subprocess
import sys
import tempfile
from release_patch import ROOT, sha

def main():
    package=Path(sys.argv[1]).resolve()
    rpc=Path(sys.argv[2]).resolve()
    manifest=json.loads((package/'manifest.json').read_text())
    original=ORIGINAL
    with tempfile.TemporaryDirectory(prefix='decrypt-install-test-',dir=ROOT/'build') as temp:
        game=Path(temp)/'NPJB00514';game.mkdir()
        shutil.copy2(original/'PARAM.SFO',game/'PARAM.SFO')
        for f in manifest['files']:
            dst=game/'USRDIR'/f['path'];dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original/'USRDIR'/f['path'],dst)
        subprocess.run([str(package/'SRW English Patcher.exe'),'--install','--game',str(game),'--rpcs3',str(rpc)],check=True)
        for f in manifest['files']:
            assert sha((game/'USRDIR'/f['path']).read_bytes())==f['target_sha256']
        subprocess.run([str(package/'SRW English Patcher.exe'),'--restore','--game',str(game)],check=True)
        for f in manifest['files']:
            assert sha((game/'USRDIR'/f['path']).read_bytes())==f['original_sha256']
    print('Automatic RPCS3 decryption, installation, and restoration passed on a temporary game copy.')


if __name__ == "__main__":
    main()
