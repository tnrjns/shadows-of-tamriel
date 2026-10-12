"""Pack the retargeted free-run clips (build_fr/*.hkx) into AltairFreerun.pack for AltairFreerun.dll's pose player.
Run in Blender (needs PyNifly's anim_skyrim):
  blender -b --factory-startup --python tools/pack_freerun.py -- ac1_clips_fr.json build_fr <out.pack>

Format (little endian):
  'AFR2', u32 bones, bones x (u16 len, name), u32 clips,
  clips x (u16 len, name, f32 duration, u32 frames,
           frames x bones x (f32 qx qy qz qw, f32 tx ty tz)   local transforms on the Skyrim skeleton,
           frames x (f32 forward, f32 up),                      AC1 root displacement in metres (jump direction, up)
           frames x (f32 x, y, z))                              the grip: midpoint of the two middle-finger knuckles
                                                                (the palm, not the wrist), game units, actor space
                                                                (x right, y forward, z up; for hanging on ledges / bars)
"""
import sys, os, json, struct, math
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\hkx')
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tools')
import anim_skyrim as A
from mathutils import Quaternion, Vector
import hkx_skel

args = sys.argv[sys.argv.index('--') + 1:]
CLIPS_JSON, SRC, OUT = args
clips = json.load(open(CLIPS_JSON))['clips']
sk = hkx_skel.load(r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\vanilla_character_skeleton.hkx')
names = list(sk.bones)


def disp_at(keys, t):
    if not keys:
        return (0.0, 0.0, 0.0)
    if t <= keys[0][0]:
        return tuple(keys[0][1:4])
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            u = (t - a[0]) / max(1e-6, b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * u for i in (1, 2, 3))
    return tuple(keys[-1][1:4])


out = bytearray(b'AFR2') + struct.pack('<I', len(names))
for n in names:
    b = n.encode()
    out += struct.pack('<H', len(b)) + b
files = sorted(f[:-4] for f in os.listdir(SRC) if f.endswith('.hkx'))
out += struct.pack('<I', len(files))
for nm in files:
    an = A.load_skyrim_animation(os.path.join(SRC, nm + '.hkx'))
    nf = len(an.tracks[0].rotations)
    dur = an.duration
    b = nm.encode()
    out += struct.pack('<H', len(b)) + b + struct.pack('<fI', dur, nf)
    for f in range(nf):
        for j in range(len(names)):
            if j < len(an.tracks):
                r = an.tracks[j].rotations[f]
                t = an.tracks[j].translations[f]
            else:
                r, t = (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
            out += struct.pack('<7f', r[0], r[1], r[2], r[3], t[0], t[1], t[2])
    # AC1 root displacement (track 00000000), metres: forward = along its own end direction, up = z
    # relative to the clip's first frame (AC1 items store it in item space, not from zero)
    keys = clips[nm]['pos'].get('00000000', [])
    start = disp_at(keys, 0.0)
    end = disp_at(keys, clips[nm]['duration'])
    end = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    h = math.hypot(end[0], end[1])
    dirx, diry = (end[0] / h, end[1] / h) if h > 1e-3 else (0.0, 1.0)
    for f in range(nf):
        x, y, z = disp_at(keys, clips[nm]['duration'] * f / max(1, nf - 1))
        x, y, z = x - start[0], y - start[1], z - start[2]
        out += struct.pack('<2f', x * dirx + y * diry, z)
    # hands: forward kinematics on the Skyrim skeleton
    hl, hr = names.index('NPC L Finger20 [LF20]'), names.index('NPC R Finger20 [RF20]')
    for f in range(nf):
        W, P = [None] * len(names), [None] * len(names)
        for j in range(len(names)):
            if j < len(an.tracks):
                r = an.tracks[j].rotations[f]; t = an.tracks[j].translations[f]
            else:
                r, t = (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
            q = Quaternion((r[3], r[0], r[1], r[2])); v = Vector(t)
            pj = sk.parents[j]
            if pj < 0:
                W[j], P[j] = q, v
            else:
                W[j] = W[pj] @ q; P[j] = P[pj] + W[pj] @ v
        m = (P[hl] + P[hr]) / 2
        out += struct.pack('<3f', m.x, m.y, m.z)
        if f == 0:
            hand0 = m
    print(f'{nm}: hands at frame 0 ({hand0.x:.0f}, {hand0.y:.0f}, {hand0.z:.0f})')
    print(f'{nm}: {nf} frames, {dur:.3f} s, displacement fwd {h:.2f} m up {end[2]:+.2f} m')
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'wb').write(out)
print('wrote', OUT, len(out), 'bytes,', len(names), 'bones')
