"""Install/restore the staged Vita3K test build with hash checks and backups.

Close the game before use; Vita3K's library window may remain open.
python tools/vita_install.py --target <Vita3K ux0/app/PCSG00260>
python tools/vita_install.py --target <same path> --restore
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=Path('build/vita/manifest.json'))
    ap.add_argument('--restore',action='store_true')
    ap.add_argument('--upgrade-from',type=Path,help='Verified earlier build manifest for the initial installer migration')
    args=ap.parse_args()
    root=args.target.resolve()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    if root.name!=manifest['title_id'] or not (root/'sce_sys/param.sfo').is_file():
        raise ValueError('Target must be the installed PCSG00260 game directory')
    backup=root/'.srw-vita-english/original'
    histories=[]
    history_paths=[root/'.srw-vita-english/installed.json',args.manifest.with_name('previous_manifest.json')]
    if args.upgrade_from:history_paths.append(args.upgrade_from)
    for history in history_paths:
        if history.is_file():
            old=json.loads(history.read_text(encoding='utf8'))
            if old.get('title_id')==manifest['title_id']:histories.extend(old['files'])
    operations=[]
    for entry in manifest['files']:
        dst=(root/entry['path']).resolve()
        if not dst.is_relative_to(root):raise ValueError('Unsafe manifest path')
        original=backup/entry['path']
        accepted={entry['source_sha256'],entry['output_sha256']}
        accepted.update(e['output_sha256'] for e in histories
                        if e['path']==entry['path'] and e['source_sha256']==entry['source_sha256'])
        installed_hash=digest(dst)
        if installed_hash not in accepted:
            raise ValueError(f'Unknown installed file; refusing to overwrite: {dst}')
        if original.exists() and digest(original)!=entry['source_sha256']:
            raise ValueError(f'Backup hash mismatch: {original}')
        if not original.exists() and installed_hash!=entry['source_sha256']:
            raise ValueError(f'Original backup missing: {original}')
        src=original if args.restore else Path(entry['output'])
        if not args.restore and not src.is_absolute():src=args.manifest.resolve().parent/src
        wanted=entry['source_sha256'] if args.restore else entry['output_sha256']
        if not src.is_file() or digest(src)!=wanted:
            raise ValueError(f'Source hash mismatch: {src}')
        operations.append((entry,dst,original,src,wanted))
    # Validate the complete operation before touching any installed file.
    for entry,dst,original,src,wanted in operations:
        if not original.exists():
            if digest(dst)!=entry['source_sha256']:raise ValueError('Original backup missing')
            original.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dst,original)
            if digest(original)!=entry['source_sha256']:raise ValueError('Backup verification failed')
        shutil.copy2(src,dst)
        if digest(dst)!=wanted:raise ValueError(f'Installation verification failed: {dst}')
        print(('Restored: ' if args.restore else 'Installed: ')+entry['path'])
    print('Verified original backups:',backup)
    if not args.restore:
        (root/'.srw-vita-english/installed.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')


if __name__=='__main__':main()
