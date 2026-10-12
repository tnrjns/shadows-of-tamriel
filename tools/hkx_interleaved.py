"""Read / patch 64-bit Skyrim SE hkaInterleavedUncompressedAnimation files (FreeClimb's format).

read(path) -> dict(duration, tracks, frames, transforms[frame][track] = (t xyz, q xyzw, s xyz), blob info)
patch(src, dst, transforms) writes a copy of src with the transform block replaced (same frame and
track count), so every other object in the file (annotations, binding, names) stays byte-identical.
"""
import sys, struct
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\hkx')
import anim_skyrim as A


def _locate(d):
    secs = A._parse_hkx_sections(d); ds = secs['__data__']; base = ds['offset']
    fx = A._parse_local_fixups(d, ds)
    objs = A._parse_virtual_fixups(d, ds, secs['__classnames__']['offset'])
    rel = next(r for r, c in objs if c == 'hkaInterleavedUncompressedAnimation')
    o = base + rel
    dur = struct.unpack_from('<f', d, o + 20)[0]
    ntr = struct.unpack_from('<I', d, o + 24)[0]
    count = struct.unpack_from('<I', d, o + 64)[0]
    start = base + fx[rel + 56]
    return dur, ntr, count, start


def read(path):
    d = open(path, 'rb').read()
    dur, ntr, count, start = _locate(d)
    nfr = count // ntr
    tf = []
    for f in range(nfr):
        row = []
        for t in range(ntr):
            v = struct.unpack_from('<12f', d, start + 48 * (f * ntr + t))
            row.append((v[0:3], v[4:8], v[8:11]))
        tf.append(row)
    return {'duration': dur, 'tracks': ntr, 'frames': nfr, 'transforms': tf}


def patch(src, dst, transforms):
    d = bytearray(open(src, 'rb').read())
    dur, ntr, count, start = _locate(bytes(d))
    nfr = count // ntr
    assert len(transforms) == nfr and all(len(r) == ntr for r in transforms), (len(transforms), nfr)
    for f, row in enumerate(transforms):
        for t, (tr, q, s) in enumerate(row):
            struct.pack_into('<12f', d, start + 48 * (f * ntr + t),
                             tr[0], tr[1], tr[2], 0.0, q[0], q[1], q[2], q[3], s[0], s[1], s[2], 0.0)
    open(dst, 'wb').write(d)


if __name__ == '__main__':
    r = read(sys.argv[1])
    print(r['duration'], r['tracks'], r['frames'])
