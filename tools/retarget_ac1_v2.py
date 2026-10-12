"""Retarget AC1 clips onto the vanilla Skyrim SE character skeleton - job-driven (v2).

blender -b --factory-startup --python tools/retarget_ac1_v2.py -- <ac1_clips2.json> <vanilla_anim_dir> <out_dir> [job-substring]

Core method as in v1 (world-rotation deltas from rest, COM from AC root scaled by leg length,
two-bone leg IK onto Altair's ankles). New per-job options:
  yaw        rotate Altair's whole pose about Z (deg, + = left): unarmed directional moves face
             the travel direction, as Altair does in AC1.
  stabilize  remove the AC root's heading change over the clip (fight strafes orbit their
             target; turn-in-place clips rotate the body, which Skyrim does itself).
  upper      vanilla clip whose spine/arms/head (world rotations) replace Altair's, so drawn
             weapons, bows and spells stay correctly in the hands; legs/pelvis stay AC1.
  timing     ('speed', u/s)  stride-matched to a Skyrim movement speed, rate clamped
             ('fixed', s)    time-scaled to a duration
             ('fill', s)     played at native rate, looped to fill a duration
             ('native',)     unchanged
  feet       footstep annotation names, placed at Altair's foot contacts
"""
import sys, os, json, math
from mathutils import Quaternion, Vector

ROOT = r'C:\Users\myste\Downloads\Altair Skyrim Native'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tooling', 'pynifly-29.1.0', 'io_scene_nifly', 'hkx'))
import hkx_skel
import hkx_annotations
import hkx_interleaved
FC_CAL = {}
import anim_skyrim as A
from anim_fo4 import AnimationData, TrackData, Annotation

args = sys.argv[sys.argv.index('--') + 1:]
CLIPS_JSON, VANILLA, OUT = args[0], args[1], args[2]
ONLY = args[3] if len(args) > 3 else ''
FPS = 30.0
RATE_MIN, RATE_MAX = 0.55, 1.8

# Skyrim speeds (u/s), Skyrim.esm MOVT: NPC_Default_MT, NPC_Sneaking_MT, NPC_Sprinting_MT.
WALK = {'F': 80.1, 'L': 80.09, 'R': 79.75, 'B': 71.93}
RUN = {'F': 370.0, 'L': 370.0, 'R': 370.0, 'B': 205.25}
SNEAK_WALK = {'F': 47.2, 'L': 41.44, 'R': 41.44, 'B': 43.38}
SNEAK_RUN = {'F': 222.0, 'L': 200.0, 'R': 200.0, 'B': 150.0}
SPRINT = 500.0
def dspeed(tbl, d):
    parts = [tbl[c] for c in d]
    return sum(parts) / len(parts)

# ---------------------------------------------------------------------------- jobs
JOBS = []
def job(out, clip, timing, yaw=0.0, stabilize=False, upper=None, feet=None, sexed=False):
    outs = [f'male/{out}', f'female/{out}'] if sexed else [out]
    JOBS.append(dict(out=outs, clip=clip, timing=timing, yaw=yaw, stabilize=stabilize, upper=upper, feet=feet))

FEET = ('FootLeft', 'FootRight')
SPRINT_FEET = ('FootSprintLeft', 'FootSprintRight')
# direction table: (skyrim suffix per family, speed key, yaw)
DIRS = [('F', 0), ('FL', 45), ('L', 90), ('BL', 135), ('B', 180), ('BR', -135), ('R', -90), ('FR', -45)]
MT = {'F': 'forward', 'FL': 'forwardleft', 'L': 'left', 'BL': 'backwardleft', 'B': 'backward',
      'BR': 'backwardright', 'R': 'right', 'FR': 'forwardright'}
SNEAKW = {'F': 'forward', 'FL': 'fwrwrdleft', 'L': 'left', 'BL': 'bckwrdleft', 'B': 'bckward',
          'BR': 'bckwrdright', 'R': 'right', 'FR': 'frwrdright'}
SNEAKR = {'F': 'forward', 'FL': 'frwrdleft', 'L': 'left', 'BL': 'bckwrdleft', 'B': 'backward',
          'BR': 'bckwrdright', 'R': 'right', 'FR': 'frwrdright'}
STRAFE = {'F': 'front', 'FL': 'frontleft', 'L': 'left', 'BL': 'backleft', 'B': 'back',
          'BR': 'backright', 'R': 'right', 'FR': 'frontright'}
def key(d):  # speed-table key letters for a direction
    return ''.join(c for c in d)

# 1. unarmed (sexed folders) - Altair faces where he goes
job('mt_idle.hkx', 'idle_low', ('native',), sexed=True)
job('mt_sprintforward.hkx', 'sprint', ('speed', SPRINT), feet=SPRINT_FEET, sexed=True)
for d, yaw in DIRS:
    job(f'mt_walk{MT[d]}.hkx', 'walk', ('speed', dspeed(WALK, key(d))), yaw=yaw, feet=FEET, sexed=True)
    back = 'B' in d
    job(f'mt_run{MT[d]}.hkx', 'jog' if back else 'run', ('speed', dspeed(RUN, key(d))), yaw=yaw, feet=FEET, sexed=True)
# turning on the spot (Skyrim rotates the actor; keep only the stepping)
job('mt_turnleft60.hkx', 'turn_left_090', ('native',), stabilize=True)
job('mt_turnleft180.hkx', 'turn_left_180', ('native',), stabilize=True)
job('mt_turnright60.hkx', 'turn_right_090', ('native',), stabilize=True)
job('mt_turnright180.hkx', 'turn_right_180', ('native',), stabilize=True)
# 2. jumping (vanilla state lengths kept; side variants face the strafe direction like the runs)
for suffix, yaw in (('', 0), ('left', 90), ('right', -90)):
    jl = {'': 1.733, 'left': 3.0, 'right': 3.0}[suffix]
    fl = {'': 1.467, 'left': 1.4, 'right': 1.4}[suffix]
    job(f'mt_jump{suffix}.hkx', 'jump_to_fall', ('fixedcut', jl), yaw=yaw)
    job(f'mt_jumpfast{suffix}.hkx', 'jump_to_fall', ('fixedcut', fl), yaw=yaw)
    job(f'mt_jumpfall{suffix}.hkx', 'fall', ('fill', {'': 5.333, 'left': 6.667, 'right': 5.333}[suffix]), yaw=yaw)
    job(f'mt_jumpland{suffix}.hkx', 'land_wait', ('fixed', {'': 0.867, 'left': 1.033, 'right': 1.033}[suffix]), yaw=yaw)
# 3. sneaking (AC1 crouch)
job('sneakmtidle.hkx', 'crouch_idle', ('native',))
for d, yaw in DIRS:
    job(f'sneakwalk_{SNEAKW[d]}.hkx', 'crouch_walk', ('speed', dspeed(SNEAK_WALK, key(d))), yaw=yaw, feet=FEET)
    job(f'sneakrun_{SNEAKR[d]}.hkx', 'crouch_walk', ('speed', dspeed(SNEAK_RUN, key(d))), yaw=yaw, feet=FEET)
job('sneak1hm_idle.hkx', 'crouch_idle', ('fill', 11.067), upper='sneak1hm_idle.hkx')
# 4. weapon drawn: AC1 fight-stance legs, vanilla upper body (weapon grip, aiming)
for fam, idle in (('1hm', '1hm_idle.hkx'), ('2hm', '2hm_idle.hkx'), ('bow', 'bow_idleheld.hkx'), ('mag', None)):
    if idle:
        job(idle, 'defence_idle', ('fill', None), upper=idle)
    for d, _ in DIRS:
        walk = f'{fam}_walk{MT[d]}.hkx'
        job(walk, f'defence_{STRAFE[d]}', ('speed', dspeed(WALK, key(d))), stabilize=True, upper=walk, feet=FEET)
        run = f'{fam}_run{MT[d]}.hkx'
        if d == 'F':
            job(run, 'run', ('speed', RUN['F']), upper=run, feet=FEET)
        else:
            job(run, f'light_{STRAFE[d]}', ('speed', dspeed(RUN, key(d))), stabilize=True, upper=run, feet=FEET)
for sp in ('mt_sprintforwardsword.hkx', '2hm_sprintforwardsword.hkx', 'bow_sprint.hkx'):
    job(sp, 'sprint', ('speed', SPRINT), upper=sp, feet=SPRINT_FEET)

# 5. extras: AC1 roll for the sneak roll; sneak and weapon-drawn turns; magic stance idle
job('sneakrun_forwardroll.hkx', 'roll', ('fixed', 0.867))
job('sneak_turnleft60.hkx', 'crouch_turn_left', ('native',), stabilize=True)
job('sneak_turnright60.hkx', 'crouch_turn_right', ('native',), stabilize=True)
job('sneak_turnleft180.hkx', 'crouch_turn_180', ('native',), stabilize=True)
job('sneak_turnright180.hkx', 'crouch_turn_180', ('native',), stabilize=True)
for fam in ('1hm', 'shd', 'mag', 'bow'):
    for side in ('left', 'right'):
        for a, src in (('60', '090'), ('180', '180')):
            f = f'{fam}_turn{side}{a}.hkx'
            job(f, f'turn_{side}_{src}', ('native',), stabilize=True, upper=f)
job('dualmagic_idle.hkx', 'light_idle', ('fill', None), upper='dualmagic_idle.hkx')
# 6. one-handed sword combat: full AC1 body; strike time-warped onto the vanilla swing so the
#    behaviour's hit events (fixed times in the vanilla graph) still land on the blow
for out, clip in (('1hm_attackright.hkx', 'atk_right'), ('1hm_attackleft.hkx', 'atk_left'),
                  ('1hm_attackpower.hkx', 'atk_power'), ('1hm_attackpowerright.hkx', 'atk_power_right'),
                  ('1hm_attackpowerleft.hkx', 'atk_power_left'), ('1hm_attackpowerfwd.hkx', 'atk_power_fwd'),
                  ('1hm_attackpowerbwd.hkx', 'atk_power_bwd'), ('1hm_attackforwardsprint.hkx', 'atk_sprint'),
                  ('1hm_attackpowerforwardsprint.hkx', 'atk_power_sprint')):
    job(out, clip, ('strike', out), stabilize=True)
job('1hm_blockidle.hkx', 'defence_idle', ('fill', 3.767))
job('1hm_blockhit.hkx', 'block_hit', ('fixed', 0.833), stabilize=True)

# 7. SkyParkour replacements (ALTAIR_JOBSET=parkour): durations and events (animmotion/sound) are
#    SkyParkour's own; Altair's AC1 climb is synced and scaled onto SkyParkour's motion path
SP_ANIMS = 'C:/Users/myste/AppData/Local/ModOrganizer/Skyrim Special Edition/mods/SkyParkour v3 - Procedural Parkour and Climbing Framework (SPPF)/meshes/actors/character/animations'
if os.environ.get('ALTAIR_JOBSET') == 'parkour':
    JOBS.clear()
    for out, clip in (('SkyParkour/SkyParkour_StepLowLeft.hkx', 'pk_climb150'), ('SkyParkour/SkyParkour_StepLowRight.hkx', 'pk_climb150'),
                      ('SkyParkour/SkyParkour_StepHighLeft.hkx', 'pk_climb150'), ('SkyParkour/SkyParkour_StepHighRight.hkx', 'pk_climb150'),
                      ('SkyParkour/SkyParkour_Vault.hkx', 'pk_vault'),
                      ('SkyParkour/SkyParkour_ClimbLow.hkx', 'pk_climb150'), ('SkyParkour/SkyParkour_GrabHigh.hkx', 'pk_climb150'),
                      ('SkyParkour/SkyParkour_Grab.hkx', 'pk_climb150'), ('SkyParkour/SkyParkour_ClimbMedium.hkx', 'pk_climb200'),
                      ('SkyParkour/SkyParkour_ClimbHigh.hkx', 'pk_climb250'), ('SkyParkour/SkyParkour_ClimbHighest.hkx', 'pk_climb300'),
                      ('SkyParkour/SkyParkour_Fail.hkx', 'pk_fail'), ('SkyParkour_Slide/LandRoll.hkx', 'pk_landroll')):
        job(out, clip, ('parkour', SP_ANIMS + '/' + out), stabilize=False)
        if out.endswith('Vault.hkx'):
            JOBS[-1]['sp_com'] = True
    # sneak roll (locomotion mod): full AC1 roll + recovery into the crouch, vanilla length
    job('sneakrun_forwardroll.hkx', 'pk_sneakroll', ('fixed', 0.867))

# 8. FreeClimb replacements (ALTAIR_JOBSET=freeclimb): FreeClimb plays its own interleaved 60 fps
#    clips and reads per-frame contacts/travel from configs/*.json. Altair's pose is written into a
#    copy of each original file (same frames/layout) and the config is regenerated from AC1 data.
FC_DIR = 'C:/Users/myste/AppData/Local/ModOrganizer/Skyrim Special Edition/mods/FreeClimb/meshes/actors/character/animations/FreeClimb'
if os.environ.get('ALTAIR_JOBSET') == 'freeclimb':
    JOBS.clear()
    for slot, clip, mode in (('hang', 'fc_hang', 'loop'), ('up', 'fc_up', 'loop'), ('down', 'fc_down', 'loop'),
                             ('left', 'fc_left', 'loop'), ('right', 'fc_right', 'loop'),
                             ('hopUp', 'fc_hopup', 'move'), ('hopLeft', 'fc_hopleft', 'move'), ('hopRight', 'fc_hopright', 'move'),
                             ('jumpCatch', 'fc_jumpcatch', 'move'), ('ledgeCatch', 'fc_ledgecatch', 'move'),
                             ('reach', 'fc_reach', 'enter'), ('contextMantle', 'fc_mantle', 'mantle')):
        job(slot + '.hkx', clip, ('freeclimb', slot, mode))

# 9. jumps v2 (ALTAIR_JOBSET=jumps): AC1 take-off into the in-air "ready to land" pose, held while
#    airborne (v1 went straight into the falling-flail loop, which read badly on small hops)
if os.environ.get('ALTAIR_JOBSET') == 'jumps':
    JOBS.clear()
    for suffix, yaw in (('', 0), ('left', 90), ('right', -90)):
        jl = {'': 1.733, 'left': 3.0, 'right': 3.0}[suffix]
        fl = {'': 1.467, 'left': 1.4, 'right': 1.4}[suffix]
        job(f'mt_jump{suffix}.hkx', 'jump_stand2', ('fixedcut', jl), yaw=yaw)
        job(f'mt_jumpfast{suffix}.hkx', 'jump_run2', ('fixedcut', fl), yaw=yaw)

# 10. leap of faith (ALTAIR_JOBSET=leap): only active while the leap-point ability is on the player
if os.environ.get('ALTAIR_JOBSET') == 'leap':
    JOBS.clear()
    for suffix in ('', 'left', 'right'):
        # the swan dive: AC1's step off the edge into the arms-spread dive, then onto the back
        job(f'mt_jump{suffix}.hkx', 'lof_dive', ('fixedcut', {'': 1.733, 'left': 3.0, 'right': 3.0}[suffix]))
        job(f'mt_jumpfast{suffix}.hkx', 'lof_dive', ('fixedcut', {'': 1.467, 'left': 1.4, 'right': 1.4}[suffix]))
        # falling: the dive ends head-down, so the fall starts with AC1's turn onto the back, then the back-fall loop
        job(f'mt_jumpfall{suffix}.hkx', 'lof_fall2', ('fixedcut', {'': 5.333, 'left': 5.333, 'right': 5.333}[suffix]))
        job(f'mt_jumpland{suffix}.hkx', 'lof_land', ('native',))

# 11. free-run jumps (ALTAIR_JOBSET=freerun): AC1's running takeoffs, flights and free-step receptions, in place
#     (root displacement is left out; AltairFreerun.dll drives the jump path), for the plugin's own pose player
if os.environ.get('ALTAIR_JOBSET') == 'freerun':
    JOBS.clear()
    for nm in json.load(open(os.path.join(os.path.dirname(CLIPS_JSON) or '.', 'ac1_spec_fr.json'))):
        job(f'{nm}.hkx', nm, ('native',))
        if nm.startswith('pray'):
            JOBS[-1]['arm_ik'] = True   # the clasped hands meet
            JOBS[-1]['arm_ik_shift'] = (0.0, -2.0, -6.0)

# ---------------------------------------------------------------------------- rig data
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
LEGS = {'L': ('NPC L Thigh [LThg]', 'NPC L Calf [LClf]', 'NPC L Foot [Lft ]', '060df401', '58988870'),
        'R': ('NPC R Thigh [RThg]', 'NPC R Calf [RClf]', 'NPC R Foot [Rft ]', '863d09fc', '9b14362c')}

def q_xyzw(q): return Quaternion((q[3], q[0], q[1], q[2]))
def to_xyzw(q): return [q.x, q.y, q.z, q.w]

data = json.load(open(CLIPS_JSON))
clips = data['clips']
ac = data['skeleton']
ac_idx = {b['bone_id']: i for i, b in enumerate(ac)}
Rz90 = Quaternion((0, 0, 1), math.radians(90))
ac_rest_rot_anim = [Rz90 @ q_xyzw(b['global_rot']) for b in ac]

sk = hkx_skel.load(os.path.join(ROOT, 'tooling', 'vanilla_character_skeleton.hkx'))
NB = len(sk.bones)
bi = {n: i for i, n in enumerate(sk.bones)}
rest_t = [Vector(p.translation) for p in sk.reference_pose]
rest_r = [q_xyzw(p.rotation) for p in sk.reference_pose]
if os.environ.get('ALTAIR_JOBSET') == 'freeclimb':
    # FreeClimb validates every non-Root/COM translation against its canonical rig (skeleton.json)
    _fc = json.load(open(FC_DIR + '/skeleton.json'))['bones']
    assert [b['name'] for b in _fc] == list(sk.bones)
    rest_t = [Vector(b['t']) for b in _fc]
    rest_r = [q_xyzw(b['q']) for b in _fc]
COM = bi['NPC COM [COM ]']

def sky_world(rots_local):
    W = [None] * NB
    for j in range(NB):
        p = sk.parents[j]
        W[j] = (W[p] @ rots_local[j]) if p >= 0 else rots_local[j].copy()
    return W
sky_rest_W = sky_world(rest_r)
# bones whose world rotation comes from the vanilla clip in hybrid jobs: the Spine subtree
UPPER = set()
for j in range(NB):
    k = j
    while k >= 0:
        if sk.bones[k] == 'NPC Spine [Spn0]':
            UPPER.add(j); break
        k = sk.parents[k]

def acpos(b): return Vector(ac[ac_idx[b]]['global_pos'])
ac_leg = (acpos('060df401') - acpos('176183f0')).length + (acpos('58988870') - acpos('060df401')).length
S = (rest_t[bi['NPC L Calf [LClf]']].length + rest_t[bi['NPC L Foot [Lft ]']].length) / ac_leg

# composite clip: takeoff -> transition -> falling loop (the extractor joins parts by time)
def join(names):
    out = {'duration': 0.0, 'rot': {}, 'pos': {}}
    for n in names:
        c = clips[n]; off = out['duration']
        for kind in ('rot', 'pos'):
            for b, keys in c[kind].items():
                if b == '00000000':
                    continue  # root motion is not used
                out[kind].setdefault(b, []).extend([[k[0] + off] + k[1:] for k in keys])
        out['duration'] += c['duration']
    return out
def blend_seams(clip, W=0.2):
    # Joined AC1 parts meet with a pose jump (the game cross-blends items at runtime). Find seams
    # (two keys at the same time) and fade the jump out over W seconds after each seam.
    for kind in ('rot', 'pos'):
        for b, keys in clip[kind].items():
            if b == '00000000' or len(keys) < 2:
                continue
            out = [keys[0]]
            seams = []
            for k in keys[1:]:
                if abs(k[0] - out[-1][0]) < 1e-4:
                    seams.append((k[0], out[-1][1:], k[1:]))   # (time, value before, value after)
                    continue
                out.append(k)
            for t0, va, vb in seams:
                for k in out:
                    if t0 < k[0] < t0 + W:
                        u = (k[0] - t0) / W; u = u * u * (3 - 2 * u)
                        if kind == 'rot':
                            qa, qb, q = q_xyzw(va), q_xyzw(vb), q_xyzw(k[1:])
                            if qa.dot(qb) < 0: qa = -qa
                            d = (qa @ qb.inverted()); d.normalize()
                            r = Quaternion().slerp(d, 1.0 - u) @ q; r.normalize()
                            k[1:] = [r.x, r.y, r.z, r.w]
                        else:
                            k[1:] = [x + (a - c) * (1.0 - u) for x, a, c in zip(k[1:], va, vb)]
            clip[kind][b] = out
if os.environ.get('ALTAIR_JOBSET') in ('parkour', 'jumps', 'leap', 'freerun'):
    for nm, c in clips.items():
        if nm.startswith(('pk_', 'jump_', 'lof_', 'hang_pullup', 'hang_drop', 'beam_', 'pole_', 'wall_', 'swing_loop')):
            blend_seams(c)

if 'jump' in clips and 'fall' in clips:
    clips['jump_to_fall'] = join(['jump'] + ['fall'] * 8)

def sample(keys, t, is_rot):
    if t <= keys[0][0]: k = keys[0]
    elif t >= keys[-1][0]: k = keys[-1]
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
        if p < 0: G[i], P[i] = lr, lp
        else:
            G[i] = G[p] @ lr
            P[i] = P[p] + G[p] @ lp
    return G, P

ROOT_I = ac_idx['2c52cbb0']
def heading(G):
    f = (G[ROOT_I] @ ac_rest_rot_anim[ROOT_I].inverted()) @ Vector((0, 1, 0))
    return math.atan2(-f.x, f.y)   # + = turned left

def swing(a, b): return a.normalized().rotation_difference(b.normalized())

def vanilla_world(an, f):
    loc = [None] * NB
    for j in range(NB):
        loc[j] = q_xyzw(an.tracks[j].rotations[f])
    W = [None] * NB
    for j in range(NB):
        p = sk.parents[j]
        W[j] = (W[p] @ loc[j]) if p >= 0 else loc[j]
    return W

def vanilla_hand_peak(an, bone='NPC R Hand [RHnd]'):
    jb = bi[bone]; prev = None; best = (0.0, 0)
    for f in range(an.num_frames):
        W, P = [None] * NB, [None] * NB
        for j in range(NB):
            p = sk.parents[j]; tr = an.tracks[j]
            lr, lt = q_xyzw(tr.rotations[f]), Vector(tr.translations[f])
            if p < 0: W[j], P[j] = lr, lt
            else: W[j] = W[p] @ lr; P[j] = P[p] + W[p] @ lt
        if prev is not None:
            v = (P[jb] - prev).length
            if v > best[0]: best = (v, f)
        prev = P[jb]
    return best[1] / (an.num_frames - 1) * an.duration

def ac_hand_peak(clip, bone='75f94d30'):
    i = ac_idx[bone]; prev = None; best = (0.0, 0.0); n = int(clip['duration'] * 60)
    for k in range(n + 1):
        t = clip['duration'] * k / n
        G, P = ac_pose(clip, t)
        if prev is not None:
            v = (P[i] - prev).length
            if v > best[0]: best = (v, t)
        prev = P[i]
    return best[1]

def sample_vanilla(an, phase):
    x = phase * (an.num_frames - 1)
    f0 = int(math.floor(x)); f1 = min(an.num_frames - 1, f0 + 1); u = x - f0
    W0, W1 = vanilla_world(an, f0), vanilla_world(an, f1)
    out = []
    for a, b in zip(W0, W1):
        if a.dot(b) < 0: b = -b
        out.append(a.slerp(b, u))
    return out

def retarget_frame(clip, t, yaw_q, yaw_ref, stabilize, upperW, offset=None, com_override=None, limb_delta=None):
    G, P = ac_pose(clip, t)
    R = yaw_q
    if stabilize:
        R = Quaternion((0, 0, 1), -(heading(G) - yaw_ref)) @ (R if R is not None else Quaternion())
    if R is not None:
        G = [R @ g for g in G]
        P = [R @ p for p in P]
    if offset is not None:
        P = [p + offset for p in P]
    W = [None] * NB
    for j in range(NB):
        name = sk.bones[j]; p = sk.parents[j]
        if upperW is not None and j in UPPER:
            W[j] = upperW[j]
            continue
        src = MAP.get(name)
        if src is not None and src in ac_idx:
            i = ac_idx[src]
            W[j] = G[i] @ ac_rest_rot_anim[i].inverted() @ sky_rest_W[j]
        else:
            W[j] = (W[p] @ rest_r[j]) if p >= 0 else rest_r[j].copy()
    com_world = P[ROOT_I] * S
    shift = Vector()
    if com_override is not None:
        shift = com_override - com_world; com_world = com_override.copy()
    Pp = [None] * NB
    for j in range(NB):
        p = sk.parents[j]
        if j == COM: Pp[j] = com_world.copy()
        elif p < 0: Pp[j] = rest_t[j].copy()
        else: Pp[j] = Pp[p] + W[p] @ rest_t[j]
    for side, (thg, clf, ft, a_clf, a_ft) in LEGS.items():
        jt, jc, jf = bi[thg], bi[clf], bi[ft]
        H = Pp[jt]
        goal, pole = P[ac_idx[a_ft]] * S + shift, P[ac_idx[a_clf]] * S + shift
        if limb_delta is not None:
            goal = goal + limb_delta['foot']
            mid = (H + goal) / 2           # on a wall the knees bend toward it (+Y), keeping AC1's knee spread
            pole = Vector((pole.x, mid.y + 40.0, mid.z))
        L1, L2 = rest_t[jc].length, rest_t[jf].length
        dv = goal - H
        d = max(1e-3, min(dv.length, (L1 + L2) * 0.9995))
        dirv = dv.normalized()
        a = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
        pv = pole - H
        bend = pv - dirv * pv.dot(dirv)
        bend = bend.normalized() if bend.length > 1e-6 else Vector((0, 1, 0))
        K = H + (dirv * math.cos(a) + bend * math.sin(a)) * L1
        A_ = H + dirv * d
        W[jt] = swing(W[jt] @ rest_t[jc], K - H) @ W[jt]
        W[jc] = swing(W[jc] @ rest_t[jf], A_ - K) @ W[jc]
    if limb_delta is not None or ARM_IK:
        # arm IK: hands onto Altair's AC1 hand path (raised by the hold calibration on FreeClimb holds). Also used
        # where AC1's hands meet (prayer): Skyrim's wider shoulders would otherwise hold them apart
        if limb_delta is None:
            # prayer: the clasp sits a little lower and further out than AC1's, at the chin (Skyrim's head is larger)
            limb_delta = {'hand': Vector(ARM_IK_SHIFT)}
        for side, (a_el, a_wr) in (('L', ('89b93a80', 'b675f36c')), ('R', ('7257a1aa', '75f94d30'))):
            ju, jf, jh = bi[f'NPC {side} UpperArm [{side}Uar]'], bi[f'NPC {side} Forearm [{side}Lar]'], bi[f'NPC {side} Hand [{side}Hnd]']
            Pa = [None] * NB
            for j in range(NB):
                pj = sk.parents[j]
                if j == COM: Pa[j] = com_world.copy()
                elif pj < 0: Pa[j] = rest_t[j].copy()
                else: Pa[j] = Pa[pj] + W[pj] @ rest_t[j]
            Sh = Pa[ju]
            goal = P[ac_idx[a_wr]] * S + shift + limb_delta['hand']
            pole = P[ac_idx[a_el]] * S + shift + limb_delta['hand'] * 0.5
            L1, L2 = rest_t[jf].length, rest_t[jh].length
            dv = goal - Sh
            d = max(1e-3, min(dv.length, (L1 + L2) * 0.999))
            dirv = dv.normalized()
            a = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
            pv = pole - Sh
            bend = pv - dirv * pv.dot(dirv)
            bend = bend.normalized() if bend.length > 1e-6 else Vector((0, 0, -1))
            E = Sh + (dirv * math.cos(a) + bend * math.sin(a)) * L1
            Wd = Sh + dirv * d
            hand_world = W[jh].copy()
            W[ju] = swing(W[ju] @ rest_t[jf], E - Sh) @ W[ju]
            W[jf] = swing(W[jf] @ rest_t[jh], Wd - E) @ W[jf]
            W[jh] = hand_world      # keep Altair's hand orientation
    # forearm twist bones carry part of the hand's roll about the forearm (Altair-driven arms only)
    for side in ('L', 'R'):
        jf, jh = bi[f'NPC {side} Forearm [{side}Lar]'], bi[f'NPC {side} Hand [{side}Hnd]']
        if upperW is not None and jf in UPPER:
            continue
        axis = rest_t[jh].normalized()
        delta = (W[jf].inverted() @ W[jh]) @ rest_r[jh].inverted()
        v = Vector((delta.x, delta.y, delta.z))
        pv = axis * v.dot(axis)
        tw = Quaternion((delta.w, pv.x, pv.y, pv.z)); tw.normalize()
        for tname in (f'NPC {side} ForearmTwist1 [{side}Lt1]', f'NPC {side} ForearmTwist2 [{side}Lt2]'):
            jt = bi[tname]
            frac = min(1.0, rest_t[jt].length / rest_t[jh].length)
            W[jt] = W[jf] @ Quaternion().slerp(tw, frac) @ rest_r[jt]
    loc_r = []
    for j in range(NB):
        p = sk.parents[j]
        q = (W[p].inverted() @ W[j]) if p >= 0 else W[j]
        q.normalize(); loc_r.append(q)
    loc_t = [v.copy() for v in rest_t]
    loc_t[COM] = com_world
    ank = {s: (P[ac_idx[LEGS[s][4]]] * S).z for s in LEGS}
    return loc_r, loc_t, ank

def stride(name):
    d = clips[name]['pos'].get('00000000')
    return (Vector(d[-1][1:3] + [0]) - Vector(d[0][1:3] + [0])).length if d else 0.0

vcache = {}
def vanilla(name):
    if name not in vcache:
        p = os.path.join(VANILLA, name)
        vcache[name] = A.load_skyrim_animation(p) if os.path.isfile(p) else None
    return vcache[name]

summary = {'scale_units_per_m': round(S, 2), 'jobs': []}
ARM_IK = False
ARM_IK_SHIFT = (0.0, 0.0, 0.0)
for jb in JOBS:
    ARM_IK = bool(jb.get('arm_ik'))
    ARM_IK_SHIFT = jb.get('arm_ik_shift', (0.0, 0.0, 0.0))
    if ONLY and ONLY not in jb['out'][0]:
        continue
    clip = clips[jb['clip']]
    src_dur = clip['duration']
    kind = jb['timing'][0]
    up = vanilla(jb['upper']) if jb['upper'] else None
    if jb['upper'] and up is None:
        summary['jobs'].append({'out': jb['out'], 'skipped': 'vanilla clip missing'}); continue
    if kind == 'speed':
        st = stride(jb['clip'])
        rate = src_dur / (st * S / jb['timing'][1]) if st > 0 else 1.0
        rate = max(RATE_MIN, min(RATE_MAX, rate))
        dur = src_dur / rate; src_span = src_dur; loop = False
    elif kind == 'fixed':
        dur = jb['timing'][1]; rate = src_dur / dur; src_span = src_dur; loop = False
    elif kind == 'fixedcut':      # native rate, cut at duration
        dur = jb['timing'][1]; rate = 1.0; src_span = dur; loop = False
    elif kind == 'fill':          # native rate, looped over the vanilla duration
        dur = jb['timing'][1] or (up.duration if up else src_dur)
        cycles = max(1, round(dur / src_dur)); dur = cycles * src_dur if not up else dur
        rate = 1.0; src_span = dur; loop = True
    elif kind == 'strike':        # piecewise-linear warp: AC hand-speed peak -> vanilla peak
        van = vanilla(jb['timing'][1])
        dur = van.duration; tv = max(0.05, min(dur - 0.05, vanilla_hand_peak(van)))
        ta = max(0.05, min(src_dur - 0.05, ac_hand_peak(clip)))
        warp = (tv, ta); rate = src_dur / dur; src_span = src_dur; loop = False
    elif kind == 'freeclimb':
        slot, mode = jb['timing'][1], jb['timing'][2]
        src_file = FC_DIR + '/' + slot + '.hkx'
        cfg_file = FC_DIR + '/configs/' + slot + '.json'
        fc_src = hkx_interleaved.read(src_file)
        dur = fc_src['duration']; n_fixed = fc_src['frames']
        rate = src_dur / dur; src_span = src_dur; loop = False
        dk = clip['pos'].get('00000000', [[0, 0, 0, 0], [src_dur, 0, 0, 0]])
        disp_end = sample(dk, src_dur, False) * S
        fc_com = [Vector(fc_src['transforms'][f][COM][0]) for f in range(n_fixed)]
        if FC_CAL.get('hand') is None:
            # hold calibration: Altair's hang limbs (relative to his COM) vs FreeClimb's hang limbs
            def limbs_rel(lr, lt):
                Wc, Pc = [None] * NB, [None] * NB
                for j in range(NB):
                    pj = sk.parents[j]
                    if pj < 0: Wc[j], Pc[j] = lr[j], lt[j]
                    else: Wc[j] = Wc[pj] @ lr[j]; Pc[j] = Pc[pj] + Wc[pj] @ lt[j]
                c = Pc[COM]
                h = (Pc[bi['NPC L Hand [LHnd]']] + Pc[bi['NPC R Hand [RHnd]']]) / 2 - c
                f_ = (Pc[bi['NPC L Foot [Lft ]']] + Pc[bi['NPC R Foot [Rft ]']]) / 2 - c
                return h, f_
            lr0, lt0, _ = retarget_frame(clips['fc_hang'], 0.0, None, 0.0, False, None, None)
            oh, of_ = limbs_rel(lr0, lt0)
            ref = hkx_interleaved.read(FC_DIR + '/hang.hkx')['transforms'][0]
            th, tf_ = limbs_rel([Quaternion((x[1][3], x[1][0], x[1][1], x[1][2])) for x in ref], [Vector(x[0]) for x in ref])
            FC_CAL['hand'], FC_CAL['foot'] = th - oh, tf_ - of_
            summary['freeclimb_limb_calibration'] = {'hand': [round(v, 1) for v in FC_CAL['hand']], 'foot': [round(v, 1) for v in FC_CAL['foot']]}
        limb_delta = {'hand': FC_CAL['hand'], 'foot': FC_CAL['foot']}
    elif kind == 'parkour':
        dur, sp_ann = hkx_annotations.read(jb['timing'][1])
        mk = []
        for _, tm, txt in sp_ann:
            if txt.startswith('animmotion'):
                x, y, z = map(float, txt.split()[1:4]); mk.append((tm, Vector((x, y, z))))
        mk.sort(key=lambda k: k[0])
        if not mk: mk = [(0.0, Vector())]
        if mk[0][0] > 0: mk.insert(0, (0.0, mk[0][1].copy()))
        if mk[-1][0] < dur: mk.append((dur, mk[-1][1].copy()))
        def m_at(t, mk=mk):
            for a, b in zip(mk, mk[1:]):
                if t <= b[0]:
                    u = (t - a[0]) / max(1e-6, b[0] - a[0]); return a[1].lerp(b[1], u)
            return mk[-1][1].copy()
        dk = clip['pos'].get('00000000', [[0, 0, 0, 0], [src_dur, 0, 0, 0]])
        def d_raw(t, dk=dk): return sample(dk, min(max(t, 0.0), src_dur), False) * S
        SM = 0.12   # smoothing half-window (s)
        def d_at(t):
            acc = Vector(); n_ = 9
            for i in range(n_):
                acc += d_raw(t - SM + 2 * SM * i / (n_ - 1))
            return acc / n_
        def cum(fn, t0, t1, n=200):
            ts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]; L = [0.0]
            for a, b in zip(ts, ts[1:]): L.append(L[-1] + (fn(b) - fn(a)).length)
            return ts, L
        ts_sp, L_sp = cum(m_at, 0.0, dur); ts_ac, L_ac = cum(d_at, 0.0, src_dur)
        def inv(ts, L, frac):
            if L[-1] < 1e-3: return None
            target = frac * L[-1]
            for i in range(1, len(L)):
                if L[i] >= target:
                    u = (target - L[i - 1]) / max(1e-9, L[i] - L[i - 1]); return ts[i - 1] + u * (ts[i] - ts[i - 1])
            return ts[-1]
        def frac_sp(t):
            if L_sp[-1] < 1e-3: return t / dur
            for i in range(1, len(ts_sp)):
                if ts_sp[i] >= t:
                    u = (t - ts_sp[i - 1]) / max(1e-9, ts_sp[i] - ts_sp[i - 1])
                    return (L_sp[i - 1] + u * (L_sp[i] - L_sp[i - 1])) / L_sp[-1]
            return 1.0
        m_end, d_end = m_at(dur), d_at(src_dur)
        ks = []
        for ax in (1, 2):   # forward, up: scale AC1's displacement onto SkyParkour's when compatible
            a, b = d_end[ax], m_end[ax]
            ks.append(b / a if abs(a) > 1 and a * b > 0 and 0.5 <= b / a <= 2.0 else None)
        def pk_offset(t_out, t_ac):
            dv = d_at(t_ac); ph = frac_sp(t_out)
            for ax, k in zip((1, 2), ks):
                dv[ax] = dv[ax] * k if k is not None else dv[ax] + (m_end[ax] - d_end[ax]) * ph
            return (dv - m_at(t_out)) / S
        rate = src_dur / dur; src_span = src_dur; loop = False
        jb['pk_scale'] = [None if k is None else round(k, 2) for k in ks]
    else:
        dur = src_dur; rate = 1.0; src_span = src_dur; loop = False
    n = max(2, int(round(dur * FPS)) + 1)
    if kind == 'freeclimb':
        n = n_fixed
    if kind == 'parkour' and jb.get('sp_com'):
        sp_an = A.load_skyrim_animation(jb['timing'][1])
        sp_z = [tr[2] for tr in sp_an.tracks[COM].translations]
        nf = len(sp_z)
        def sp_com_at(t):
            x = max(0.0, min(1.0, t / dur)) * (nf - 1); f0 = int(x); f1 = min(nf - 1, f0 + 1); u = x - f0
            return Vector(sp_an.tracks[COM].translations[f0]).lerp(Vector(sp_an.tracks[COM].translations[f1]), u)
        ia = max(range(nf), key=lambda i: sp_z[i]); il = min(range(ia, nf), key=lambda i: sp_z[i])
        tv_apex, tv_land = dur * ia / (nf - 1), dur * il / (nf - 1)
        rk = clip['pos']['2c52cbb0']
        def h_ac(t): return (sample(dk, t, False).z + sample(rk, t, False).z)
        ts = [src_dur * i / 200 for i in range(201)]
        ja = max(range(201), key=lambda i: h_ac(ts[i])); jl = min(range(ja, 201), key=lambda i: h_ac(ts[i]))
        ta_apex, ta_land = ts[ja], ts[jl]
        if ta_apex < 0.05 * src_dur:
            # AC1's passover drops to lower ground (no height apex): anchor on the chain itself -
            # hand planted over the obstacle mid-passover, touchdown at the landing part
            names = {l.split('	')[0]: float(l.split('	')[1]) for l in open(os.path.join(ROOT, 'ac1_anim_names.txt'), encoding='utf-8') if '	' in l}
            pd = [names.get(x, 0.0) for x in clip.get('parts', [])]
            if len(pd) >= 4:
                ta_apex = sum(pd[:3]) + 0.5 * pd[3]; ta_land = sum(pd[:4])
        knots = [(0.0, 0.0), (tv_apex, ta_apex), (tv_land, ta_land), (dur, src_dur)]
        def warp_t(tau):
            for (a0, b0), (a1, b1) in zip(knots, knots[1:]):
                if tau <= a1:
                    return b0 + (b1 - b0) * (tau - a0) / max(1e-6, a1 - a0)
            return src_dur
        pk_t = [warp_t(dur * k / (n - 1)) for k in range(n)]
        pk_off = [None] * n
        pk_com = [sp_com_at(dur * k / (n - 1)) for k in range(n)]
        jb['vault_keys'] = {'sp_apex': round(tv_apex, 3), 'sp_land': round(tv_land, 3), 'ac_apex': round(ta_apex, 3), 'ac_land': round(ta_land, 3)}
    elif kind == 'parkour':
        uni = [src_dur * k / (n - 1) for k in range(n)]
        warp_t = []
        for k in range(n):
            w = inv(ts_ac, L_ac, frac_sp(dur * k / (n - 1)))
            warp_t.append(uni[k] if w is None else w)
        mix = [0.5 * a + 0.5 * b for a, b in zip(uni, warp_t)]
        half = max(1, int(round(0.15 * FPS)))
        sm = []
        for k in range(n):
            lo, hi = max(0, k - half), min(n - 1, k + half)
            sm.append(sum(mix[lo:hi + 1]) / (hi - lo + 1))
        sm[0], sm[-1] = 0.0, src_dur
        base = src_dur / dur / FPS          # uniform AC seconds per output frame
        pk_t = [0.0]
        for k in range(1, n):               # monotone, rate within [0.35, 2.5] x uniform
            step = min(max(sm[k] - pk_t[-1], 0.35 * base), 2.5 * base)
            pk_t.append(min(src_dur, pk_t[-1] + step))
        pk_off = [pk_offset(dur * k / (n - 1), pk_t[k]) for k in range(n)]
    yaw_q = Quaternion((0, 0, 1), math.radians(jb['yaw'])) if jb['yaw'] else None
    yaw_ref = heading(ac_pose(clip, 0.0)[0]) if jb['stabilize'] else 0.0
    an = AnimationData(duration=dur, num_frames=n, num_tracks=NB, frame_duration=dur / (n - 1))
    an.bone_names = list(sk.bones); an.track_to_bone_indices = list(range(NB))
    an.original_skeleton_name = sk.name
    tracks = [TrackData([], [], []) for _ in range(NB)]
    prev = [None] * NB
    ank = {'L': [], 'R': []}
    for k in range(n):
        ph = k / (n - 1)
        t = ph * src_span
        if loop: t = math.fmod(t, src_dur)
        if kind == 'strike':
            tau = ph * dur; tv, ta = warp
            t = tau * ta / tv if tau <= tv else ta + (tau - tv) * (src_dur - ta) / (dur - tv)
        upW = sample_vanilla(up, ph) if up else None
        off = None
        if kind == 'parkour':
            t, off = pk_t[k], pk_off[k]
        if kind == 'parkour' and jb.get('sp_com'):
            lr, lt, a_ = retarget_frame(clip, min(t, src_dur), None, 0.0, False, None, None, com_override=pk_com[k])
        elif kind == 'freeclimb':
            t = ph * src_dur
            lr, lt, a_ = retarget_frame(clip, min(t, src_dur), yaw_q, yaw_ref, False, None, None,
                                        com_override=fc_com[k], limb_delta=limb_delta)
        else:
            lr, lt, a_ = retarget_frame(clip, min(t, src_dur), yaw_q, yaw_ref, jb['stabilize'], upW, off)
        for j in range(NB):
            q = lr[j]
            if prev[j] is not None and prev[j].dot(q) < 0: q = -q
            prev[j] = q
            tracks[j].rotations.append(to_xyzw(q))
            tracks[j].translations.append(list(lt[j]))
            tracks[j].scales.append([1.0, 1.0, 1.0])
        for s in ank: ank[s].append(a_[s])
    if kind == 'parkour':
        for tr in tracks:
            R0, T0 = [list(r) for r in tr.rotations], [list(v) for v in tr.translations]
            for k in range(1, n - 1):
                qa, qb, qc = (Quaternion((x[3], x[0], x[1], x[2])) for x in (R0[k - 1], R0[k], R0[k + 1]))
                q = qb.slerp(qa.slerp(qc, 0.5), 0.33); q.normalize()
                tr.rotations[k] = [q.x, q.y, q.z, q.w]
                tr.translations[k] = [0.25 * a + 0.5 * b + 0.25 * c for a, b, c in zip(T0[k - 1], T0[k], T0[k + 1])]
    if kind == 'parkour':
        # de-spike: wherever the COM/pelvis/spine/thighs jump in one frame, re-interpolate a window
        watch = [COM, bi['NPC Pelvis [Pelv]'], bi['NPC Spine [Spn0]'], bi['NPC L Thigh [LThg]'], bi['NPC R Thigh [RThg]']]
        def qv(x): return Quaternion((x[3], x[0], x[1], x[2]))
        for _ in range(4):
            spikes = []
            for k in range(n - 1):
                dp = (Vector(tracks[COM].translations[k + 1]) - Vector(tracks[COM].translations[k])).length
                da = max(math.degrees(qv(tracks[j].rotations[k]).rotation_difference(qv(tracks[j].rotations[k + 1])).angle) for j in watch)
                if dp > 14.0 or da > 30.0:
                    spikes.append(k)
            if not spikes:
                break
            for k in spikes:
                a, b = max(0, k - 2), min(n - 1, k + 3)
                if a == 0: b = min(n - 1, max(b, 5))
                for tr in tracks:
                    qa, qb = qv(tr.rotations[a]), qv(tr.rotations[b])
                    if qa.dot(qb) < 0: qb = -qb
                    ta, tb = Vector(tr.translations[a]), Vector(tr.translations[b])
                    for m_ in range(a + 1, b):
                        u = (m_ - a) / (b - a); u = u * u * (3 - 2 * u)
                        q = qa.slerp(qb, u); tr.rotations[m_] = [q.x, q.y, q.z, q.w]
                        tr.translations[m_] = list(ta.lerp(tb, u))
    an.tracks = tracks
    if kind == 'parkour':
        an.annotations = [Annotation(time=tm, text=txt) for _, tm, txt in sp_ann]
    if jb['feet']:
        for s, label in zip(('L', 'R'), jb['feet']):
            k = min(range(n), key=lambda i: ank[s][i])
            an.annotations.append(Annotation(time=round(dur * k / (n - 1), 4), text=label))
        an.annotations.sort(key=lambda a: a.time)
    if kind == 'freeclimb':
        os.makedirs(os.path.join(OUT, 'configs'), exist_ok=True)
        if jb['timing'][2] == 'loop':
            for tr in tracks:   # exact loop
                tr.rotations[-1] = list(tr.rotations[0]); tr.translations[-1] = list(tr.translations[0])
        frames = [[(tracks[j].translations[k], tracks[j].rotations[k], [1.0, 1.0, 1.0]) for j in range(NB)] for k in range(n)]
        hkx_interleaved.patch(src_file, os.path.join(OUT, jb['out'][0]), frames)
        # contacts [L hand, R hand, L foot, R foot] from AC1's ACUATORCONTACTS bits, softened over +-3 frames
        ck = clip.get('contacts') or [[0.0, 60]]
        def bits_at(t):
            b = ck[0][1]
            for tm, v in ck:
                if tm <= t + 1e-4: b = v
                else: break
            return b
        raw = []
        for k in range(n):
            b = bits_at(src_dur * k / (n - 1))
            raw.append([float(b >> 4 & 1), float(b >> 5 & 1), float((b >> 2 & 1) | (b & 1)), float((b >> 3 & 1) | (b >> 1 & 1))])
        cont = []
        for k in range(n):
            lo, hi = max(0, k - 3), min(n - 1, k + 3)
            cont.append([round(sum(raw[i][c] for i in range(lo, hi + 1)) / (hi - lo + 1), 4) for c in range(4)])
        cfg = json.load(open(cfg_file))
        cfg['contacts'] = cont
        trav = [float(v) for v in disp_end]
        if jb['timing'][2] == 'loop' and Vector(trav).length > 1:
            cfg['travel'] = trav; cfg['stride'] = float(Vector(trav).length)
        # actions keep FreeClimb's own travel/height: their COM path (copied) defines the motion
            pass   # releaseHands/replant/unplant phases: FreeClimb's originals are kept (AC1's contact track
                   # doesn't flag the hands on the ledge top, so they can't be derived reliably)
        json.dump(cfg, open(os.path.join(OUT, 'configs', jb['timing'][1] + '.json'), 'w'), indent=2)
    for o in ([] if kind == 'freeclimb' else jb['out']):
        dst = os.path.join(OUT, o.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        A.write_skyrim_animation(dst, an, ptr_size=8)
    if kind == 'strike':
        jb['strike_vanilla_s'], jb['strike_ac1_s'] = round(warp[0], 3), round(warp[1], 3)
    summary['jobs'].append({'out': jb['out'], 'clip': jb['clip'], 'dur': round(dur, 3),
                            'strike': (jb.get('strike_vanilla_s'), jb.get('strike_ac1_s')),
                            'rate': round(rate, 3), 'yaw': jb['yaw'], 'stabilize': jb['stabilize'],
                            'upper': jb['upper'], 'pk_scale_fwd_up': jb.get('pk_scale'), 'vault_keys': jb.get('vault_keys'), 'annotations': [(a.time, a.text) for a in an.annotations]})
    print('JOB', jb['out'][0], round(dur, 3), round(rate, 3), flush=True)
json.dump(summary, open(os.path.join(OUT, 'retarget_v2_report.json'), 'w'), indent=1)
print('DONE', len(summary['jobs']))
