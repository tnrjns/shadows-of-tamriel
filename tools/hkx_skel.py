"""Read the vanilla SE character skeleton.hkx (64-bit). PyNifly's parser assumes a 16-byte object
header for 64-bit packfiles; SE files use 24, so the hkaSkeleton fields are read here directly."""
import sys, struct
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\hkx')
import anim_skyrim as A
from anim_fo4 import Skeleton, BonePose

def load(path):
    d = open(path, 'rb').read()
    secs = A._parse_hkx_sections(d); ds = secs['__data__']; base = ds['offset']
    fx = A._parse_local_fixups(d, ds)
    objs = A._parse_virtual_fixups(d, ds, secs['__classnames__']['offset'])
    rel = next(r for r, c in objs if c == 'hkaSkeleton')   # first = the animation skeleton
    s = base + rel
    sk = Skeleton()
    sk.name = A._read_null_string(d, base + fx[rel + 24])
    n = struct.unpack_from('<I', d, s + 40)[0]
    pi = base + fx[rel + 32]
    sk.parents = [struct.unpack_from('<h', d, pi + 2 * i)[0] for i in range(n)]
    bo = fx[rel + 48]
    for i in range(struct.unpack_from('<I', d, s + 56)[0]):
        sk.bones.append(A._read_null_string(d, base + fx[bo + 16 * i]))
        sk.lock_translation.append(bool(d[base + bo + 16 * i + 8]))
    po = base + fx[rel + 64]
    for i in range(struct.unpack_from('<I', d, s + 72)[0]):
        v = struct.unpack_from('<12f', d, po + 48 * i)
        sk.reference_pose.append(BonePose(list(v[0:3]), list(v[4:8]), list(v[8:11])))
    return sk

if __name__ == '__main__':
    sk = load(sys.argv[1])
    print(sk.name, len(sk.bones))
    for i, (b, p, r) in enumerate(zip(sk.bones, sk.parents, sk.reference_pose)):
        print(i, b, p, [round(x, 2) for x in r.translation], [round(x, 3) for x in r.rotation])
