"""Extract named files from a Skyrim SE BSA (v105, LZ4 frame compression) - pure Python.
Usage: bsa_extract.py <bsa> <out_dir> <internal\\path> [...]"""
import struct, sys, os


def lz4_block(src, out, i, end):
    while i < end:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255: break
        out += src[i:i + lit]; i += lit
        if i >= end: break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4
        start = len(out) - off
        for k in range(ml):
            out.append(out[start + k])
    return out


def lz4_frame(src):
    assert struct.unpack_from('<I', src, 0)[0] == 0x184D2204, 'not an LZ4 frame'
    flg = src[4]; i = 6
    if flg & 0x08: i += 8          # content size
    if flg & 0x01: i += 4          # dict id
    i += 1                         # header checksum
    out = bytearray()
    while True:
        bs = struct.unpack_from('<I', src, i)[0]; i += 4
        if bs == 0: break
        if bs & 0x80000000:
            n = bs & 0x7FFFFFFF; out += src[i:i + n]; i += n
        else:
            lz4_block(src, out, i, i + bs); i += bs
        if flg & 0x10: i += 4      # block checksum
    return bytes(out)


def entries(b):
    magic, ver, off, flags, nfold, nfile, lfold, lfile, ftype = struct.unpack_from('<4sIIIIIIII', b, 0)
    assert magic == b'BSA\0' and ver == 105
    p = off; folders = []
    for _ in range(nfold):
        h, cnt, _pad, foff = struct.unpack_from('<QIIQ', b, p); folders.append(cnt); p += 24
    recs = []
    for cnt in folders:
        ln = b[p]; name = b[p + 1:p + ln].decode('cp1252'); p += 1 + ln
        for k in range(cnt):
            h, size, foff = struct.unpack_from('<QII', b, p); p += 16
            recs.append([name, size, foff])
    names = b[p:p + lfile].split(b'\0')
    for r, n in zip(recs, names):
        r[0] = r[0] + chr(92) + n.decode('cp1252')
    return flags, recs


if __name__ == '__main__':
    bsa, out_dir = sys.argv[1], sys.argv[2]
    want = {w.lower() for w in sys.argv[3:]}
    b = open(bsa, 'rb').read()
    flags, recs = entries(b)
    for path, size, foff in recs:
        if path.lower() not in want: continue
        comp = bool(flags & 4) ^ bool(size & 0x40000000)
        size &= 0x3FFFFFFF
        data = b[foff:foff + size]
        if flags & 0x100:  # embedded name
            ln = data[0]; data = data[1 + ln:]
        if comp:
            data = lz4_frame(data[4:])
        dst = os.path.join(out_dir, path.replace(chr(92), os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        print('extracted', path, len(data))
