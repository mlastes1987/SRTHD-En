"""Verify staged Vita text, pointer rewrites, hooks, BSS, and battle quote limits."""
import argparse
import collections
import json
from pathlib import Path
import struct
import capstone
from vita_arm import address_pairs
from vita_text import segments
from vita_runtime import FONT_METRICS


def verify(source,output,report,runtime):
    original=segments(source);built=segments(output)
    def at(data,segs,va,size):
        s=next(s for s in segs if s['type']==1 and s['va']<=va and va+size<=s['va']+s['size'])
        return data[s['off']+va-s['va']:s['off']+va-s['va']+size]
    permitted=[bytearray(s['size']) for s in original]
    def allow(va,size):
        n=next(i for i,s in enumerate(original) if s['type']==1 and s['va']<=va and va+size<=s['va']+s['size'])
        p=va-original[n]['va'];permitted[n][p:p+size]=b'\1'*size
    assert [s['va'] for s in original]==[s['va'] for s in built]
    moves={}
    for e in report['entries']:
        off=int(e['offset'],16)
        s=next(s for s in original if s['type']==1 and s['off']<=off<s['off']+s['size'])
        va=s['va']+off-s['off']
        expected=e['english'][0].encode(e['encoding'])+b'\0'
        if e['status']=='translated':allow(va,e['slot'])
        elif e['status']=='relocated':moves[va]=int(e['target_va'],16)
        else:raise AssertionError(f'Unresolved text: {e}')
        assert at(output,built,moves.get(va,va),len(expected))==expected,e
    pointer_count=0
    for s in original:
        if s['type']!=1:continue
        for pos in range(s['off'],s['off']+s['size']-3,4):
            old=struct.unpack_from('<I',source,pos)[0]
            if old in moves:
                va=s['va']+pos-s['off'];allow(va,4)
                assert struct.unpack('<I',at(output,built,va,4))[0]==moves[old]
                pointer_count+=1
    pairs=address_pairs(source,original[0]);after_pairs=address_pairs(output,built[0])
    after={(lo,hi):target for target,lo,hi in after_pairs}
    immediate_count=0
    for target,lo,hi in pairs:
        if target in moves:
            assert after[(lo,hi)]==moves[target],(hex(target),hex(lo))
            allow(lo,4);allow(hi,4);immediate_count+=1
    md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB)
    for pc,target in runtime['hooks'].items():
        pc=int(pc,16);allow(pc,4)
        ins=list(md.disasm(at(output,built,pc,4),pc))
        assert len(ins)==1 and ins[0].mnemonic=='b.w' and int(ins[0].op_str[1:],16)==int(target,16)
    allow(0x81009d3a,4)
    changed=0
    for n,(a,b) in enumerate(zip(original,built)):
        before=source[a['off']:a['off']+a['size']]
        after=output[b['off']:b['off']+a['size']]
        if a['type']!=1:assert before==after;continue
        for p,(x,y) in enumerate(zip(before,after)):
            if x!=y:
                assert permitted[n][p],f'Unexplained loaded-byte change: {a["va"]+p:#x}'
                changed+=1
        if a['memsz']>a['size']:
            assert not any(output[b['off']+a['size']:b['off']+a['memsz']]),'BSS is not zero'
    metrics=json.loads(FONT_METRICS.read_text(encoding='utf8'))
    quotes=[]
    for e in report['entries']:
        off=int(e['offset'],16)
        if not 0xd5300<=off<0x11ea34 or e['encoding']!='utf-8':continue
        text=e['english'][0]
        lines=text.splitlines()
        assert len(text.encode('utf-8'))+7<=104,e
        assert len(lines)<=4,e
        for i,line in enumerate(lines):
            width=sum(int(metrics[c]['advance']*38+metrics[c]['adjust_px']) if c in metrics else 38 for c in line)
            assert width+(38 if i==0 else 0)<=800,(e,width)
        quotes.append((len(lines)+1)//2)
    return dict(text_entries=len(report['entries']),moved_strings=len(moves),
                updated_table_pointers=pointer_count,updated_instruction_pairs=immediate_count,
                verified_hooks=len(runtime['hooks']),explained_changed_loaded_bytes=changed,
                battle_quotes=len(quotes),two_page_quotes=sum(p==2 for p in quotes),
                bss_zero_verified=True,comment_segment_preserved=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=Path('work/vita/eboot.original.self'))
    ap.add_argument('--image',type=Path,default=Path('build/vita/eboot.bin'))
    ap.add_argument('--work',type=Path,default=Path('work/vita'))
    args=ap.parse_args()
    result=verify(args.source.read_bytes(),args.image.read_bytes(),
                  json.loads((args.work/'text_port_report.json').read_text(encoding='utf8')),
                  json.loads((args.work/'runtime_report.json').read_text(encoding='utf8')))
    (args.work/'verification_report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))
