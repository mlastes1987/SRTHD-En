"""Stamp pk87 / eng vNUMBER into the native title background on PS3 or Vita.

Uses the game's existing bitmap glyphs, not a separately generated art asset.
python tools/title_version.py --platform ps3 --archive build/current.CPK --output build/versioned.CPK
The input must have a clean, unstamped title background (entry 117).
"""
import argparse,hashlib,json,re,struct
from pathlib import Path
from PIL import Image,ImageChops,ImageFilter
from cpk import Cpk,crilayla_decompress

ROOT=Path(__file__).resolve().parents[1]
FONT=ROOT/'work/tabata/00000.bin'
METRICS=Path(__file__).with_name('vita_font_metrics.json')
VERSIONS=Path(__file__).with_name('translation_versions.json')
RIGHT=1232
BOTTOM=676
SIZE=18
LINE_STEP=24


def current(platform):return json.loads(VERSIONS.read_text())[platform]


def number(version):
    match=re.fullmatch(r'(\d+\.\d+\.\d+)(?:[-.][A-Za-z0-9.-]+)?',version)
    if not match:raise ValueError('Version must begin with major.minor.patch')
    return match[1]


def load_font(path):
    data=Path(path).read_bytes()
    if len(data)<128 or data[0x18]!=0xab or struct.unpack_from('>HH',data,0x20)!=(4096,1120):
        raise ValueError('Expected the original 4096x1120 GCM G8B8 font atlas')
    raw=data[128:]
    if len(raw)!=4096*1120*2:raise ValueError('Invalid font payload')
    return ImageChops.lighter(Image.frombytes('L',(4096,1120),raw[::2]),
                             Image.frombytes('L',(4096,1120),raw[1::2]))


def line(text,font,metrics):
    width=sum(round(metrics[c]['advance']*32+metrics[c].get('adjust_px',0)) for c in text)
    mask=Image.new('L',(width,32));x=0
    for c in text:
        m=metrics[c];box=m['box']
        if box:
            gx=m['glyph']%128*32;gy=m['glyph']//128*32
            glyph=font.crop((gx+box[0],gy,gx+box[2],gy+32))
            mask.paste(glyph,(x,0))
        x+=round(m['advance']*32+m.get('adjust_px',0))
    return mask.resize((max(1,round(width*SIZE/32)),SIZE),Image.Resampling.LANCZOS)


def screen(atlas):
    if atlas.size!=(1024,1024):raise ValueError('Unexpected title atlas dimensions')
    im=Image.new('RGBA',(1280,720))
    im.paste(atlas.crop((0,0,1024,720)),(0,0))
    im.paste(atlas.crop((0,720,720,976)).transpose(Image.Transpose.ROTATE_270),(1024,0))
    return im


def stamp(atlas,version,font):
    metrics=json.loads(METRICS.read_text())
    labels=['pk87','eng v'+number(version)]
    overlay=Image.new('RGBA',(1280,720))
    for i,text in enumerate(labels):
        mask=line(text,font,metrics)
        x=RIGHT-mask.width;y=BOTTOM-SIZE-(1-i)*LINE_STEP
        pad=Image.new('L',(mask.width+4,SIZE+4));pad.paste(mask,(2,2))
        stroke=pad.filter(ImageFilter.MaxFilter(3))
        layer=Image.new('RGBA',pad.size,(0,0,0,0))
        layer.paste((0,0,0,210),(0,0,*layer.size),stroke)
        layer.paste((255,255,255,255),(0,0,*layer.size),pad)
        overlay.alpha_composite(layer,(x-2,y-2))
    bounds=overlay.getchannel('A').getbbox()
    if bounds[0]<1024 or bounds[2]>=1280 or bounds[3]>=720:raise ValueError('Label outside right title pane')
    im=screen(atlas);im.alpha_composite(overlay)
    result=atlas.copy()
    result.paste(im.crop((1024,0,1280,720)).transpose(Image.Transpose.ROTATE_90),(0,720))
    # Native title uses a rotated right-hand tile. Convert the screen bounds.
    native_box=(bounds[1],720+1280-bounds[2],bounds[3],720+1280-bounds[0])
    return result,dict(lines=labels,version=version,screen_bounds=bounds,atlas_bounds=native_box,
                       font_size=SIZE,right_margin=1280-RIGHT,bottom_margin=720-BOTTOM)


def texture(raw,platform,version,font):
    if platform=='ps3':
        from gcm_texture import decode,encode
    elif platform=='vita':
        from vita_gxt import decode,encode_region
    else:raise ValueError('Unknown platform')
    original=decode(raw);im,report=stamp(original,version,font)
    if platform=='ps3':packed=encode(raw,im)
    else:packed=encode_region(raw,im.crop(report['atlas_bounds']),report['atlas_bounds'])
    actual=decode(packed)
    # Exact visual preservation outside the version-label rectangle.
    box=report['atlas_bounds']
    for region in [(0,0,1024,box[1]),(0,box[3],1024,1024),
                   (0,box[1],box[0],box[3]),(box[2],box[1],1024,box[3])]:
        if original.crop(region).tobytes()!=actual.crop(region).tobytes():
            raise ValueError('Unrelated title pixels changed')
    return packed,screen(actual),report


def archive(source,output,platform,version,font_path=FONT,background=None):
    if Path(source).resolve()==Path(output).resolve():raise ValueError('Use a separate output archive')
    source=Cpk(str(source));replacements={};report=None;preview=None
    clean=Cpk(str(background)) if background else source
    for row in clean.files:
        if int(row['FileName'].split('.')[0])==117:
            raw=clean.payload(row)
            if raw.startswith(b'CRILAYLA'):raw=crilayla_decompress(raw)
            replacements[117],preview,report=texture(raw,platform,version,load_font(font_path))
    if not replacements:raise ValueError('Title background entry 117 missing')
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    source.rebuild(replacements,str(output));built=Cpk(str(output))
    rows={int(r['FileName'].split('.')[0]):r for r in source.files}
    for row in built.files:
        fid=int(row['FileName'].split('.')[0]);raw=built.payload(row)
        if fid==117:
            if raw.startswith(b'CRILAYLA'):raw=crilayla_decompress(raw)
            if raw!=replacements[117]:raise ValueError('Title replacement roundtrip failed')
        elif raw!=source.payload(rows[fid]):raise ValueError('Unrelated archive entry changed')
    preview.save(str(output)+'.title.png')
    report.update(platform=platform,output_sha256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),
                  unchanged_entries=len(rows)-1)
    Path(str(output)+'.title.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--platform',choices=['ps3','vita'],required=True)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--version')
    ap.add_argument('--font',type=Path,default=FONT)
    ap.add_argument('--background-archive',type=Path,help='Original archive supplying a clean title texture for repeat builds')
    args=ap.parse_args()
    print(json.dumps(archive(args.archive,args.output,args.platform,args.version or current(args.platform),args.font,args.background_archive),indent=2))
