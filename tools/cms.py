"""bhkCompressedMeshShapeData reader (Skyrim SE): materials, transforms, big triangles and chunks, plus a chunk's
triangles in Havok space. Used by patch_windmill.py to find collision without matching visible geometry."""
import struct


def parse_cms(d, o):
    r = {}
    bpi, bpw, mw, mi, err = struct.unpack_from('<IIIIf', d, o); o += 20
    r['aabb'] = struct.unpack_from('<8f', d, o); o += 32
    o += 2
    for _ in ('m32', 'm16', 'm8'):
        n, = struct.unpack_from('<I', d, o); o += 4 + 4 * n
    n, = struct.unpack_from('<I', d, o); o += 4
    r['mats'] = [struct.unpack_from('<IBBH', d, o + 8 * k) for k in range(n)]; r['mats_off'] = o; o += 8 * n
    n, = struct.unpack_from('<I', d, o); o += 4  # named materials
    n, = struct.unpack_from('<I', d, o); o += 4
    r['xf'] = [struct.unpack_from('<8f', d, o + 32 * k) for k in range(n)]; o += 32 * n
    n, = struct.unpack_from('<I', d, o); o += 4
    r['bigv'] = [struct.unpack_from('<4f', d, o + 16 * k) for k in range(n)]; o += 16 * n
    n, = struct.unpack_from('<I', d, o); o += 4
    r['bigt'] = [struct.unpack_from('<3HIH', d, o + 12 * k) for k in range(n)]; r['bigt_off'] = o; o += 12 * n
    n, = struct.unpack_from('<I', d, o); o += 4
    ch = []
    for _ in range(n):
        c = {'off': o}
        c['t'] = struct.unpack_from('<4f', d, o); o += 16
        c['mat'], c['ref'], c['xf'] = struct.unpack_from('<IHH', d, o); o += 8
        nv, = struct.unpack_from('<I', d, o); o += 4; c['v'] = struct.unpack_from('<%dH' % nv, d, o); o += 2 * nv
        ni, = struct.unpack_from('<I', d, o); o += 4; c['i'] = struct.unpack_from('<%dH' % ni, d, o); o += 2 * ni
        ns, = struct.unpack_from('<I', d, o); o += 4; c['s'] = struct.unpack_from('<%dH' % ns, d, o); o += 2 * ns
        nw, = struct.unpack_from('<I', d, o); o += 4; o += 2 * nw
        ch.append(c)
    r['chunks'] = ch
    r['end'] = o + 4
    r['err'] = err
    return r


def chunk_tris(r, c):
    err = r['err']; t = c['t']
    vs = [(c['v'][3 * k] * err + t[0], c['v'][3 * k + 1] * err + t[1], c['v'][3 * k + 2] * err + t[2]) for k in range(len(c['v']) // 3)]
    if c['xf'] != 65535 and c['xf'] < len(r['xf']):
        x = r['xf'][c['xf']]; tx = x[:3]; qx, qy, qz, qw = x[4:8]
        def rot(p):
            px, py, pz = p
            cx = qy * pz - qz * py; cy = qz * px - qx * pz; cz = qx * py - qy * px
            cx2 = qy * cz - qz * cy; cy2 = qz * cx - qx * cz; cz2 = qx * cy - qy * cx
            return (px + 2 * (qw * cx + cx2) + tx[0], py + 2 * (qw * cy + cy2) + tx[1], pz + 2 * (qw * cz + cz2) + tx[2])
        vs = [rot(p) for p in vs]
    tris = []; i = 0; idx = c['i']
    for sl in c['s']:
        for k in range(sl - 2):
            tris.append((idx[i + k], idx[i + k + 1], idx[i + k + 2]))
        i += sl
    while i + 2 < len(idx):
        tris.append(idx[i:i + 3]); i += 3
    return vs, tris
