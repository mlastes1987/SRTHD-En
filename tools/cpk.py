#!/usr/bin/env python3
"""CRI CPK (@UTF) archive tool for Super Robot Taisen 1 HD (NPJB00514).

Layout confirmed against CriPakTools (C#) reference implementation:
  @UTF table: magic, table_size, rows_off, strings_off, data_off  (offsets
  relative to table_start + 8), table_name, ncols(i16), row_len(i16),
  nrows(i32).  Column entry = u8 flags + u32 name_offset (a flags byte of 0
  means the writer padded the flag field to 4 bytes).

Usage:
  python cpk.py list    <archive.cpk>
  python cpk.py extract <archive.cpk> <outdir>
  python cpk.py build   <indir> <archive.cpk> [--template <orig.cpk>]
                        [--only <id,id,...>] [--recompress-all] [--install]
  python cpk.py verify  <a.cpk> <b.cpk>

`build` writes a complete archive: it regenerates the ITOC (including the
DataL/DataH split and the "ITOC" header), re-compresses only the files named
by <indir> (narrow it further with --only 12,34), copies every other entry's
original byte stream, and patches the header row (ContentOffset, ContentSize,
ItocSize, Files and the two size totals).  Entries that compress larger than
they started are stored raw (the decoder keys off the CRILAYLA magic).

`verify` decompresses both archives and compares every payload, so a repack is
only accepted when the game would see identical data (a build runs the same
check automatically and refuses to install a mismatch).  --install copies the
result into the RPCS3 game directory, keeping the untouched archive as
<name>.orig.
"""
import os
import struct
import sys

T_U8, T_U16, T_U32, T_U64, T_F32, T_U64B, T_U64C, T_F32B = range(8)
TYPE_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4}


def _cstr(data, off):
    end = data.index(b"\x00", off)
    return data[off:end].decode("utf-8", "replace")


class Column:
    __slots__ = ("flags", "type", "storage", "name")

    def __init__(self, flags, name):
        self.flags = flags
        self.type = flags & 0x0F
        self.storage = flags & 0xF0
        self.name = name


class UTF:
    def __init__(self):
        self.columns = []
        self.rows = []
        self.table_name = ""
        self.row_len = 0

    @classmethod
    def read(cls, data, off):
        if data[off:off + 4] != b"@UTF":
            raise ValueError("no @UTF at %#x" % off)
        base = off + 8
        table_size, rows_off, strings_off, data_off, name_off = struct.unpack_from(
            ">IIIII", data, off + 4)
        ncols, row_len = struct.unpack_from(">hh", data, off + 24)
        nrows = struct.unpack_from(">i", data, off + 28)[0]
        strings = base + strings_off

        t = cls()
        t.row_len = row_len
        t.table_name = _cstr(data, strings + name_off)
        p = off + 32
        for _ in range(ncols):
            flags = data[p]
            p += 1
            if flags == 0:
                p += 3          # 4-byte aligned flag field
                flags = data[p]
                p += 1
            noff = struct.unpack_from(">I", data, p)[0]
            p += 4
            t.columns.append(Column(flags, _cstr(data, strings + noff)))

        rows_start = base + rows_off
        for i in range(nrows):
            q = rows_start + i * row_len
            row = {}
            for c in t.columns:
                if c.storage != 0x50:
                    row[c.name] = None
                    continue
                ty = c.type
                if ty in (0, 1):
                    row[c.name] = data[q]
                    q += 1
                elif ty in (2, 3):
                    row[c.name] = struct.unpack_from(">H", data, q)[0]
                    q += 2
                elif ty in (4, 5):
                    row[c.name] = struct.unpack_from(">I", data, q)[0]
                    q += 4
                elif ty in (6, 7):
                    row[c.name] = struct.unpack_from(">Q", data, q)[0]
                    q += 8
                elif ty == 8:
                    row[c.name] = struct.unpack_from(">f", data, q)[0]
                    q += 4
                elif ty == 10:
                    rel = struct.unpack_from(">I", data, q)[0]
                    q += 4
                    row[c.name] = _cstr(data, strings + rel)
                elif ty == 11:
                    rel, ln = struct.unpack_from(">II", data, q)
                    q += 8
                    row[c.name] = data[base + data_off + rel:base + data_off + rel + ln]
                else:
                    raise ValueError("bad column type %#x" % ty)
            t.rows.append(row)
        return t


# ------------------------------------------------------------------ CPK
class Cpk:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        if self.data[:4] != b"CPK ":
            raise ValueError("%s is not a CPK archive" % path)
        self.header = UTF.read(self.data, 0x10)
        h = self.header.rows[0]
        # offsets in the header table are already absolute here after parsing
        self.content_offset = h.get("ContentOffset")
        self.align = h.get("Align") or 16
        self.has_names = False
        toc_off = h.get("TocOffset")
        if toc_off:
            self.toc = UTF.read(self.data, toc_off)
            self.files = [r for r in self.toc.rows if r.get("FileName") is not None]
            self.has_names = bool(self.files)
        if not self.has_names:
            # ID-based archive: sizes live in the split ITOC, and the payload
            # is laid out sequentially from ContentOffset in ID order.
            self.toc = None
            self.files = self._read_itoc()

    def _read_itoc(self):
        h = self.header.rows[0]
        itoc_off = h.get("ItocOffset")
        rel = self.data.find(b"@UTF", itoc_off, itoc_off + 0x40)
        if rel < 0:
            raise ValueError("no ITOC table at %#x" % itoc_off)
        info = UTF.read(self.data, rel)
        rows = []
        for key in ("DataL", "DataH"):
            blob = info.rows[0].get(key)
            if not blob:
                continue
            sub = UTF.read(blob, 0)
            rows.extend(sub.rows)
        sizes = {r["ID"]: r for r in rows}
        pos = self.content_offset
        files = []
        for fid in sorted(sizes):
            r = sizes[fid]
            files.append({
                "FileName": "%05d" % fid,
                "Offset": pos,
                "FileSize": r["FileSize"],
                "ExtractSize": r["ExtractSize"],
            })
            pos += (r["FileSize"] + self.align - 1) // self.align * self.align
        return files

    def extract_all(self, outdir):
        n = 0
        for row in self.files:
            if "Offset" in row:
                off = row["Offset"]
            else:
                off = self.content_offset + row["FileOffset"]
            blob = self.data[off:off + row["FileSize"]]
            if blob[:8] == b"CRILAYLA":
                blob = crilayla_decompress(blob)
            name = row["FileName"].replace("\\", "/").lstrip("/")
            if not os.path.splitext(name)[1]:
                name += ".bin"
            dst = os.path.join(outdir, name)
            os.makedirs(os.path.dirname(dst) or outdir, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(blob)
            n += 1
        return n


    def payload(self, row):
        off = row.get("Offset")
        if off is None:
            off = self.content_offset + row["FileOffset"]
        return self.data[off:off + row["FileSize"]]

    def rebuild(self, replacements, out_path, log=print, recompress_all=False):
        """Write a new archive with `replacements` (id -> uncompressed bytes).

        Untouched entries keep their original byte stream, so editing one file
        costs one compression and the rest of the archive is copied verbatim.
        `recompress_all` re-encodes every entry through this module's encoder
        instead, which is how the encoder itself gets tested in game.
        The header, the ITOC and every inferred offset are regenerated.
        """
        align = self.align or 16
        header = self.header.rows[0]
        itoc_off = header["ItocOffset"]

        entries = []
        stats = []
        recompressed = 0
        for row in self.files:
            fid = int(row["FileName"].split(".")[0])
            if fid in replacements or recompress_all:
                raw = replacements.get(fid)
                if raw is None:
                    raw = self.payload(row)
                    if raw[:8] == b"CRILAYLA":
                        raw = crilayla_decompress(raw)
                # The codec stores the first 0x100 bytes verbatim, so anything
                # that small has to be stored raw.
                packed = crilayla_compress(raw) if len(raw) > 0x100 else b""
                if packed and len(packed) < len(raw):
                    blob, size, extract = packed, len(packed), len(raw)
                else:
                    blob, size, extract = raw, len(raw), len(raw)
                recompressed += 1
                if fid in replacements:
                    stats.append((fid, row["FileSize"], len(blob), len(raw),
                                  blob is packed))
            else:
                blob = self.payload(row)
                size, extract = row["FileSize"], row["ExtractSize"]
            entries.append((fid, blob, size, extract))

        itoc = build_itoc([(fid, size, extract) for fid, _b, size, extract in entries])
        itoc_size = len(itoc)      # the originals store the exact length here
        # Keep the original content position whenever the new ITOC still fits in
        # front of it.  An edit that does not change any size then reproduces the
        # archive byte for byte, which is the cheapest thing to trust.
        content_off = header["ContentOffset"]
        if content_off < _align(itoc_off + itoc_size, 0x20):
            content_off = _align(itoc_off + itoc_size, 0x20)

        buf = bytearray(self.data[:itoc_off])
        buf += itoc
        buf += b"\x00" * (content_off - len(buf))
        end = content_off
        for _fid, blob, _size, _extract in entries:
            buf += blob
            end = len(buf)
            buf += b"\x00" * (_align(len(blob), align) - len(blob))
        content_size = len(buf) - content_off
        del buf[end:]              # the last entry is not padded on disk

        patch = {
            "ContentOffset": content_off,
            "ContentSize": content_size,
            "ItocSize": itoc_size,
            "EnabledPackedSize": sum(e[3] for e in entries),
            "EnabledDataSize": sum(e[2] for e in entries),
            "Files": len(entries),
        }
        for name, (ctype, pos) in _header_slots(self.data).items():
            if name not in patch:
                continue
            fmt = {4: ">I", 6: ">Q"}.get(ctype)
            if fmt is None:
                raise ValueError("unexpected header column type %d for %s" % (ctype, name))
            struct.pack_into(fmt, buf, pos, patch[name])

        with open(out_path, "wb") as f:
            f.write(buf)
        for fid, before, after, raw_len, compressed in stats:
            log("  replaced %05d: %d -> %d bytes (%s), %d raw" %
                (fid, before, after, "crilayla" if compressed else "stored", raw_len))
        return {"path": out_path, "bytes": len(buf), "content": content_size,
                "itoc": itoc_size, "replaced": stats, "recompressed": recompressed}


def compare(archive_a, archive_b, only=None):
    """Return [(id, reason)] for every entry that differs between two archives.

    `only` restricts the comparison to those ids, which is what a build wants:
    replaced entries are expected to differ and are checked against their input
    instead.
    """
    problems = []
    rows_a = {int(r["FileName"].split(".")[0]): r for r in archive_a.files}
    rows_b = {int(r["FileName"].split(".")[0]): r for r in archive_b.files}
    if sorted(rows_a) != sorted(rows_b):
        problems.append((-1, "entry ids differ"))
    for fid in sorted(set(rows_a) & set(rows_b)):
        if only is not None and fid not in only:
            continue
        a, b = rows_a[fid], rows_b[fid]
        if a["ExtractSize"] != b["ExtractSize"]:
            problems.append((fid, "extract size %d != %d" %
                             (a["ExtractSize"], b["ExtractSize"])))
            continue
        da, db = archive_a.payload(a), archive_b.payload(b)
        if da[:8] == b"CRILAYLA":
            da = crilayla_decompress(da)
        if db[:8] == b"CRILAYLA":
            db = crilayla_decompress(db)
        if da != db:
            where = next((i for i, (x, y) in enumerate(zip(da, db)) if x != y), None)
            problems.append((fid, "content differs at %s" % where))
    return problems


def crilayla_decompress(data):
    """CRILAYLA (CRI Layla) codec as implemented by CriPakTools.

    Layout: 16-byte header, reverse-order bitstream, then a plain 0x100-byte
    prefix of the output at the very end of the entry.
    """
    assert data[:8] == b"CRILAYLA"
    size, head_off = struct.unpack_from("<II", data, 8)
    out = bytearray(size + 0x100)
    out[:0x100] = data[head_off + 0x10:head_off + 0x10 + 0x100]

    pos = len(data) - 0x100 - 1
    bit_pool = 0
    bits_left = 0

    def bits(n):
        nonlocal pos, bit_pool, bits_left
        v = 0
        got = 0
        while got < n:
            if bits_left == 0:
                bit_pool = data[pos]
                bits_left = 8
                pos -= 1
            take = min(bits_left, n - got)
            v = (v << take) | ((bit_pool >> (bits_left - take)) & ((1 << take) - 1))
            bits_left -= take
            got += take
        return v

    out_end = 0x100 + size - 1
    written = 0
    vle_lens = (2, 3, 5, 8)
    while written < size:
        if bits(1):
            backref = out_end - written + bits(13) + 3
            length = 3
            level = 0
            while level < len(vle_lens):
                part = bits(vle_lens[level])
                length += part
                if part != (1 << vle_lens[level]) - 1:
                    break
                level += 1
            if level == len(vle_lens):
                while True:
                    part = bits(8)
                    length += part
                    if part != 255:
                        break
            for _ in range(length):
                if written >= size:
                    break
                out[out_end - written] = out[backref]
                backref -= 1
                written += 1
        else:
            out[out_end - written] = bits(8)
            written += 1
    return bytes(out)


# ------------------------------------------------------- CRILAYLA compression
_VLE_WIDTHS = (2, 3, 5, 8)


class _BitWriter:
    """Write bits MSB-first; the encoder reverses the bytes at the end because
    the decoder walks the bitstream backwards from the byte before the literal
    prefix."""

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def bits(self, value, count):
        for i in range(count - 1, -1, -1):
            self.acc = (self.acc << 1) | ((value >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc = 0
                self.n = 0

    def finish(self):
        if self.n:
            self.out.append(self.acc << (8 - self.n))
            self.acc = self.n = 0
        return bytes(self.out)


def _write_length(bw, extra):
    """Inverse of the decoder's length VLE: 2,3,5,8-bit parts, then 8-bit runs.
    A part equal to its maximum continues to the next width."""
    for width in _VLE_WIDTHS:
        top = (1 << width) - 1
        if extra >= top:
            bw.bits(top, width)
            extra -= top
        else:
            bw.bits(extra, width)
            return
    while extra >= 255:
        bw.bits(255, 8)
        extra -= 255
    bw.bits(extra, 8)


def crilayla_compress(data, max_distance=8194):
    """Encode bytes as a CRILAYLA entry; `crilayla_decompress` reverses it.

    The decoder fills the output backwards, so the encoder walks the input in
    reverse.  The first 0x100 bytes are stored verbatim at the end of the entry;
    the declared size excludes them.  Symbol k writes file offset n-1-k and a
    match at distance D reads offset n-1-k+D, so in reverse-index terms source
    and destination advance together: it is a plain forward LZ match on the
    reversed bytes, found greedily with a table of 3-byte contexts.  Matches may
    overlap their own source (L > D); the decoder copies byte by byte, which is
    exactly a run-length match.  The distance field is 13 bits and the decoder
    adds 3, so the farthest reachable match is 8194 bytes ahead.
    """
    n = len(data)
    if n <= 0x100:
        raise ValueError("CRILAYLA needs more than 0x100 bytes")
    size = n - 0x100
    rev = data[::-1]
    index = {}
    bw = _BitWriter()
    k = 0

    def remember(pos):
        if pos + 2 >= size:
            return
        key = (rev[pos], rev[pos + 1], rev[pos + 2])
        bucket = index.get(key)
        if bucket is None:
            index[key] = [pos]
        else:
            bucket.append(pos)
            if len(bucket) > 8:
                del bucket[0]

    while k < size:
        best_len = 0
        best_dist = 0
        if k + 2 < size:
            key = (rev[k], rev[k + 1], rev[k + 2])
            bucket = index.get(key)
            if bucket:
                while bucket and k - bucket[0] > max_distance:
                    del bucket[0]
                for src in reversed(bucket):
                    dist = k - src
                    if dist < 3:
                        continue
                    length = 3
                    limit = min(0xFFFF, size - k)
                    while length < limit and rev[k + length] == rev[src + length]:
                        length += 1
                    if length > best_len:
                        best_len, best_dist = length, dist
                        if length >= 64:
                            break

        if best_len >= 3:
            bw.bits(1, 1)
            bw.bits(best_dist - 3, 13)
            _write_length(bw, best_len - 3)
            for step in range(best_len):
                remember(k + step)
            k += best_len
        else:
            bw.bits(0, 1)
            bw.bits(rev[k], 8)
            remember(k)
            k += 1

    body = bw.finish()[::-1]
    head = b"CRILAYLA" + struct.pack("<II", size, len(body))
    return head + body + data[:0x100]


# ------------------------------------------------------------------ UTF writer
_UTF_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4,
             10: 4, 11: 8}


def _align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def build_utf(name, columns, rows):
    """Serialise a @UTF table the way the CRI writer does.

    columns: [(name, type)]; rows: [tuple].  Type 10 values are strings, type 11
    values are byte strings collected into the table's data region.  Offsets are
    relative to table_start + 8 (the "base"), which is what Cpk's reader assumes
    and what the originals use.  A table with no rows is written with constant
    columns, exactly as the originals do.
    """
    empty = not rows
    storage = 0x10 if empty else 0x50
    strings = bytearray(b"<NULL>\x00")
    name_off = len(strings)
    strings += name.encode("utf-8") + b"\x00"
    col_off = []
    for cname, _ctype in columns:
        col_off.append(len(strings))
        strings += cname.encode("utf-8") + b"\x00"

    str_off = {}
    for ri, row in enumerate(rows):
        for ci, (_cname, ctype) in enumerate(columns):
            if ctype == 10:
                str_off[(ri, ci)] = len(strings)
                strings += str(row[ci]).encode("utf-8") + b"\x00"

    data = bytearray()
    data_off = {}
    for ri, row in enumerate(rows):
        for ci, (_cname, ctype) in enumerate(columns):
            if ctype == 11:
                data_off[(ri, ci)] = (len(data), len(row[ci]))
                data += row[ci]

    row_len = 0 if empty else sum(_UTF_SIZE[ctype] for _n, ctype in columns)
    rows_off = 24 + 5 * len(columns)
    strings_off = rows_off + row_len * len(rows)
    strings_end = strings_off + len(strings)
    data_start = _align(strings_end, 8)   # the originals pad here even with no data
    table_size = data_start + len(data)

    out = bytearray(struct.pack(">4sIIIIIhhi", b"@UTF", table_size, rows_off,
                                strings_off, data_start, name_off,
                                len(columns), row_len, len(rows)))
    for (cname, ctype), off in zip(columns, col_off):
        out.append(ctype | storage)
        out += struct.pack(">I", off)

    for ri, row in enumerate(rows):
        for ci, (_cname, ctype) in enumerate(columns):
            value = row[ci]
            if ctype == 10:
                out += struct.pack(">I", str_off[(ri, ci)])
            elif ctype == 11:
                off, length = data_off[(ri, ci)]
                out += struct.pack(">II", off, length)
            elif ctype in (0, 1):
                out += struct.pack(">B", value)
            elif ctype in (2, 3):
                out += struct.pack(">H", value)
            elif ctype in (4, 5):
                out += struct.pack(">I", value)
            elif ctype in (6, 7):
                out += struct.pack(">Q", value)
            elif ctype == 8:
                out += struct.pack(">f", value)
            else:
                raise ValueError("unsupported column type %d" % ctype)

    out += strings
    out += b"\x00" * (data_start - strings_end)
    out += data
    return bytes(out)


def build_itoc(entries):
    """entries: [(id, file_size, extract_size)] -> full ITOC region bytes.

    Small entries live in the u16 DataL table, the rest in DataH; an entry has
    to fit both sizes in 16 bits to go low, which is the split the originals
    use (KDATA 161 is 780942/780942 and sits in DataH).
    """
    low_ids = {e[0] for e in entries if e[1] <= 0xFFFF and e[2] <= 0xFFFF}
    low = [e for e in entries if e[0] in low_ids]
    high = [e for e in entries if e[0] not in low_ids]
    data_l = build_utf("CpkItocL", [("ID", 2), ("FileSize", 2), ("ExtractSize", 2)],
                       low)
    data_h = build_utf("CpkItocH", [("ID", 2), ("FileSize", 4), ("ExtractSize", 4)],
                       high)
    info = build_utf("CpkItocInfo",
                     [("FilesL", 4), ("FilesH", 4), ("DataL", 11), ("DataH", 11)],
                     [(len(low), len(high), data_l, data_h)])
    # The "ITOC" stub is little-endian even though the tables after it are
    # big-endian: 49 54 4f 43 | ff 00 00 00 | 50 01 00 00 | 00 00 00 00.
    return struct.pack("<4sIII", b"ITOC", 0xFF, len(info), 0) + info


def _header_slots(data):
    """Map header column name -> (type, byte offset within the row)."""
    off = 0x10
    base = off + 8
    _ts, rows_off, strings_off, _do, _no = struct.unpack_from(">IIIII", data, off + 4)
    ncols, _row_len = struct.unpack_from(">hh", data, off + 24)
    strings = base + strings_off
    p = off + 32
    cols = []
    for _ in range(ncols):
        flags = data[p]
        p += 1
        if flags == 0:
            p += 3
            flags = data[p]
            p += 1
        name_off = struct.unpack_from(">I", data, p)[0]
        p += 4
        end = data.index(b"\x00", strings + name_off)
        cols.append((flags, data[strings + name_off:end].decode("utf-8", "replace")))
    slots = {}
    q = base + rows_off
    for flags, name in cols:
        if (flags & 0xF0) != 0x50:
            continue
        slots[name] = (flags & 0x0F, q)
        q += _UTF_SIZE[flags & 0x0F]
    return slots


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "list":
        cpk = Cpk(argv[2])
        print("content_offset=%#x  files=%d  total=%d" %
              (cpk.content_offset, len(cpk.files), len(cpk.data)))
        print("%-48s %10s %10s %s" % ("FileName", "Offset", "FileSize", "ExtractSize"))
        for r in cpk.files:
            off = r.get("Offset", r.get("FileOffset"))
            print("%-48s %10d %10d %s" % (r["FileName"], off, r["FileSize"],
                                          r.get("ExtractSize")))
        return 0
    if cmd == "extract":
        cpk = Cpk(argv[2])
        n = cpk.extract_all(argv[3])
        print("extracted %d files -> %s" % (n, argv[3]))
        return 0
    if cmd == "build":
        return cmd_build(argv[2:])
    if cmd == "verify":
        if len(argv) < 4:
            print("usage: cpk.py verify <a.cpk> <b.cpk>")
            return 1
        a, b = Cpk(argv[2]), Cpk(argv[3])
        problems = compare(a, b)
        for fid, why in problems:
            print("  %s %s" % ("%05d" % fid if fid >= 0 else "-----", why))
        print("%d entries, %d problems" % (len(a.files), len(problems)))
        return 1 if problems else 0
    print("unknown command:", cmd)
    return 1


from project_paths import RPCS3_DIR
RPCS3_USRDIR = str(RPCS3_DIR / "dev_hdd0/game/NPJB00514/USRDIR") if RPCS3_DIR else None


def read_replacements(indir):
    """Collect <indir>/NNNNN[.ext] files as {id: bytes}."""
    found = {}
    names = {}
    for name in sorted(os.listdir(indir)):
        path = os.path.join(indir, name)
        if not os.path.isfile(path):
            continue
        stem = name.split(".")[0]
        if not stem.isdigit():
            continue
        fid=int(stem)
        if fid in names:
            raise ValueError('Duplicate replacement ID %05d: %s and %s. Keep previews and backups in a separate directory.'
                             % (fid,names[fid],name))
        names[fid]=name
        with open(path, "rb") as f:
            found[fid] = f.read()
    return found


def cmd_build(args):
    if len(args) < 2:
        print("usage: cpk.py build <indir> <archive.cpk> --template <orig.cpk>"
              " [--install]")
        return 1
    indir, out_path = args[0], args[1]
    template = out_path if "--template" not in args else args[args.index("--template") + 1]
    install = "--install" in args
    if install and RPCS3_USRDIR is None:
        raise SystemExit("Set SRW_RPCS3_DIR before using --install.")
    if not os.path.isdir(indir):
        print("not a directory:", indir)
        return 1
    if not os.path.isfile(template):
        print("template archive not found:", template)
        return 1

    source = Cpk(template)
    replacements = read_replacements(indir)
    if "--only" in args:
        wanted = {int(x) for x in args[args.index("--only") + 1].split(",") if x.strip()}
        skipped = sorted(set(replacements) - wanted)
        replacements = {k: v for k, v in replacements.items() if k in wanted}
        if skipped:
            print("ignoring %d files not named by --only" % len(skipped))
    known = {int(r["FileName"].split(".")[0]) for r in source.files}
    unknown = sorted(set(replacements) - known)
    if unknown:
        print("ids not in the archive: %s" % ", ".join("%05d" % i for i in unknown))
        return 1

    print("template %s: %d files, content at %#x" %
          (template, len(source.files), source.content_offset))
    result = source.rebuild(replacements, out_path,
                            recompress_all="--recompress-all" in args)
    built = Cpk(out_path)
    print("wrote %s: %d bytes, content %d at %#x, itoc %d, %d replaced, %d recompressed" %
          (result["path"], result["bytes"], result["content"],
           built.content_offset, result["itoc"], len(replacements),
           result["recompressed"]))

    untouched = known - set(replacements)
    problems = compare(source, built, only=untouched)
    built_rows = {int(r["FileName"].split(".")[0]): r for r in built.files}
    for fid, want in replacements.items():
        row = built_rows.get(fid)
        if row is None:
            problems.append((fid, "missing from the rebuilt archive"))
            continue
        got = built.payload(row)
        if got[:8] == b"CRILAYLA":
            got = crilayla_decompress(got)
        if got != want:
            where = next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), None)
            problems.append((fid, "replacement did not round-trip (differs at %s)" % where))
    if problems:
        for fid, why in problems:
            print("  %s %s" % ("%05d" % fid if fid >= 0 else "-----", why))
        print("VERIFY FAILED")
        return 1
    print("verify: %d untouched payloads identical, %d replacements round-trip" %
          (len(untouched), len(replacements)))

    if install:
        import shutil
        normalized = template.replace("\\", "/")
        low = normalized.lower()
        marker = "/usrdir/"
        paths = {
            "kdataps3.cpk": "DATA/KURODATA/KDATAPS3.CPK",
            "tpackps3.cpk": "DATA/TABATA/TPACKPS3.CPK",
            "piece1stps3.cpk": "DATA/PIECE/PIECE1STPS3.CPK",
            "map1stps3.cpk": "DATA/MAP/MAP1STPS3.CPK",
        }
        rel = normalized[low.index(marker)+len(marker):] if marker in low else paths.get(os.path.basename(low))
        if rel is None:
            raise SystemExit("Cannot infer the installed archive path; use the canonical original archive as --template.")
        dst = os.path.join(RPCS3_USRDIR, rel)
        dst = os.path.abspath(dst)
        if os.path.commonpath([dst, os.path.abspath(RPCS3_USRDIR)]) != os.path.abspath(RPCS3_USRDIR):
            raise SystemExit("Archive destination leaves the configured USRDIR.")
        if not os.path.exists(dst + ".orig"):
            shutil.copy2(dst, dst + ".orig")
            print("backed up original ->", dst + ".orig")
        shutil.copy2(out_path, dst)
        print("installed ->", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
