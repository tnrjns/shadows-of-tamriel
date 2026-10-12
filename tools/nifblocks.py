"""Minimal Skyrim SE NIF header reader: block types, sizes, offsets and the string table (no block parsing).
Usage as a script: python nifblocks.py <file.nif>   (lists the collision blocks)"""
import struct, sys


def header(path):
    d = open(path, 'rb').read()
    i = d.index(b'\n') + 1
    ver, = struct.unpack_from('<I', d, i); i += 4; i += 1  # version, endian
    uv, nb = struct.unpack_from('<II', d, i); i += 8
    uv2, = struct.unpack_from('<I', d, i); i += 4
    for _ in range(3):  # author, process script, export script (byte-length strings)
        l = d[i]; i += 1 + l
    if uv2 >= 130:
        l = d[i]; i += 1 + l  # max filepath
    nt, = struct.unpack_from('<H', d, i); i += 2
    types = []
    for _ in range(nt):
        l, = struct.unpack_from('<I', d, i); types.append(d[i + 4:i + 4 + l].decode()); i += 4 + l
    bt = struct.unpack_from('<%dH' % nb, d, i); i += 2 * nb
    bs = struct.unpack_from('<%dI' % nb, d, i); i += 4 * nb
    ns, ml = struct.unpack_from('<II', d, i); i += 8
    strs = []
    for _ in range(ns):
        l, = struct.unpack_from('<I', d, i); strs.append(d[i + 4:i + 4 + l].decode(errors='replace')); i += 4 + l
    ng, = struct.unpack_from('<I', d, i); i += 4 + 4 * ng
    offs = []
    o = i
    for s in bs:
        offs.append(o); o += s
    return d, [types[t & 0x7fff] for t in bt], bs, offs, strs


if __name__ == '__main__':
    d, ty, bs, offs, strs = header(sys.argv[1])
    for k, (t, s) in enumerate(zip(ty, bs)):
        if t.startswith('bhk') or 'Collision' in t:
            print(k, t, s)
    print(len(ty), 'blocks', 'end', offs[-1] + bs[-1], len(d))
