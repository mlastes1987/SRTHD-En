"""Build a Windows patch-only release from verified local translation outputs.

python tools/release_patch.py --version 0.1.0-preview.1
No original game files, keys, emulator, or complete translated binaries ship.
"""
import argparse
import hashlib
import json
from pathlib import Path
from project_paths import ORIGINAL
import shutil
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b'SRWDIF01'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def delta(source, target, block=32):
    index = {}
    for pos in range(0, len(source)-block+1, block):
        index.setdefault(source[pos:pos+block], pos)
    out, literal = bytearray(MAGIC+struct.pack('<Q',len(target))), bytearray()
    def flush():
        if literal:
            out.extend(b'A'+struct.pack('<I',len(literal))+literal)
            literal.clear()
    pos = 0
    while pos < len(target):
        match = index.get(target[pos:pos+block]) if pos+block<=len(target) else None
        if match is None:
            literal.append(target[pos])
            pos += 1
            continue
        flush()
        size = block
        limit = min(len(source)-match,len(target)-pos)
        while size+block<=limit and source[match+size:match+size+block]==target[pos+size:pos+size+block]:
            size += block
        while size<limit and source[match+size]==target[pos+size]:
            size += 1
        out.extend(b'C'+struct.pack('<II',match,size))
        pos += size
    flush()
    out.extend(b'E')
    compressor = zlib.compressobj(9,zlib.DEFLATED,-15)
    return compressor.compress(out)+compressor.flush()


def apply(source, patch):
    data = zlib.decompress(patch,-15)
    assert data[:8]==MAGIC
    size, = struct.unpack_from('<Q',data,8)
    pos, out = 16, bytearray()
    while data[pos:pos+1]!=b'E':
        kind, pos = data[pos:pos+1], pos+1
        if kind==b'C':
            off,n = struct.unpack_from('<II',data,pos)
            pos += 8
            assert off+n<=len(source)
            out.extend(source[off:off+n])
        else:
            assert kind==b'A'
            n, = struct.unpack_from('<I',data,pos)
            pos += 4
            out.extend(data[pos:pos+n])
            pos += n
        assert len(out)<=size
    assert pos+1==len(data) and len(out)==size
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version',required=True)
    ap.add_argument('--original',type=Path,default=ORIGINAL)
    ap.add_argument('--output',type=Path,default=ROOT/'release')
    ap.add_argument('--ui-archive',type=Path,default=ROOT/'build/KDATAPS3.translated.CPK')
    ap.add_argument('--unit-archive',type=Path,default=ROOT/'build/PIECE1STPS3.translated.CPK')
    args = ap.parse_args()
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,60}',args.version):
        ap.error('Version must be a simple filename-safe label.')
    import sys
    for command in (
            [str(ROOT/'tools/build.py'),'--proportional'],
            ['-m','unittest','discover','-s','tools','-p','test_battle_pages.py'],
            ['-m','unittest','discover','-s','tools','-p','test_text_import.py'],
            [str(ROOT/'tools/verify_build.py')]):
        subprocess.run([sys.executable]+command,check=True,cwd=ROOT)
    folder = args.output/f'SRWT1-HD-English-{args.version}'
    if folder.exists():
        ap.error('Release folder exists; use a new version or output folder.')
    folder.mkdir(parents=True)
    (folder/'patches').mkdir()
    files = []
    for rel,target in (
            ('EBOOT.BIN',ROOT/'build/EBOOT.BIN'),
            ('DATA/KURODATA/KDATAPS3.CPK',args.ui_archive),
            ('DATA/PIECE/PIECE1STPS3.CPK',args.unit_archive)):
        original = args.original/'USRDIR'/rel
        source_path = original.with_suffix('.elf') if rel=='EBOOT.BIN' else original
        source, translated = source_path.read_bytes(),target.read_bytes()
        patch = delta(source,translated)
        assert apply(source,patch)==translated,rel
        patch_name = 'patches/'+Path(rel).name+'.srwdiff'
        (folder/patch_name).write_bytes(patch)
        item = dict(path=rel,patch=patch_name,source_sha256=sha(source),
                    original_sha256=sha(original.read_bytes()),target_sha256=sha(translated),
                    target_size=len(translated),patch_sha256=sha(patch),decrypt=rel=='EBOOT.BIN')
        files.append(item)
        print(f'{rel}: {len(translated):,} target bytes -> {len(patch):,} patch bytes')
    manifest = dict(format=1,title_id='NPJB00514',name='Super Robot Wars HD English',
                    version=args.version,channel='preview',files=files)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    shutil.copy2(ROOT/'installer/README.txt',folder/'README.txt')
    compiler = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:anycpu','/optimize+',
                    '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
                    '/reference:System.Web.Extensions.dll',
                    '/out:'+str(folder/'SRW English Patcher.exe'),str(ROOT/'installer/Program.cs')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/test_release.py'),str(folder),str(args.original)],check=True,cwd=ROOT)
    hashes = '\n'.join(sha(p.read_bytes())+'  '+p.relative_to(folder).as_posix()
                       for p in sorted(folder.rglob('*')) if p.is_file())+'\n'
    (folder/'SHA256SUMS.txt').write_text(hashes,encoding='utf-8')
    zip_path = shutil.make_archive(str(folder),'zip',root_dir=folder)
    Path(zip_path+'.sha256').write_text(sha(Path(zip_path).read_bytes())+'  '+Path(zip_path).name+'\n',encoding='utf-8')
    print('Release:',zip_path)


if __name__=='__main__':
    main()
