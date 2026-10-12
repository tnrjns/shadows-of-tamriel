"""Read annotation tracks from any 64-bit Skyrim SE hkaAnimation (spline or interleaved)."""
import sys, struct
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\hkx')
import anim_skyrim as A

def read(path):
    d = open(path, 'rb').read()
    secs = A._parse_hkx_sections(d); ds = secs['__data__']; base = ds['offset']
    fx = A._parse_local_fixups(d, ds)
    objs = A._parse_virtual_fixups(d, ds, secs['__classnames__']['offset'])
    rel = next(r for r, c in objs if c.startswith('hka') and c.endswith('Animation'))
    dur = struct.unpack_from('<f', d, base + rel + 20)[0]
    ntr = struct.unpack_from('<I', d, base + rel + 48)[0]
    out = []
    tr0 = fx.get(rel + 40)
    for t in range(ntr if tr0 is not None else 0):
        trel = tr0 + 24 * t
        n = struct.unpack_from('<I', d, base + trel + 16)[0]
        arr = fx.get(trel + 8)
        for k in range(n if arr is not None else 0):
            arel = arr + 16 * k
            tm = struct.unpack_from('<f', d, base + arel)[0]
            sp = fx.get(arel + 8)
            out.append((t, tm, A._read_null_string(d, base + sp) if sp is not None else ''))
    return dur, out

if __name__ == '__main__':
    for p in sys.argv[1:]:
        dur, ann = read(p)
        print(p.split('/')[-1], round(dur, 3), len(ann), ann[:6])
