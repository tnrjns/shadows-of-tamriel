"""Retarget AC1 locomotion clips (ac1_clips.json, from tools/ac1_anim_export) onto the vanilla
Skyrim SE character skeleton and write 64-bit HKX animations.

Run with Blender's Python (mathutils):
  blender -b --factory-startup --python tools/retarget_ac1.py -- <ac1_clips.json> <out_dir>

Method
  * AC FK per frame in animation space (Z-up, facing +Y, metres). AC rest globals are given in
    skeleton space (facing +X), so the rest is rotated 90 deg about Z to compare.
  * Mapped Skyrim bones take the AC bone's world rotation change from rest:
        Q_sky = Q_ac(t) * Q_ac_rest^-1 * Q_sky_rest
    unmapped bones keep their rest local rotation.
  * COM follows the AC root position scaled by leg length (AC hip-ankle vs Skyrim thigh+calf).
  * Two-bone leg IK puts each Skyrim ankle where Altair's ankle is (scaled), with the knee in
    Altair's knee plane, so feet stay planted despite the different rest poses/proportions.
  * Clip length is rescaled so the AC stride matches Skyrim's movement speed (no foot sliding).
"""
import sys, os, json, math
from mathutils import Quaternion, Vector, Matrix

ROOT = r'C:\Users\myste\Downloads\Altair Skyrim Native'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tooling', 'pynifly-29.1.0', 'io_scene_nifly', 'hkx'))
import hkx_skel
import anim_skyrim as A
from anim_fo4 import AnimationData, TrackData, Annotation

args = sys.argv[sys.argv.index('--') + 1:]
CLIPS_JSON, OUT = args[0], args[1]
FPS = 30.0

# Skyrim forward speeds (units/s) from Skyrim.esm MOVT NPC_Default_MT / NPC_Sprinting_MT.
SKY_WALK, SKY_RUN, SKY_SPRINT = 80.1, 370.0, 500.0
JOBS = [  # (AC clip, output files, Skyrim speed or None = keep AC timing, footstep annotation names)
    ('idle_low', ['mt_idle.hkx'], None, None),
    ('walk', ['mt_walkforward.hkx'], SKY_WALK, ('FootLeft', 'FootRight')),
    ('run', ['mt_runforward.hkx'], SKY_RUN, ('FootLeft', 'FootRight')),
    ('sprint', ['mt_sprintforward.hkx'], SKY_SPRINT, ('FootSprintLeft', 'FootSprintRight')),
]

MAP = {
    'NPC COM [COM ]': '2c52cbb0', 'NPC Pelvis [Pelv]': 'ded10611',
    'NPC Spine [Spn0]': '530ec1cb', 'NPC Spine1 [Spn1]': '8f39fa4e', 'NPC Spine2 [Spn2]': '1630abf4',
    'NPC Neck [Neck]': '8023796d', 'NPC Head [Head]': '07c159a2',
    'NPC L Clavicle [LClv]': 'b898b609', 'NPC L UpperArm [LUar]': 'eb830ada',
    'NPC L Forearm [LLar]': '89b93a80', 'NPC L Hand [LHnd]': 'b675f36c',
    'NPC R Clavicle [RClv]': '63d89144', 'NPC R UpperArm [RUar]': '6bb3f727',
    'NPC R Forearm [RLar]': '7257a1aa', 'NPC R Hand [RHnd]': '75f94d30',
    'NPC L Thigh [LThg]': '176183f0', 'NPC L Calf [LClf]': '060df401',
    'NPC L Foot [Lft ]': '58988870', 'NPC L Toe0 [LToe]': '058b96dd',
    'NPC R Thigh [RThg]': '757f1291', 'NPC R Calf [RClf]': '863d09fc',
    'NPC R Foot [Rft ]': '9b14362c', 'NPC R Toe0 [RToe]': 'e556c9be',
}
FINGERS = {
    'L': [['78f4e1ac', 'e1fdb016', '96fa8080'], ['1e679ed0', '876ecf6a', 'f069fffc'],
          ['911fbacf', '0816eb75', '7f11dbe3'], ['d34048cf', '4a491975'], ['f4a6edbc', '6dafbc06', '1aa88c90']],
    'R': [['9829becf', '0120ef75', '7627dfe3'], ['febac1b3', '67b39009', '10b4a09f'],
          ['45445772', 'dc4d06c8', 'ab4a365e'], ['dbf635c5', '42ff647f', '35f854e9'],
          ['147bb2df', '8d72e365', 'fa75d3f3']],
}
for s, chains in FINGERS.items():
    for fi, ch in enumerate(chains):
        for ji, b in enumerate(ch):
            MAP[f'NPC {s} Finger{fi}{ji} [{s}F{fi}{ji}]'] = b
LEGS = {'L': ('NPC L Thigh [LThg]', 'NPC L Calf [LClf]', 'NPC L Foot [Lft ]', '176183f0', '060df401', '58988870'),
        'R': ('NPC R Thigh [RThg]', 'NPC R Calf [RClf]', 'NPC R Foot [Rft ]', '757f1291', '863d09fc', '9b14362c')}

def q_xyzw(q):
    return Quaternion((q[3], q[0], q[1], q[2]))

def to_xyzw(q):
    return [q.x, q.y, q.z, q.w]

# ---- data --------------------------------------------------------------------------
data = json.load(open(CLIPS_JSON))
ac = data['skeleton']
ac_ids = [b['bone_id'] for b in ac]
ac_idx = {b: i for i, b in enumerate(ac_ids)}
Rz90 = Quaternion((0, 0, 1), math.radians(90))
ac_rest_rot_anim = [Rz90 @ q_xyzw(b['global_rot']) for b in ac]

sk = hkx_skel.load(os.path.join(ROOT, 'tooling', 'vanilla_character_skeleton.hkx'))
NB = len(sk.bones)
bi = {n: i for i, n in enumerate(sk.bones)}
rest_t = [Vector(p.translation) for p in sk.reference_pose]
rest_r = [q_xyzw(p.rotation) for p in sk.reference_pose]

def sky_fk(rots_local, trans_local):
    W, P = [None] * NB, [None] * NB
    for j in range(NB):
        p = sk.parents[j]
        if p < 0:
            W[j], P[j] = rots_local[j].copy(), trans_local[j].copy()
        else:
            W[j] = W[p] @ rots_local[j]
            P[j] = P[p] + W[p] @ trans_local[j]
    return W, P
sky_rest_W, sky_rest_P = sky_fk(rest_r, rest_t)

# scale: AC leg (hip->knee->ankle, skeleton rest, metres) vs Skyrim thigh+calf (units)
def acpos(b): return Vector(ac[ac_idx[b]]['global_pos'])
ac_leg = (acpos('060df401') - acpos('176183f0')).length + (acpos('58988870') - acpos('060df401')).length
sky_leg = rest_t[bi['NPC L Calf [LClf]']].length + rest_t[bi['NPC L Foot [Lft ]']].length
S = sky_leg / ac_leg

# ---- sampling ------------------------------------------------------------------------
def sample(keys, t, is_rot):
    if t <= keys[0][0]:
        k = keys[0]
    elif t >= keys[-1][0]:
        k = keys[-1]
    else:
        lo, hi = 0, len(keys) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if keys[mid][0] <= t: lo = mid
            else: hi = mid
        a, b = keys[lo], keys[hi]
        u = (t - a[0]) / max(1e-9, b[0] - a[0])
        if is_rot:
            qa, qb = q_xyzw(a[1:]), q_xyzw(b[1:])
            if qa.dot(qb) < 0: qb = -qb
            return qa.slerp(qb, u)
        return Vector(a[1:]).lerp(Vector(b[1:]), u)
    return q_xyzw(k[1:]) if is_rot else Vector(k[1:])

def ac_pose(clip, t):
    rot, pos = clip['rot'], clip['pos']
    G, P = [None] * len(ac), [None] * len(ac)
    for i, b in enumerate(ac):
        bid = b['bone_id']
        lr = sample(rot[bid], t, True) if bid in rot else q_xyzw(b['local_rot'])
        lp = sample(pos[bid], t, False) if bid in pos else Vector(b['local_pos'])
        p = b['parent']
        if p < 0:
            G[i], P[i] = lr, lp
        else:
            G[i] = G[p] @ lr
            P[i] = P[p] + G[p] @ lp
    return G, P

def swing(v_from, v_to):
    return v_from.normalized().rotation_difference(v_to.normalized())

def retarget_frame(clip, t):
    G, P = ac_pose(clip, t)
    W = [None] * NB
    # world rotations
    for j in range(NB):
        name = sk.bones[j]; p = sk.parents[j]
        src = MAP.get(name)
        if src is not None and src in ac_idx:
            i = ac_idx[src]
            W[j] = G[i] @ ac_rest_rot_anim[i].inverted() @ sky_rest_W[j]
        else:
            W[j] = (W[p] @ rest_r[j]) if p >= 0 else rest_r[j].copy()
    root_i = ac_idx['2c52cbb0']
    com_world = P[root_i] * S
    # positions with rest bone lengths (COM moved)
    def positions():
        Pp = [None] * NB
        for j in range(NB):
            p = sk.parents[j]
            if sk.bones[j] == 'NPC COM [COM ]':
                Pp[j] = com_world.copy()
            elif p < 0:
                Pp[j] = rest_t[j].copy()
            else:
                Pp[j] = Pp[p] + W[p] @ rest_t[j]
        return Pp
    Pp = positions()
    # leg IK
    for side, (thg, clf, ft, a_thg, a_clf, a_ft) in LEGS.items():
        jt, jc, jf = bi[thg], bi[clf], bi[ft]
        H = Pp[jt]
        goal = P[ac_idx[a_ft]] * S
        pole = P[ac_idx[a_clf]] * S
        L1, L2 = rest_t[jc].length, rest_t[jf].length
        d_vec = goal - H
        d = min(d_vec.length, (L1 + L2) * 0.9995)
        dirv = d_vec.normalized()
        cos_a = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
        a = math.acos(max(-1.0, min(1.0, cos_a)))
        pv = pole - H
        bend = (pv - dirv * pv.dot(dirv))
        bend = bend.normalized() if bend.length > 1e-6 else Vector((0, 1, 0))
        K = H + (dirv * math.cos(a) + bend * math.sin(a)) * L1
        A_ = H + dirv * d
        # thigh: rotate so its child (knee) lands on K
        cur_k = H + W[jt] @ rest_t[jc]
        W[jt] = swing(cur_k - H, K - H) @ W[jt]
        # calf world rot: delta keeps its twist, swing so the ankle lands on A_
        cur_a = K + W[jc] @ rest_t[jf]
        W[jc] = swing(cur_a - K, A_ - K) @ W[jc]
        # (foot keeps its own world rotation)
    # locals
    loc_r = [None] * NB
    loc_t = [t_.copy() for t_ in rest_t]
    for j in range(NB):
        p = sk.parents[j]
        loc_r[j] = (W[p].inverted() @ W[j]) if p >= 0 else W[j]
        loc_r[j].normalize()
    loc_t[bi['NPC COM [COM ]']] = com_world - rest_t[0]  # COM parent (Root) sits at origin
    ankles = {s: (P[ac_idx[LEGS[s][5]]] * S).z for s in LEGS}
    return loc_r, loc_t, ankles

def stride(clip):
    d = clip['pos']['00000000']
    return (Vector(d[-1][1:]) - Vector(d[0][1:])).length

os.makedirs(OUT, exist_ok=True)
summary = {'scale_units_per_m': round(S, 2)}
for name, outs, sky_speed, feet in JOBS:
    clip = data['clips'][name]
    dur_src = clip['duration']
    if sky_speed:
        dur = stride(clip) * S / sky_speed
    else:
        dur = dur_src
    n = max(2, int(round(dur * FPS)) + 1)
    an = AnimationData(duration=dur, num_frames=n, num_tracks=NB, frame_duration=dur / (n - 1))
    an.bone_names = list(sk.bones); an.track_to_bone_indices = list(range(NB))
    an.original_skeleton_name = sk.name
    tracks = [TrackData([], [], []) for _ in range(NB)]
    prev = [None] * NB
    ank = {'L': [], 'R': []}
    for k in range(n):
        t = dur_src * k / (n - 1)
        lr, lt, ankles = retarget_frame(clip, t)
        for j in range(NB):
            q = lr[j]
            if prev[j] is not None and prev[j].dot(q) < 0: q = -q
            prev[j] = q
            tracks[j].rotations.append(to_xyzw(q))
            tracks[j].translations.append(list(lt[j]))
            tracks[j].scales.append([1.0, 1.0, 1.0])
        for s in ank: ank[s].append(ankles[s])
    an.tracks = tracks
    if feet:
        for s, label in zip(('L', 'R'), feet):
            k = min(range(n), key=lambda i: ank[s][i])
            an.annotations.append(Annotation(time=round(dur * k / (n - 1), 4), text=label))
        an.annotations.sort(key=lambda a: a.time)
    for o in outs:
        A.write_skyrim_animation(os.path.join(OUT, o), an, ptr_size=8)
    summary[name] = {'files': outs, 'src_duration': round(dur_src, 3), 'duration': round(dur, 3),
                     'playback_rate_vs_ac1': round(dur_src / dur, 3), 'frames': n,
                     'annotations': [(a.time, a.text) for a in an.annotations]}
json.dump(summary, open(os.path.join(OUT, 'retarget_report.json'), 'w'), indent=1)
print('RETARGET', json.dumps(summary))
