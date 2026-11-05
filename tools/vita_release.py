"""Package a verified PCSG00260 build as a Vita rePatch playtest folder and ZIP.

python tools/vita_release.py --version 0.1.0-vita-preview
The private release contains replacement files; it is separate from the PS3
delta patcher and must stay outside the public source repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

PAYLOAD_PATHS={'eboot.bin','DATA/kurodata/KDataVITA.cpk'}


def sha(data):return hashlib.sha256(data).hexdigest()


def instructions(version):
    return f'''SUPER ROBOT WARS HD — PS VITA ENGLISH PLAYTEST
Title ID: PCSG00260 | Version: {version}

This is the experimental Vita translation package. It contains two modified
files in a standard rePatch layout. Supply your own installed Japanese
PCSG00260 game. No game installer, license, emulator, or plugin is bundled.

CONTENTS
  rePatch/PCSG00260/eboot.bin
  rePatch/PCSG00260/DATA/kurodata/KDataVITA.cpk

VITA HARDWARE / rePatch
1. Close the game and back up any existing PCSG00260 rePatch files.
2. Use an installed and working rePatch plugin. Follow its own setup guide:
   https://github.com/dots-tb/rePatch-reDux0/wiki/
3. Copy the included rePatch folder to ux0: so the executable is at:
   ux0:rePatch/PCSG00260/eboot.bin
4. Launch your installed PCSG00260 game.
To remove this overlay, move its PCSG00260 folder out of ux0:rePatch.
Hardware execution of this build has not been verified. This layout is
provided for playtesting, not as a hardware-compatibility claim.

VITA3K
1. Close the game. Locate its installed ux0/app/PCSG00260 folder.
2. Back up that folder's eboot.bin and DATA/kurodata/KDataVITA.cpk.
3. Copy the CONTENTS of the included rePatch/PCSG00260 folder into the
   installed ux0/app/PCSG00260 folder, keeping the DATA directory structure.
4. Launch the game normally. Restore your backups to undo the replacement.

Optional checked installation from the public tools checkout (Python 3.10+):
  python tools/vita_install.py --manifest PATH_TO_EXTRACTED/manifest.json --target PATH_TO/ux0/app/PCSG00260
  python tools/vita_install.py --manifest PATH_TO_EXTRACTED/manifest.json --target PATH_TO/ux0/app/PCSG00260 --restore
That tool verifies supported file hashes, preserves original backups, and
records the installed build for later upgrades.

WHAT TO TEST
The build includes proportional spacing matching the PS3 measurements,
two-page attack/counter dialogue, English UI artwork, and selection-label
overlap fixes. Automated checks cover text, pointers, ARM instructions,
archive contents, installation, and restoration. In-game behavior of the
latest spacing/paging changes still needs confirmation, especially multi-unit
attacks, fast-forward, page transitions, save/load dialogs, and map returns.

REPORTS AND CURRENT BUILDS
https://discord.gg/DwR2jxj5b
https://github.com/mlastes1987/SRTHD-En/issues
Include this version, platform/emulator version, episode, unit/attack or menu,
expected behavior, reproduction steps, and screenshots where useful.

SHA256SUMS.txt verifies the extracted payloads and metadata. The ZIP also has
a separate .zip.sha256 checksum beside it.
'''


def package(manifest_path,version,output):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,60}',version):
        raise ValueError('Invalid version label')
    manifest_path=manifest_path.resolve()
    build=json.loads(manifest_path.read_text(encoding='utf8'))
    if build.get('title_id')!='PCSG00260':raise ValueError('Expected PCSG00260 build')
    if {e['path'] for e in build['files']}!=PAYLOAD_PATHS or len(build['files'])!=2:
        raise ValueError('Release must contain exactly the two supported Vita replacement files')
    payloads={};files=[]
    for entry in build['files']:
        path=Path(entry['output'])
        if not path.is_absolute():path=manifest_path.parent/path
        data=path.read_bytes()
        if sha(data)!=entry['output_sha256']:raise ValueError(f'Build hash mismatch: {entry["path"]}')
        magic=b'SCE\0' if entry['path']=='eboot.bin' else b'CPK '
        if not data.startswith(magic):raise ValueError(f'Unexpected file format: {entry["path"]}')
        relative='rePatch/PCSG00260/'+entry['path']
        payloads[relative]=data
        files.append(dict(path=entry['path'],output=relative,size=len(data),
                          source_sha256=entry['source_sha256'],output_sha256=entry['output_sha256']))
    name='SRW-HD-Vita-PCSG00260-English-'+version+'-rePatch'
    folder=output/name;zip_path=output/(name+'.zip')
    if folder.exists() or zip_path.exists():raise FileExistsError('Choose a new version or output directory; package already exists')
    release=dict(format='srw-vita-repatch-v1',title_id='PCSG00260',platform='PS Vita',
                 version=version,kind='rePatch playtest',hardware_tested=False,
                 runtime_tested=bool(build.get('runtime_tested',False)),
                 stage=build.get('stage',''),text_counts=build.get('text_counts',{}),
                 validation=build.get('validation',{}),runtime=build.get('runtime',{}),files=files)
    payloads['manifest.json']=(json.dumps(release,indent=2)+'\n').encode('utf8')
    payloads['README-PLAYTEST.txt']=instructions(version).encode('utf8')
    payloads['SHA256SUMS.txt']=''.join(sha(data)+'  '+name+'\n' for name,data in sorted(payloads.items())).encode('utf8')
    folder.mkdir(parents=True)
    for relative,data in payloads.items():
        destination=folder/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for relative,data in sorted(payloads.items()):
            info=zipfile.ZipInfo(relative,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,data,compresslevel=9)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP integrity failure')
        if set(archive.namelist())!=set(payloads):raise ValueError('Unexpected ZIP contents')
        for relative,data in payloads.items():
            if archive.read(relative)!=data:raise ValueError(f'ZIP roundtrip failure: {relative}')
    checksum=zip_path.with_suffix(zip_path.suffix+'.sha256')
    checksum.write_text(sha(zip_path.read_bytes())+'  '+zip_path.name+'\n',encoding='utf8')
    return folder,zip_path


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path,default=Path('build/vita/manifest.json'))
    ap.add_argument('--version',required=True)
    ap.add_argument('--output',type=Path,default=Path('release'))
    args=ap.parse_args()
    folder,archive=package(args.manifest,args.version,args.output)
    print('rePatch folder:',folder/'rePatch')
    print('Verified ZIP:',archive)
    print('ZIP bytes:',archive.stat().st_size)
