"""Build and verify PCSG00260 English text/UI, spacing, and paging.

python tools/vita_build.py --game local/vita/original --self local/vita/eboot.original.self
The build stages outputs without modifying an installed game.
"""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path
from PIL import Image
from cpk import Cpk, crilayla_decompress
from vita_gxt import encode, decode
from vita_text import build


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game',type=Path,required=True)
    ap.add_argument('--self',dest='self_path',type=Path,required=True)
    ap.add_argument('--csv',type=Path,default=Path('work/text/translation.csv'))
    ap.add_argument('--art',type=Path,default=Path('work/ui_edit'))
    ap.add_argument('--output',type=Path,default=Path('build/vita'))
    ap.add_argument('--work',type=Path,default=Path('work/vita'))
    ap.add_argument('--basic',action='store_true',help='Rebuild the initial in-place text/UI port only')
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    args.work.mkdir(parents=True,exist_ok=True)
    original=args.self_path.read_bytes()
    overrides={} if args.basic else json.loads(Path('tools/vita_text_overrides.json').read_text(encoding='utf8'))
    data,report=build(original,args.csv,relocate=not args.basic,overrides=overrides)
    if not args.basic:
        from vita_runtime import patch
        data=patch(data,original,args.work)
    previous=args.output/'manifest.json'
    if previous.exists():
        history=args.output/'history';history.mkdir(exist_ok=True)
        shutil.copy2(previous,history/(sha(previous.read_bytes())+'.json'))
        shutil.copy2(previous,args.output/'previous_manifest.json')
    (args.output/'eboot.bin').write_bytes(data)
    (args.work/'text_port_report.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    archive_path=args.game/'DATA/kurodata/KDataVITA.cpk'
    archive=Cpk(str(archive_path))
    art={118:'title_menu_faithful_native.png',
         119:'super_robot_wars_title_texture_single_line.png',
         138:'level_up_atlas_138.png'}
    replacements={}
    preview=args.work/'ui_preview';preview.mkdir(exist_ok=True)
    for fid,name in art.items():
        row=next(r for r in archive.files if int(r['FileName'])==fid)
        raw=archive.payload(row)
        if raw.startswith(b'CRILAYLA'):raw=crilayla_decompress(raw)
        with Image.open(args.art/name) as im:replacements[fid]=encode(raw,im)
        decode(replacements[fid]).save(preview/f'{fid:05}.png')
    if not args.basic:
        row=next(r for r in archive.files if int(r['FileName'])==32)
        raw=archive.payload(row)
        if raw.startswith(b'CRILAYLA'):raw=crilayla_decompress(raw)
        raw=bytearray(raw)
        # Vita and PS3 originals have byte-identical team-selection SSAD panes.
        # Apply only the two properties verified in the PS3 banner fix.
        for off,before,after in ((0xce4,219000,271000),(0x10e8,1000,0)):
            if struct.unpack_from('<I',raw,off)[0]!=before:raise ValueError('Team banner source changed')
            struct.pack_into('<I',raw,off,after)
        replacements[32]=bytes(raw)
    output_archive=args.output/'KDataVITA.cpk'
    archive.rebuild(replacements,str(output_archive))
    built=Cpk(str(output_archive))
    for row in built.files:
        fid=int(row['FileName']);raw=built.payload(row)
        if fid in replacements:
            if raw.startswith(b'CRILAYLA'):raw=crilayla_decompress(raw)
            if raw!=replacements[fid]:raise ValueError(f'Bad replacement {fid}')
        else:
            before=next(r for r in archive.files if int(r['FileName'])==fid)
            if raw!=archive.payload(before):raise ValueError(f'Untouched payload changed: {fid}')
    manifest={'title_id':'PCSG00260','stage':'initial text and UI port' if args.basic else 'proportional spacing and attack paging',
              'runtime_tested':False,'text_counts':report['counts'],
              'ui_entries':sorted(replacements),'files':[]}
    if not args.basic:manifest['runtime']=json.loads((args.work/'runtime_report.json').read_text())
    if not args.basic:
        from vita_verify import verify
        validation=verify(original,data,report,manifest['runtime'])
        (args.work/'verification_report.json').write_text(json.dumps(validation,indent=2),encoding='utf8')
        manifest['validation']=validation
    for relative,output in [('eboot.bin',args.output/'eboot.bin'),
                            ('DATA/kurodata/KDataVITA.cpk',output_archive)]:
        manifest['files'].append(dict(path=relative,output=str(output.resolve()),
            source_sha256=sha((args.game/relative).read_bytes()),
            output_sha256=sha(output.read_bytes())))
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Text:',report['counts'])
    print(f'UI: {len(replacements)} replacements verified; {len(archive.files)-len(replacements)} untouched payloads identical')
    print('Staged build:',args.output)


if __name__=='__main__':main()
