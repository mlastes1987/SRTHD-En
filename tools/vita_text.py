"""Stage PCSG00260 translations in a decrypted, fixed-address Vita SELF.

python tools/vita_text.py --source work/vita/eboot.original.self

Only whole, NUL-terminated source matches with one English translation are
accepted. The optional relocation pass moves longer strings after the existing
BSS and updates data pointers and Thumb MOVW/MOVT references. Per-offset
overrides resolve Vita-specific labels and inline terrain-name records.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import struct


def segments(data):
    if data[:4] != b'SCE\0':
        raise ValueError('Expected a decrypted Vita SELF')
    elf, ph, si = (struct.unpack_from('<Q', data, p)[0] for p in (0x40, 0x48, 0x58))
    if data[elf:elf+6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected ELF32 little endian')
    count = struct.unpack_from('<H', data, elf+44)[0]
    result = []
    for i in range(count):
        p = struct.unpack_from('<8I', data, ph+32*i)
        off, size, compression, encryption = struct.unpack_from('<4Q', data, si+32*i)
        if compression != 1 or encryption != 2:
            raise ValueError('Export decrypted SELF with Vita3K first')
        if off+size > len(data) or size != p[4]:
            raise ValueError('Invalid segment bounds')
        result.append(dict(type=p[0], off=off, size=size, va=p[2], flags=p[6],memsz=p[5]))
    return result


def build(source, csv_path, relocate=False, overrides=None):
    overrides=overrides or {}
    data = bytearray(source)
    loads = [s for s in segments(source) if s['type'] == 1]
    choices = collections.defaultdict(set)
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['english']:
                choices[row['japanese']].add(row['english'])
    # Restrict pointer checks to loaded data, never SELF metadata/relocations.
    references=collections.defaultdict(list)
    for seg in loads:
        for p in range(seg['off'],seg['off']+seg['size']-3,4):
            value=struct.unpack_from('<I',source,p)[0]
            if any(s['va']<=value<s['va']+s['size'] for s in loads):
                references[value].append(p)
    targets=set(references)
    pairs=[]
    if relocate:
        from vita_arm import address_pairs
        pairs=address_pairs(source,loads[0])
        targets.update(p[0] for p in pairs)
    candidates = {}
    for japanese, english in choices.items():
        for enc in ('utf-8', 'cp932'):
            try: raw = japanese.encode(enc)+b'\0'
            except UnicodeEncodeError: continue
            for seg in loads:
                start, end = seg['off'], seg['off']+seg['size']
                pos = source.find(raw, start, end)
                while pos >= 0:
                    # Do not treat a suffix inside another string as a full match.
                    if pos == start or source[pos-1] == 0:
                        candidates[pos] = (japanese, english, enc, raw, seg)
                    pos = source.find(raw, pos+1, end)
    for key,override in overrides.items():
        off=int(key,16)
        if off in candidates:continue
        japanese=override['japanese']
        enc=override.get('encoding','utf-8')
        raw=japanese.encode(enc)+b'\0'
        seg=next((s for s in loads if s['off']<=off and off+len(raw)<=s['off']+s['size']),None)
        if seg is None or source[off:off+len(raw)]!=raw:
            raise ValueError(f'Override source bytes changed at {off:#x}')
        candidates[off]=(japanese,{override['english']},enc,raw,seg)
    report = {'source_sha256': hashlib.sha256(source).hexdigest(),
              'counts': {}, 'entries': []}
    counts = collections.Counter()
    for off, (japanese, english, enc, raw, seg) in sorted(candidates.items()):
        override=overrides.get(hex(off))
        if override:
            if override['japanese']!=japanese:raise ValueError(f'Override source mismatch at {off:#x}')
            english={override['english']}
        entry = dict(offset=hex(off), encoding=enc, japanese=japanese,
                     english=sorted(english))
        status = 'ambiguous' if len(english) != 1 else 'ready'
        replacement = None
        if status == 'ready':
            try: replacement = next(iter(english)).encode(enc)+b'\0'
            except UnicodeEncodeError:
                status = 'encoding'
        va = seg['va']+off-seg['off']
        # A merged literal may also be referenced at a suffix. Preserve it.
        if status == 'ready' and any(v in targets for v in range(va+1, va+len(raw)-1)):
            status = 'interior_reference'
        limit = min((off+len(raw)+3)//4*4, seg['off']+seg['size'])
        slot = len(raw)
        while off+slot < limit and source[off+slot] == 0:
            slot += 1
        if override and 'inline_capacity' in override:
            capacity=override['inline_capacity']
            if off+capacity>seg['off']+seg['size'] or any(source[off+len(raw):off+capacity]):
                raise ValueError(f'Inline label capacity changed at {off:#x}')
            slot=capacity
        if status == 'ready' and len(replacement) > slot:
            status = 'overflow'
        if status == 'ready':
            data[off:off+slot] = replacement+b'\0'*(slot-len(replacement))
            status = 'translated'
        entry.update(status=status, slot=slot,
                     required=len(replacement) if replacement is not None else None)
        report['entries'].append(entry)
        counts[status] += 1
    assert len(data) == len(source)
    if relocate:
        from vita_self import repack
        from vita_arm import immediate
        segs=segments(source)
        pool_seg=loads[-1]
        pool=bytearray(b'\0'*(pool_seg['memsz']-pool_seg['size']))
        for e in report['entries']:
            if e['status'] not in ('overflow','interior_reference'):continue
            off=int(e['offset'],16)
            seg=next(s for s in loads if s['off']<=off<s['off']+s['size'])
            va=seg['va']+off-seg['off']
            raw=e['english'][0].encode(e['encoding'])+b'\0'
            refs=references.get(va,[])
            code_refs=[p for p in pairs if p[0]==va]
            if not refs and not code_refs:
                e['status']='unreferenced_overflow';continue
            pool.extend(b'\0'*((-len(pool))%4))
            new_va=pool_seg['va']+pool_seg['size']+len(pool)
            pool.extend(raw)
            for p in refs:struct.pack_into('<I',data,p,new_va)
            for _,lo,hi in code_refs:
                for pc,value in ((lo,new_va&65535),(hi,new_va>>16)):
                    p=loads[0]['off']+pc-loads[0]['va']
                    data[p:p+4]=immediate(data[p:p+4],value)
            e.update(status='relocated',target_va=hex(new_va),
                     pointer_references=len(refs),instruction_references=len(code_refs))
        payloads={i:bytes(data[s['off']:s['off']+s['size']]) for i,s in enumerate(segs)}
        idx=segs.index(pool_seg)
        payloads[idx]+=bytes(pool)
        data=bytearray(repack(bytes(data),payloads))
    # Confirm every accepted translation after all writes, catching overlaps.
    for e in report['entries']:
        if e['status'] in ('translated','relocated'):
            old_off=int(e['offset'],16)
            old_seg=next(s for s in loads if s['off']<=old_off<s['off']+s['size'])
            va=int(e['target_va'],16) if e['status']=='relocated' else old_seg['va']+old_off-old_seg['off']
            new_seg=next(s for s in segments(data) if s['type']==1 and s['va']<=va<s['va']+s['size'])
            off=new_seg['off']+va-new_seg['va']
            expected = e['english'][0].encode(e['encoding'])+b'\0'
            assert data[off:off+len(expected)] == expected, e
    report['counts'] = dict(collections.Counter(e['status'] for e in report['entries']))
    report['output_sha256'] = hashlib.sha256(data).hexdigest()
    return bytes(data), report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--csv', type=Path, default=Path('work/text/translation.csv'))
    ap.add_argument('--output', type=Path, default=Path('build/vita/eboot.bin'))
    ap.add_argument('--report', type=Path, default=Path('work/vita/text_port_report.json'))
    ap.add_argument('--relocate',action='store_true')
    ap.add_argument('--overrides',type=Path)
    args = ap.parse_args()
    overrides=json.loads(args.overrides.read_text(encoding='utf8')) if args.overrides else None
    data, report = build(args.source.read_bytes(), args.csv,args.relocate,overrides)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['counts']))
    print('Staged:', args.output, '(not installed)')


if __name__ == '__main__':
    main()
