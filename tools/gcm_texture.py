"""Decode/encode the actual GCM ARGB texture geometry and Morton layout."""
from pathlib import Path
import struct
from PIL import Image


def offsets(width, height):
    bx, by = width.bit_length()-1, height.bit_length()-1
    assert width == 1 << bx and height == 1 << by
    def spread(value, bits, other):
        return sum(((value >> i) & 1) << (2*i if i < other else i+other)
                   for i in range(bits))
    return ([spread(x, bx, by) for x in range(width)],
            [spread(y, by, bx) << 1 if by <= bx else
             sum(((y >> i) & 1) << (2*i+1 if i < bx else i+bx)
                 for i in range(by)) for y in range(height)])


def decode(data):
    width, height = struct.unpack_from(">HH", data, 0x20)
    fmt = data[0x18]
    assert fmt in (0x85, 0xA5), hex(fmt)
    raw = data[0x80:0x80+width*height*4]
    assert len(raw) == width*height*4
    if fmt == 0x85:
        xs, ys = offsets(width, height)
        linear = bytearray(len(raw))
        for y, yy in enumerate(ys):
            for x, xx in enumerate(xs):
                a, b = (y*width+x)*4, (xx+yy)*4
                linear[a:a+4] = raw[b:b+4]
        raw = bytes(linear)
    return Image.frombytes("RGBA", (width, height), raw, "raw", "ARGB")


def encode(original, im):
    width, height = struct.unpack_from(">HH", original, 0x20)
    assert im.size == (width, height)
    r, g, b, a = im.convert("RGBA").split()
    raw = Image.merge("RGBA", (a,r,g,b)).tobytes()
    if original[0x18] == 0x85:
        xs, ys = offsets(width, height)
        swizzled = bytearray(len(raw))
        for y, yy in enumerate(ys):
            for x, xx in enumerate(xs):
                a, b = (y*width+x)*4, (xx+yy)*4
                swizzled[b:b+4] = raw[a:a+4]
        raw = bytes(swizzled)
    else:
        assert original[0x18] == 0xA5
    return original[:0x80] + raw + original[0x80+len(raw):]


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1])
    im = decode(path.read_bytes())
    output = Path(sys.argv[2])
    im.save(output)
    print(path, im.size, "->", output)
