"""Build and apply PCSG00260 proportional font hooks to a staged SELF."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
from vita_arm import branch
from vita_self import repack
from vita_text import segments

CAVE=0x81149900
FONT_METRICS=Path(__file__).with_name('vita_font_metrics.json')
HOOKS={0x81009ccc:'measure_class',0x81009cd2:'measure_default',
       0x81009ce4:'measure_plain',0x8100951e:'draw_bearing',
       0x81009564:'draw_advance'}
HOOKS.update({0x810766a6:'page_init',0x810779c6:'page_update',0x810770fe:'page_render'})
HOOKS.update({0x81072854:'faction_ally_big',0x810728ce:'faction_enemy_small',
              0x81072938:'faction_ally_small',0x810729a2:'faction_enemy_big'})


def symbols(elf):
    shoff=struct.unpack_from('<I',elf,32)[0]
    entsize,count=struct.unpack_from('<HH',elf,46)
    sections=[struct.unpack_from('<10I',elf,shoff+i*entsize) for i in range(count)]
    result={}
    for sec in sections:
        if sec[1]!=2:continue
        strings=sections[sec[6]];names=elf[strings[4]:strings[4]+strings[5]]
        for p in range(sec[4],sec[4]+sec[5],sec[9]):
            name,value=struct.unpack_from('<II',elf,p)
            label=names[name:names.find(b'\0',name)].decode()
            result[label]=value&~1
    return result


def toolchain():
    compiler=shutil.which('clang')
    if not compiler:raise FileNotFoundError('ARM-capable clang is required')
    clang=Path(compiler)
    def companion(name):
        for path in (clang.parent/(name+'.exe'),clang.parent/name):
            if path.is_file():return path
        found=shutil.which(name)
        if found:return Path(found)
        raise FileNotFoundError(f'{name} is required alongside clang or on PATH')
    return clang,companion('ld.lld'),companion('llvm-objcopy')


def assemble(work):
    work.mkdir(parents=True,exist_ok=True)
    metrics=json.loads(FONT_METRICS.read_text(encoding='utf8'))
    table=bytearray(283*2)
    for ch,m in metrics.items():
        adv=round(m['advance']*256);left=round(m['left']*32)
        assert 0<adv<512 and 0<=left<32
        value=0x8000|adv|left<<9|(0x4000 if ch in 'ks' else 0)
        struct.pack_into('<H',table,m['glyph']*2,value)
    (work/'font_metrics.bin').write_bytes(table)
    def width(text,size):return sum(int(metrics[c]['advance']*size+metrics[c]['adjust_px']) for c in text)
    faction=[1072-(width('Enemies',30)+10)/2,1072+(width('Allies /',38)+10)/2,
             1072-(width('Enemies',38)+10)/2,1072+(width('Allies /',30)+10)/2]
    (work/'faction_positions.bin').write_bytes(struct.pack('<4f',*faction))
    clang,linker,objcopy=toolchain()
    obj=work/'runtime.o';elf=work/'runtime.elf';binary=work/'runtime.bin'
    assembly=Path(__file__).with_suffix('.s').read_text(encoding='utf8')
    for name in ('font_metrics.bin','faction_positions.bin'):
        assembly=assembly.replace('work/vita/'+name,(work/name).resolve().as_posix())
    generated=work/'runtime.generated.s'
    generated.write_text(assembly,encoding='utf8')
    subprocess.run([str(clang),'--target=armv7a-none-eabi','-c',str(generated),'-o',str(obj)],check=True)
    returns={'return_measure_class':0x81009cd0,'return_measure_default':0x81009cd6,
             'return_measure_plain':0x81009ce8,'return_draw_bearing':0x81009522,
             'return_draw_advance':0x81009568,'return_page_init':0x810766aa,
             'return_page_update':0x810779ca,'return_page_hold':0x81079d0e,
             'return_page_render':0x81077102,
             **{'return_'+name:pc+4 for pc,name in HOOKS.items() if name.startswith('faction_')}}
    subprocess.run([str(linker),'-Ttext='+hex(CAVE),'--entry='+hex(CAVE),
                    *[f'--defsym={k}={v:#x}' for k,v in returns.items()],
                    str(obj),'-o',str(elf)],check=True)
    subprocess.run([str(objcopy),'-O','binary',str(elf),str(binary)],check=True)
    return binary.read_bytes(),symbols(elf.read_bytes())


def patch(source,original,work=Path('work/vita')):
    blob,labels=assemble(work)
    segs=segments(source);seg=segs[0]
    end=CAVE+len(blob)
    if end>segs[1]['va']:raise ValueError('Runtime payload exceeds executable-segment gap')
    payload=bytearray(source[seg['off']:seg['off']+seg['size']])
    start=CAVE-seg['va']
    if len(payload)>start and any(payload[start:]):raise ValueError('Runtime cave occupied')
    payload.extend(b'\0'*(start+len(blob)-len(payload)))
    payload[start:start+len(blob)]=blob
    old=segments(original)[0]
    for pc,name in HOOKS.items():
        pos=pc-seg['va'];oldpos=old['off']+pos
        if payload[pos:pos+4]!=original[oldpos:oldpos+4]:raise ValueError(f'Hook changed: {pc:#x}')
        payload[pos:pos+4]=branch(pc,labels[name])
    # Always use native width measurement in the centered text wrapper.
    pos=0x81009d3a-seg['va']
    if payload[pos:pos+4]!=original[old['off']+pos:old['off']+pos+4]:raise ValueError('Center hook changed')
    payload[pos:pos+4]=bytes.fromhex('4ff00103') # mov.w r3,#1
    output=repack(source,{0:bytes(payload)})
    report=dict(cave=hex(CAVE),payload_bytes=len(blob),end=hex(end),
                hooks={hex(pc):hex(labels[name]) for pc,name in HOOKS.items()},
                glyphs=95,ks_adjustment=-1,
                centered_measurement=True,
                paging=dict(ticks_per_page=120,buffers=['0x8125cdf4','0x8125ce6d'],
                            pointer='0x8125d0cc',max_lines=4,max_pages=2))
    (work/'runtime_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return output


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image',type=Path,default=Path('build/vita/eboot.bin'))
    ap.add_argument('--original',type=Path,default=Path('work/vita/eboot.original.self'))
    args=ap.parse_args()
    args.image.write_bytes(patch(args.image.read_bytes(),args.original.read_bytes()))
    print('Applied Vita proportional font hooks')
