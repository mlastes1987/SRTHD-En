"""End-to-end installer tests against workspace-only copies of original files."""
from pathlib import Path
from project_paths import ORIGINAL
import shutil
import subprocess
import tempfile
import json
import sys
from release_patch import ROOT, delta, apply


def main():
    package=Path(sys.argv[1]).resolve()
    # Synthetic edge cases exercise copy/add transitions and empty outputs.
    for source,target in [(b'',b''),(b'',b'hello'),(b'x'*1000,b'x'*600+b'change'+b'x'*700),
                          (bytes(range(256))*20,b'prefix'+bytes(range(256))*20+b'end')]:
        assert apply(source,delta(source,target))==target
    compiler=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    (ROOT/'build').mkdir(exist_ok=True)
    harness=ROOT/'build/InstallerTests.exe'
    subprocess.run([str(compiler),'/nologo','/target:exe','/main:InstallerTests',
                    '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll',
                    '/out:'+str(harness),str(ROOT/'installer/Program.cs'),str(ROOT/'installer/InstallerTests.cs')],check=True)
    with tempfile.TemporaryDirectory(prefix='installer-test-',dir=ROOT/'build') as temp:
        temp=Path(temp)
        game=temp/'RPCS3 Test Space'/'dev_hdd0/game/NPJB00514'
        game.mkdir(parents=True)
        original=Path(sys.argv[2]) if len(sys.argv)>2 else ORIGINAL
        shutil.copy2(original/'PARAM.SFO',game/'PARAM.SFO')
        manifest=json.loads((package/'manifest.json').read_text())
        for entry in manifest['files']:
            dst=game/'USRDIR'/entry['path']; dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original/'USRDIR'/entry['path'],dst)
        subprocess.run([str(harness),str(package),str(game),str(original/'USRDIR/EBOOT.elf'),
                        str(ROOT/'shots/english_patcher_preview.png')],check=True)
        # Public CLI preflight accepts either RPCS3 root or game/USRDIR.
        for selection in (game/'USRDIR',temp/'RPCS3 Test Space'):
            subprocess.run([str(package/'SRW English Patcher.exe'),'--check','--game',str(selection)],check=True)
    print('Installer integration checks passed; original live game was not modified.')


if __name__=='__main__': main()
