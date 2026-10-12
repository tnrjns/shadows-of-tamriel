"""Decode HKX animations back (round-trip check) and render the outfit NIF driven by them.

blender -b --factory-startup -P tools/preview_hkx.py -- <out_prefix> <nif> <hkx> [<hkx> ...]
Env: PREVIEW_FRAMES (count per clip, default 6), PREVIEW_VIEWS (side,front,q34)
"""
import bpy, sys, os, math, json
from mathutils import Quaternion, Vector, Matrix

ROOT = r'C:\Users\myste\Downloads\Altair Skyrim Native'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tooling', 'pynifly-29.1.0'))
sys.path.insert(0, os.path.join(ROOT, 'tooling', 'pynifly-29.1.0', 'io_scene_nifly', 'hkx'))
import hkx_skel
import hkx_annotations
import anim_skyrim as A
import addon_utils
addon_utils.enable('io_scene_nifly', default_set=True, persistent=False)

args = sys.argv[sys.argv.index('--') + 1:]
OUTP, NIF, HKXS = args[0], args[1], args[2:]
NFR = int(os.environ.get('PREVIEW_FRAMES', '6'))
VIEWS = os.environ.get('PREVIEW_VIEWS', 'side,front').split(',')
SKEL_NIF = os.path.join(ROOT, 'tooling', 'pynifly-29.1.0', 'io_scene_nifly', 'skeletons', 'Skyrim', 'skeleton.nif')

sk = hkx_skel.load(os.path.join(ROOT, 'tooling', 'vanilla_character_skeleton.hkx'))
def q(v): return Quaternion((v[3], v[0], v[1], v[2]))

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.pynifly(filepath=SKEL_NIF, rename_bones=False, blender_xf=False,
                             import_animations=False, import_collisions=False, import_tris=False)
arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][-1]
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.import_scene.pynifly(filepath=NIF, rename_bones=False, blender_xf=False, import_animations=False,
                             import_collisions=False, import_tris=False, reference_skel=SKEL_NIF, apply_skinning=True)
for o in bpy.context.scene.objects:
    if o.type == 'MESH' and (o.name.startswith('BSBound') or not any(m.type == 'ARMATURE' for m in o.modifiers)):
        o.hide_render = True

# optional weapon on the Weapon node (Skyrim blade = node +Y)
weapon_objs = []
if os.environ.get('PREVIEW_WEAPON'):
    before = set(bpy.data.objects.keys())
    bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = None
    bpy.ops.import_scene.pynifly(filepath=os.environ['PREVIEW_WEAPON'], rename_bones=False, blender_xf=False,
                                 import_animations=False, import_collisions=False, import_tris=False)
    for n in set(bpy.data.objects.keys()) - before:
        o = bpy.data.objects[n]
        if o.type == 'MESH' and not o.name.startswith(('Blood', 'BSBound')):
            o.parent = None; weapon_objs.append((o, o.matrix_world.copy()))
        elif o.type == 'MESH':
            o.hide_render = True
# bone order: parents first
order = []
seen = set()
def visit(j):
    if j in seen: return
    p = sk.parents[j]
    if p >= 0: visit(p)
    seen.add(j); order.append(j)
for j in range(len(sk.bones)): visit(j)

def pose_frame(anim, f, root_offset=None):
    W = [None] * len(sk.bones)
    for j in order:
        tr = anim.tracks[j]
        M = Matrix.Translation(Vector(tr.translations[f])) @ q(tr.rotations[f]).to_matrix().to_4x4()
        p = sk.parents[j]
        W[j] = (W[p] @ M) if p >= 0 else ((Matrix.Translation(root_offset) @ M) if root_offset is not None else M)
    for j in order:
        pb = arm.pose.bones.get(sk.bones[j])
        if pb is not None:
            pb.matrix = W[j]
            bpy.context.view_layer.update()
    wj = sk.bones.index('Weapon')
    for o, m0 in weapon_objs:
        o.matrix_world = arm.matrix_world @ W[wj] @ m0
    return W

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'; scene.display.shading.color_type = 'TEXTURE'
scene.render.resolution_x = 600; scene.render.resolution_y = 800
scene.world.color = (0.32, 0.32, 0.34)
bpy.ops.object.camera_add(); cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = float(os.environ.get('PREVIEW_SCALE', '160'))
cam.data.clip_end = 5000; scene.camera = cam
# ground line for foot contact
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0)); g = bpy.context.object
mat = bpy.data.materials.new('ground'); mat.diffuse_color = (0.18, 0.2, 0.18, 1); g.data.materials.append(mat)
views = {'side': Vector((-400, 0, 0)), 'front': Vector((0, 400, 0)), 'q34': Vector((-280, 280, 60))}
report = {}
import hkx_interleaved
from types import SimpleNamespace
def load_any(h):
    try:
        return A.load_skyrim_animation(h)
    except ValueError:
        r = hkx_interleaved.read(h)
        tr = [SimpleNamespace(translations=[r['transforms'][f][j][0] for f in range(r['frames'])],
                              rotations=[r['transforms'][f][j][1] for f in range(r['frames'])]) for j in range(r['tracks'])]
        return SimpleNamespace(duration=r['duration'], num_frames=r['frames'], tracks=tr, annotations=[])
if os.environ.get('PREVIEW_OBSTACLE'):
    oy, oh = map(float, os.environ['PREVIEW_OBSTACLE'].split(','))
    bpy.ops.mesh.primitive_cube_add(size=1); ob = bpy.context.object
    ob.scale = (80, 20, oh); ob.location = (0, oy, oh / 2)
    om = bpy.data.materials.new('obst'); om.diffuse_color = (0.5, 0.42, 0.35, 1); ob.data.materials.append(om)
if os.environ.get('PREVIEW_WALL'):
    bpy.ops.mesh.primitive_cube_add(size=1); wall = bpy.context.object
    wall.scale = (200, 4, 400); wall.location = (0, float(os.environ['PREVIEW_WALL']) + 2, 120)
    wm = bpy.data.materials.new('wall'); wm.diffuse_color = (0.5, 0.45, 0.4, 1); wall.data.materials.append(wm)
for h in HKXS:
    an = load_any(h)
    motion = []
    if os.environ.get('PREVIEW_MOTION'):
        for _, tm, txt in hkx_annotations.read(h)[1]:
            if txt.startswith('animmotion'):
                motion.append((tm, Vector(tuple(map(float, txt.split()[1:4])))))
        motion.sort(key=lambda k: k[0])
    def m_at(t):
        if not motion: return Vector()
        if t <= motion[0][0]: return motion[0][1]
        for a, b in zip(motion, motion[1:]):
            if t <= b[0]: return a[1].lerp(b[1], (t - a[0]) / max(1e-6, b[0] - a[0]))
        return motion[-1][1]
    ledge = None
    if motion:
        me = motion[-1][1]
        if me.z > 20:
            bpy.ops.mesh.primitive_cube_add(size=1); ledge = bpy.context.object
            ledge.scale = (80, 90, me.z); ledge.location = (0, me.y + 45 - 20, me.z / 2)
            lm = bpy.data.materials.new('ledge'); lm.diffuse_color = (0.45, 0.4, 0.35, 1); ledge.data.materials.append(lm)
    base = os.path.splitext(os.path.basename(h))[0]
    feet = []
    for k in range(NFR):
        f = int(round(k * (an.num_frames - 1) / max(1, NFR - 1))) if NFR > 1 else 0
        W = pose_frame(an, f, m_at(f / max(1, an.num_frames - 1) * an.duration) if motion else None)
        for o, m0 in weapon_objs:
            o.matrix_world = arm.matrix_world @ W[sk.bones.index('Weapon')] @ m0
        lf = W[sk.bones.index('NPC L Foot [Lft ]')].translation.z
        rf = W[sk.bones.index('NPC R Foot [Rft ]')].translation.z
        feet.append((f, round(lf, 1), round(rf, 1)))
        for vn in VIEWS:
            c = Vector((0, 0, 66)) + (Vector((0, motion[-1][1].y * 0.5, motion[-1][1].z * 0.5)) if motion else Vector())
            cam.location = c + views[vn]
            cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = f'{OUTP}_{base}_{vn}_{k}.png'
            bpy.ops.render.render(write_still=True)
    if ledge is not None:
        bpy.data.objects.remove(ledge, do_unlink=True)
    arm.location = (0, 0, 0)
    report[base] = {'duration': an.duration, 'frames': an.num_frames, 'tracks': len(an.tracks),
                    'annotations': [(a.time, a.text) for a in an.annotations], 'ankle_z(frame,L,R)': feet}
print('PREVIEW', json.dumps(report))
