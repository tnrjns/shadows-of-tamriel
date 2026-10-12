"""Remove the invisible wall above the Solitude windmill bridge: the 'spikes' collision body of swindmill.nif
(invisible panels along the bridge railing) is switched to layer L_NONCOLLIDABLE (15). Only the layer bytes of
that rigid body and of its compressed-mesh material change, so the MOPP tree stays valid.
Usage: python tools/patch_windmill.py <in swindmill.nif (SMIM)> <out nif>"""
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nifblocks import header
from cms import parse_cms
d, ty, bs, offs, strs = header(sys.argv[1]); b = bytearray(d)
NONCOLLIDABLE = 15
# the rigid body whose collision object targets the 'spikes' node
for k, t in enumerate(ty):
    if t == 'bhkCollisionObject':
        target, _, body = struct.unpack_from('<iHi', d, offs[k])
        if strs[struct.unpack_from('<i', d, offs[target])[0]] == 'spikes':
            ro = offs[body]; shape = struct.unpack_from('<i', d, ro)[0]
            print('rigid body', body, ty[body], 'layer', d[ro + 4])
            for o in range(ro, ro + 40):                  # havok filter and its copy (layer 3, flags 0x80)
                if d[o] == 3 and d[o + 1] == 0x80:
                    b[o] = NONCOLLIDABLE; print('  filter at +%d' % (o - ro))
            # bhkMoppBvTreeShape -> bhkCompressedMeshShape -> data
            print('  shape', shape, ty[shape])
            data = max(i for i in range(shape) if ty[i] == 'bhkCompressedMeshShapeData')   # written just before it
            print('  data', data)
            r = parse_cms(d, offs[data])
            for m in range(len(r['mats'])):
                o = r['mats_off'] + 8 * m + 4
                print('  cms material', m, 'layer', d[o], '->', NONCOLLIDABLE); b[o] = NONCOLLIDABLE
open(sys.argv[2], 'wb').write(b)
print('wrote', sys.argv[2])
