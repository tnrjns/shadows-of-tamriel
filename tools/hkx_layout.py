"""Print the packfile layout of HKX files (objects, per-object pointer fixup offsets, array counts)."""
import sys, struct
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\hkx')
import anim_skyrim as A
for p in sys.argv[1:]:
    d = open(p, 'rb').read()
    print('==', p.split('/')[-1], 'len', len(d), 'hdr', d[:0x40].hex())
    secs = A._parse_hkx_sections(d); ds = secs['__data__']
    fx = A._parse_local_fixups(d, ds)
    objs = A._parse_virtual_fixups(d, ds, secs['__classnames__']['offset'])
    gl = []
    # global fixups: (src, dstsec, dst) triples of u32 between data2 and data3
    o = ds['data2']
    while o + 12 <= ds['data3']:
        a, b, c = struct.unpack_from('<III', d, o)
        if a != 0xFFFFFFFF: gl.append((a, b, c))
        o += 12
    bounds = [r for r, _ in objs] + [ds['data1'] - ds['offset']]
    for i, (rel, cls) in enumerate(objs):
        end = bounds[i + 1]
        lf = sorted((k - rel, v) for k, v in fx.items() if rel <= k < end)
        gf = sorted((a - rel, c) for a, b, c in gl if rel <= a < end)
        print(f'  {rel:6d} {cls:32s} size {end-rel:5d} local {[k for k,_ in lf]} global {[k for k,_ in gf]}')
        if cls in ('hkaSplineCompressedAnimation', 'hkaAnimationBinding', 'hkaSkeleton', 'hkaAnimationContainer'):
            raw = d[ds['offset'] + rel: ds['offset'] + rel + min(end - rel, 224)]
            print('     raw', raw.hex())
