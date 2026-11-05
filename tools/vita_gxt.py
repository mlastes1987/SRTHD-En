"""PCSG00260 single-texture GXT P8 decoder/encoder (linear or swizzled).

GXM/GXT definitions: vitasdk vita-headers include/psp2/gxm.h and Scarlet
Platform/Sony/PSVita.cs. Palette colors are little-endian ABGR (RGBA bytes).
"""
import argparse
from pathlib import Path
import struct
from PIL import Image


def metadata(data):
    if data[:4] != b'GXT\0' or struct.unpack_from('<II', data, 4) != (0x10000003, 1):
        raise ValueError('Expected GXT v3 with one texture')
    off, size, palette, flags, layout, fmt = struct.unpack_from('<6I', data, 0x20)
    width, height, mips = struct.unpack_from('<HHI', data, 0x38)
    if fmt != 0x95000000 or mips != 1 or palette != 0:
        raise ValueError('Only P8 ABGR, one palette, one mip is supported')
    if size != width*height or layout not in (0, 0x60000000):
        raise ValueError('Unsupported P8 layout/size')
    palette_off = struct.unpack_from('<II', data, 0x0c)
    palette_off = sum(palette_off)-1024
    if palette_off < off+size or palette_off+1024 > len(data):
        raise ValueError('Invalid palette bounds')
    return off, size, palette_off, layout, width, height


def positions(width, height, layout):
    if layout == 0x60000000:
        return range(width*height)
    if width & (width-1) or height & (height-1):
        raise ValueError('Swizzled texture requires power-of-two dimensions')
    # Vita Morton order interleaves Y in the low bit, then X.
    bx, by = width.bit_length()-1, height.bit_length()-1
    def coord(x, y):
        v = 0
        for i in range(min(bx,by)):
            v |= ((y >> i)&1) << (2*i)
            v |= ((x >> i)&1) << (2*i+1)
        if bx > by: v |= (x >> by) << (2*by)
        if by > bx: v |= (y >> bx) << (2*bx)
        return v
    return [coord(x,y) for y in range(height) for x in range(width)]


def decode(data):
    off, size, pal, layout, width, height = metadata(data)
    colors = [data[pal+i*4:pal+i*4+4] for i in range(256)]
    rgba = b''.join(colors[data[off+p]] for p in positions(width,height,layout))
    return Image.frombytes('RGBA', (width,height), rgba)


def encode(original, image):
    off, size, pal, layout, width, height = metadata(original)
    image = image.convert('RGBA')
    if image.size != (width,height):
        raise ValueError('Replacement dimensions must match the original')
    indexed = image.quantize(colors=256, method=Image.Quantize.FASTOCTREE,
                             dither=Image.Dither.NONE)
    palette = bytes(indexed.getpalette('RGBA'))
    palette = palette.ljust(1024,b'\0')
    data = bytearray(original)
    data[pal:pal+1024] = palette
    for p, index in zip(positions(width,height,layout), indexed.tobytes()):
        data[off+p] = index
    assert len(data) == len(original)
    return bytes(data)


def encode_region(original, image, box, use_region_palette=False):
    """Replace one region; optionally restrict colors to its original indices.

    Region-only matching prevents unrelated frame colors from entering text
    glows. Both modes preserve all palette bytes and pixels outside the box.
    """
    off, size, pal, layout, width, height = metadata(original)
    left, top, right, bottom = box
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError('Region outside texture')
    image = image.convert('RGBA')
    if image.size != (right-left, bottom-top):
        raise ValueError('Replacement dimensions must match region')
    colors = [tuple(original[pal+i*4:pal+i*4+4]) for i in range(256)]
    def premult(c):
        return tuple(v*c[3]/255 for v in c[:3]) + (c[3],)
    palette = [premult(c) for c in colors]
    order = positions(width, height, layout)
    allowed = sorted({original[off+order[y*width+x]]
                      for y in range(top,bottom) for x in range(left,right)}) if use_region_palette else range(256)
    cache = {}
    data = bytearray(original)
    for y in range(top, bottom):
        for x in range(left, right):
            color = image.getpixel((x-left,y-top))
            if color not in cache:
                target = premult(color)
                cache[color] = min(allowed, key=lambda i:
                    sum((a-b)**2 for a,b in zip(target,palette[i])))
            data[off+order[y*width+x]] = cache[color]
    return bytes(data)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['decode','encode'])
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--image', type=Path)
    args = ap.parse_args()
    if args.mode == 'decode': decode(args.source.read_bytes()).save(args.output)
    else:
        if not args.image: ap.error('encode requires --image')
        args.output.write_bytes(encode(args.source.read_bytes(),Image.open(args.image)))
