import bpy, sys, os, json, math, shutil, traceback
from mathutils import Matrix, Vector

BASE = r'C:\Users\myste\Downloads\Altair Skyrim Native'
ADDON_PARENT = os.path.join(BASE, 'tooling', 'pynifly-29.1.0')
ADDON_MOD = 'io_scene_nifly'
SOURCE_NIF = r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif'
SOURCE_MOD = r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement'
TARGET_NIF = os.path.join(ADDON_PARENT, 'io_scene_nifly', 'skeletons', 'Skyrim', 'skeleton.nif')
NODE_REPORT = os.path.join(BASE, 'node_report.json')
OUT_NIF = os.path.join(BASE, 'meshes', 'armor', 'AltairNative', 'Altair.nif')
os.makedirs(os.path.dirname(OUT_NIF), exist_ok=True)

sys.path.insert(0, ADDON_PARENT)
import addon_utils
addon_utils.enable(ADDON_MOD, default_set=True, persistent=False)

# Start from an empty, deterministic scene.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Import the vanilla Skyrim reference armature first.
bpy.ops.import_scene.pynifly(
    filepath=TARGET_NIF, rename_bones=False, rename_bones_niftools=False,
    blender_xf=False, import_animations=False, import_collisions=False,
    import_tris=False, import_pose=False, apply_skinning=False)
target_arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
if not target_arms:
    raise RuntimeError('PyNifly did not import the Skyrim reference armature')
target_arm = target_arms[-1]
target_arm.name = 'Altair Skyrim Skeleton'
target_arm['PYN_GAME'] = 'SKYRIMSE'
target_arm['PYN_RENAME_BONES'] = False
target_arm['PYN_RENAME_BONES_NIFTOOLS'] = False
target_arm['PYN_BLENDER_XF'] = False
valid_bones = set(target_arm.data.bones.keys())

# Import Altaïr independently so the game-specific source rig stays available only
# long enough to remap its weights.
source_before = {o.name for o in bpy.context.scene.objects}
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = None
bpy.ops.import_scene.pynifly(
    filepath=SOURCE_NIF, rename_bones=False, rename_bones_niftools=False,
    blender_xf=False, import_animations=False, import_collisions=False,
    import_tris=False, apply_skinning=True, import_pose=False)
source_objects = [o for o in bpy.context.scene.objects if o.name not in source_before]
source_meshes = [o for o in source_objects if o.type == 'MESH']
source_armatures = [o for o in source_objects if o.type == 'ARMATURE']
if not source_meshes:
    raise RuntimeError('PyNifly imported no Altaïr meshes')

# Convert the Altaïr model's Y-down, Z-lateral, meter-scale coordinates to Skyrim's
# X-lateral, Y-depth, Z-up, 70-units-per-meter coordinates, with its source root at
# Skyrim pelvis height.
node_data = json.load(open(NODE_REPORT, encoding='utf-8'))
source_nodes = {n['name']: tuple(float(v) for v in n['pos']) for n in node_data['src']['nodes']}
target_nodes = {n['name']: tuple(float(v) for v in n['pos']) for n in node_data['target']['nodes']}
allow = []
for name in target_nodes:
    if name not in valid_bones:
        continue
    if name in {'NPC Root [Root]', 'NPC Pelvis [Pelv]', 'NPC Spine [Spn0]', 'NPC Spine1 [Spn1]',
                'NPC Spine2 [Spn2]', 'NPC Neck [Neck]', 'NPC Head [Head]',
                'NPC L Thigh [LThg]', 'NPC L Calf [LClf]', 'NPC L Foot [Lft ]', 'NPC L Toe0 [LToe]',
                'NPC R Thigh [RThg]', 'NPC R Calf [RClf]', 'NPC R Foot [Rft ]', 'NPC R Toe0 [RToe]',
                'NPC L Clavicle [LClv]', 'NPC L UpperArm [LUar]', 'NPC L Forearm [LLar]', 'NPC L Hand [LHnd]',
                'NPC R Clavicle [RClv]', 'NPC R UpperArm [RUar]', 'NPC R Forearm [RLar]', 'NPC R Hand [RHnd]'}:
        allow.append(name)
    elif any(name.startswith(f'NPC {side} Finger') for side in ('L', 'R')) or \
         any(name.startswith(f'NPC {side} ') and ('Twist' in name) for side in ('L', 'R')):
        allow.append(name)
if not allow:
    raise RuntimeError('No canonical Skyrim deform bones were found')

def convert_point(xyz):
    x, y, z = xyz
    return (-z * 70.0, x * 70.0, -y * 70.0 + 69.0)

def map_source_bone(source_name):
    if source_name not in source_nodes:
        return 'NPC Pelvis [Pelv]', 999.0
    pos = convert_point(source_nodes[source_name])
    best = min(allow, key=lambda nm: math.dist(pos, target_nodes[nm]))
    return best, math.dist(pos, target_nodes[best])

mapping_log = []
for mesh in source_meshes:
    old_groups = list(mesh.vertex_groups)
    # Bone influence weights are accumulated under the nearest Skyrim deform bones;
    # SBP body-slot groups are retained so PyNifly emits the original armor partition.
    vertex_weights = [dict() for _ in mesh.data.vertices]
    partition_weights = {}
    for group in old_groups:
        if group.name.startswith('SBP_'):
            memberships = []
            for v in mesh.data.vertices:
                try:
                    w = group.weight(v.index)
                except RuntimeError:
                    continue
                memberships.append((v.index, w))
            partition_weights[group.name] = memberships
            continue
        target_name, dist = map_source_bone(group.name)
        mapping_log.append({'mesh': mesh.name, 'source_bone': group.name,
                            'target_bone': target_name, 'distance': round(dist, 2)})
        for v in mesh.data.vertices:
            try:
                w = group.weight(v.index)
            except RuntimeError:
                continue
            vertex_weights[v.index][target_name] = vertex_weights[v.index].get(target_name, 0.0) + w

    # Bake source mesh object transforms and apply the validated axis/scale/pelvis conversion.
    source_world = mesh.matrix_world.copy()
    for v in mesh.data.vertices:
        p = source_world @ v.co
        v.co = Vector(convert_point((p.x, p.y, p.z)))

    # Clear the old hashed skeleton and restore an identity object transform; the converted
    # vertex positions now live directly in Skyrim armature space.
    mesh.parent = None
    mesh.matrix_world = Matrix.Identity(4)
    for mod in list(mesh.modifiers):
        mesh.modifiers.remove(mod)
    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)

    new_groups = {name: mesh.vertex_groups.new(name=name) for name in allow}
    for name in partition_weights:
        mesh.vertex_groups.new(name=name)
    for vidx, weights in enumerate(vertex_weights):
        if not weights:
            weights = {'NPC Pelvis [Pelv]': 1.0}
        top = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:4]
        total = sum(w for _, w in top)
        for name, w in top:
            if name in new_groups and w > 0.0:
                new_groups[name].add([vidx], w / total, 'REPLACE')
    for group_name, memberships in partition_weights.items():
        g = mesh.vertex_groups[group_name]
        for vidx, w in memberships:
            g.add([vidx], w, 'REPLACE')

    arm = mesh.modifiers.new('Skyrim Skeleton Weights', 'ARMATURE')
    arm.object = target_arm
    mesh['PYN_GAME'] = 'SKYRIMSE'
    mesh['PYN_BLENDER_XF'] = False
    mesh['PYN_RENAME_BONES'] = False
    mesh['PYN_RENAME_BONES_NIFTOOLS'] = False

# Discard the source rig and its helper nodes; the exported shapes now use only Skyrim bones.
for obj in source_objects:
    if obj.type != 'MESH' and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

# Bring textures into this independent MO2 mod. Source NIF texture paths are already
# relative (textures\\<hash>.dds), so they remain valid without editing source assets.
for root, dirs, files in os.walk(os.path.join(SOURCE_MOD, 'textures')):
    for fn in files:
        if fn.lower().endswith('.dds'):
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, os.path.join(SOURCE_MOD, 'textures'))
            dst = os.path.join(BASE, 'textures', rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

# Store explicit, stable NIF export settings (the vanilla skeleton template carries
# broad defaults that would otherwise serialize every helper bone).
from io_scene_nifly.util.settings import ExportSettings
from io_scene_nifly.nif.pyn_props import write_export_settings
settings = ExportSettings()
settings.game = 'SKYRIMSE'
settings.rename_bones = False
settings.rename_bones_niftools = False
settings.rotate_bones_pretty = False
settings.blender_xf = False
settings.export_pose = False
settings.preserve_hierarchy = False
settings.export_all_bones = False
settings.write_bodytri = False
settings.export_modifiers = False
settings.export_animations = False
settings.export_colors = True
settings.write_tris = False
for mesh in source_meshes:
    write_export_settings(mesh, target_arm, settings)

# Export the skinned meshes as a Skyrim SE NIF.
bpy.ops.object.select_all(action='DESELECT')
target_arm.select_set(True)
for mesh in source_meshes:
    mesh.select_set(True)
bpy.context.view_layer.objects.active = target_arm
res = bpy.ops.export_scene.pynifly(
    filepath=OUT_NIF, target_game='SKYRIMSE', intuit_defaults=True,
    blender_xf=False, rename_bones=False, rename_bones_niftools=False,
    rotate_bones_pretty=False, preserve_hierarchy=False, export_all_bones=False,
    write_bodytri=False, export_pose=False, export_modifiers=False,
    export_animations=False, export_colors=True, write_tris=False)
if not os.path.isfile(OUT_NIF):
    raise RuntimeError(f'PyNifly export failed: {res}')

with open(os.path.join(BASE, 'bone_mapping.json'), 'w', encoding='utf-8') as f:
    json.dump(mapping_log, f, indent=2)
print('NATIVE_BUILD_RESULT', json.dumps({'result': sorted(res), 'nif': OUT_NIF,
      'source_meshes': len(source_meshes), 'valid_skyrim_bones': len(allow),
      'mapping_entries': len(mapping_log), 'target_armature': target_arm.name,
      'armature_bone_count': len(target_arm.data.bones)}, indent=2))

