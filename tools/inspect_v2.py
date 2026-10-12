"""Inspect a Skyrim-skinned NIF in Blender: per-shape weight report, textured renders,
and optional test poses on the vanilla Skyrim skeleton.

Run: blender -b --factory-startup -P tools/inspect_v2.py -- <nif> <out_prefix> [pose ...]
Poses: rest, walk, crouch, armsup, twist
"""
import bpy, sys, os, json, math
from mathutils import Vector, Matrix, Euler

BASE = r'C:\Users\myste\Downloads\Altair Skyrim Native'
ADDON_PARENT = os.path.join(BASE, 'tooling', 'pynifly-29.1.0')
SKEL = os.path.join(ADDON_PARENT, 'io_scene_nifly', 'skeletons', 'Skyrim', 'skeleton.nif')
argv = sys.argv[sys.argv.index('--') + 1:]
NIF, OUT = argv[0], argv[1]
POSES = argv[2:] or ['rest']
TEXROOT = os.environ.get('ALTAIR_TEXROOT', BASE)

sys.path.insert(0, ADDON_PARENT)
import addon_utils
addon_utils.enable('io_scene_nifly', default_set=True, persistent=False)
prefs = bpy.context.preferences.addons['io_scene_nifly'].preferences
prefs.sky_texture_path_1 = TEXROOT

bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.pynifly(filepath=SKEL, rename_bones=False, blender_xf=False,
                             import_animations=False, import_collisions=False, import_tris=False)
arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][-1]
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.import_scene.pynifly(filepath=NIF, rename_bones=False, blender_xf=False,
                             import_animations=False, import_collisions=False, import_tris=False,
                             reference_skel=SKEL, apply_skinning=True)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith('BSBound')]
for o in bpy.context.scene.objects:
    if o.type == 'MESH' and o.name.startswith('BSBound'):
        o.hide_render = True
# Skeleton visual objects (if any) should not render.
for o in bpy.context.scene.objects:
    if o.type == 'MESH' and o not in meshes:
        o.hide_render = True

# --- weight report -------------------------------------------------------------
report = {}
for o in meshes:
    bones = {}
    nweights = []
    unweighted = 0
    for v in o.data.vertices:
        ws = [(o.vertex_groups[g.group].name, g.weight) for g in v.groups
              if not o.vertex_groups[g.group].name.startswith('SBP_') and g.weight > 0]
        if not ws:
            unweighted += 1
        nweights.append(len(ws))
        for n, w in ws:
            bones[n] = bones.get(n, 0.0) + w
    sk_mods = [m for m in o.modifiers if m.type == 'ARMATURE']
    report[o.name] = {'verts': len(o.data.vertices), 'unweighted': unweighted,
                      'max_influences': max(nweights) if nweights else 0,
                      'bones': {k: round(v, 1) for k, v in sorted(bones.items(), key=lambda kv: -kv[1])},
                      'partitions': [g.name for g in o.vertex_groups if g.name.startswith('SBP_')],
                      'armature_mod': bool(sk_mods),
                      'textures': [n.image.filepath for m in o.data.materials if m and m.node_tree
                                   for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]}
open(OUT + '_weights.json', 'w').write(json.dumps(report, indent=2))

# --- test poses ----------------------------------------------------------------
def rot(bone, x=0, y=0, z=0):
    """Rotate a pose bone around armature-space axes (degrees), about its head."""
    pb = arm.pose.bones.get(bone)
    if pb is None:
        return
    R = (Matrix.Rotation(math.radians(z), 4, 'Z') @ Matrix.Rotation(math.radians(y), 4, 'Y')
         @ Matrix.Rotation(math.radians(x), 4, 'X'))
    m = pb.matrix.copy()
    head = m.to_translation()
    m = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ m
    pb.matrix = m
    bpy.context.view_layer.update()

def reset_pose():
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

def apply_pose(name):
    reset_pose()
    if name == 'walk':        # big stride: left leg forward, right back, knee bend, arm swing
        rot('NPC L Thigh [LThg]', x=45); rot('NPC L Calf [LClf]', x=-50)
        rot('NPC R Thigh [RThg]', x=-30); rot('NPC R Calf [RClf]', x=-25)
        rot('NPC L UpperArm [LUar]', x=-30); rot('NPC R UpperArm [RUar]', x=30)
        rot('NPC L Forearm [LLar]', x=40); rot('NPC R Forearm [RLar]', x=40)
    elif name == 'crouch':    # deep crouch / sneak
        rot('NPC Spine [Spn0]', x=-25)
        rot('NPC L Thigh [LThg]', x=80); rot('NPC R Thigh [RThg]', x=80)
        rot('NPC L Calf [LClf]', x=-110); rot('NPC R Calf [RClf]', x=-110)
        rot('NPC L Foot [Lft ]', x=30); rot('NPC R Foot [Rft ]', x=30)
    elif name == 'armsup':    # arms raised sideways (T-ish) and forward bend at elbow
        rot('NPC L UpperArm [LUar]', y=60); rot('NPC R UpperArm [RUar]', y=-60)
        rot('NPC L Forearm [LLar]', x=60); rot('NPC R Forearm [RLar]', x=60)
    elif name == 'twist':     # torso twist and head turn, one hand forward (combat-like)
        rot('NPC Spine1 [Spn1]', z=25); rot('NPC Spine2 [Spn2]', z=20)
        rot('NPC Head [Head]', z=-40)
        rot('NPC R UpperArm [RUar]', x=70); rot('NPC R Forearm [RLar]', x=60)

# --- rendering -----------------------------------------------------------------
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = os.environ.get('ALTAIR_COLOR', 'TEXTURE')
scene.display.shading.show_cavity = False
scene.render.resolution_x = 700; scene.render.resolution_y = 900
scene.render.film_transparent = False
scene.world.color = (0.32, 0.32, 0.34)
bpy.ops.object.camera_add()
cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = float(os.environ.get('ALTAIR_SCALE', '150')); cam.data.clip_end = 5000
scene.camera = cam
center = Vector(tuple(float(c) for c in os.environ.get('ALTAIR_CENTER', '0,0,66').split(',')))
views = {'front': Vector((0, 400, 0)), 'side': Vector((-400, 0, 0)), 'back': Vector((0, -400, 0)),
         'q34': Vector((-280, 280, 60))}
want_views = os.environ.get('ALTAIR_VIEWS', 'front,side,back').split(',')
for pose in POSES:
    apply_pose(pose)
    for vn in want_views:
        cam.location = center + views[vn]
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = f'{OUT}_{pose}_{vn}.png'
        bpy.ops.render.render(write_still=True)
print('INSPECT_DONE', json.dumps({k: (v['verts'], v['unweighted'], v['max_influences']) for k, v in report.items()}))
