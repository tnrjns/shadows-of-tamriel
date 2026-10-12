"""Rebuild the Skyrim-native Altair outfit NIF with explicit (hierarchy-based) bone mapping.

Differences from build_native.py (v1):
  * Source bones are mapped to Skyrim bones by their role in the source hierarchy, not by
    nearest bind position (v1 sent chest/clavicle weights to Neck, lip/jaw bones to the
    clavicles, and coat tails to the calves).
  * Legs and arms are conformed to the vanilla skeleton's joint positions (Altair's knee sat
    ~5 units above Skyrim's), using the original source weights to deform the mesh.
  * The eyes/teeth/tongue sub-mesh, whose bind sat at the pelvis, is moved into the head.
  * Loose weapon props (sword, dagger) bound to origin-bind weapon bones are dropped.
  * Textures are referenced from textures\\armor\\AltairNative\\ with a shared flat normal map.

Run: blender -b --factory-startup -P tools/build_native_v2.py -- <out_dir>
Writes <out_dir>/meshes/armor/AltairNative/Altair.nif and 1stPersonAltair.nif plus a report.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Matrix, Vector

BASE = r'C:\Users\myste\Downloads\Altair Skyrim Native'
ADDON_PARENT = os.path.join(BASE, 'tooling', 'pynifly-29.1.0')
SOURCE_NIF = r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif'
TARGET_NIF = os.path.join(ADDON_PARENT, 'io_scene_nifly', 'skeletons', 'Skyrim', 'skeleton.nif')
OUT_DIR = sys.argv[sys.argv.index('--') + 1]
MESH_DIR = os.path.join(OUT_DIR, 'meshes', 'armor', 'AltairNative')
os.makedirs(MESH_DIR, exist_ok=True)
TEX_PREFIX = 'textures\\armor\\AltairNative\\'
FLAT_NORMAL = TEX_PREFIX + 'altair_flat_n.dds'

sys.path.insert(0, ADDON_PARENT)
import addon_utils
addon_utils.enable('io_scene_nifly', default_set=True, persistent=False)

DROP_SHAPES = {'ARCM_Altair_Sword_D', 'UCMA_Altair_Dagger'}
COAT_SHAPES = {'UCMA_Altair_Cloth', 'UCMA_Altair_Cloth_UP', 'UCMA_Altair_Flaps'}
FACE_PARTS = 'Universal_Head_Obj_Clean'

PELV, SPN0, SPN1, SPN2 = 'NPC Pelvis [Pelv]', 'NPC Spine [Spn0]', 'NPC Spine1 [Spn1]', 'NPC Spine2 [Spn2]'
NECK, HEAD = 'NPC Neck [Neck]', 'NPC Head [Head]'

def side(s):
    return {'clv': f'NPC {s} Clavicle [{s}Clv]', 'uar': f'NPC {s} UpperArm [{s}Uar]',
            'ut1': f'NPC {s} UpperarmTwist1 [{s}Ut1]', 'ut2': f'NPC {s} UpperarmTwist2 [{s}Ut2]',
            'lar': f'NPC {s} Forearm [{s}Lar]', 'lt1': f'NPC {s} ForearmTwist1 [{s}Lt1]',
            'lt2': f'NPC {s} ForearmTwist2 [{s}Lt2]', 'hnd': f'NPC {s} Hand [{s}Hnd]',
            'thg': f'NPC {s} Thigh [{s}Thg]', 'clf': f'NPC {s} Calf [{s}Clf]',
            'ft': f'NPC {s} Foot [{s}ft ]', 'toe': f'NPC {s} Toe0 [{s}Toe]',
            'f': lambda a, b: f'NPC {s} Finger{a}{b} [{s}F{a}{b}]'}
L, R = side('L'), side('R')

# Source bone -> {skyrim bone: fraction}. Derived from the source hierarchy (see HANDOFF /
# node_report.json); hashed names are the AC1 rig's.
MAP = {
    # root / pelvis / spine
    'bone_2c52cbb0': {PELV: 1}, 'bone_ded10611': {PELV: 1}, 'bone_530ec1cb': {SPN0: 1},
    'bone_8f39fa4e': {SPN1: 1}, 'bone_1630abf4': {SPN2: 1},
    'bone_cbf50abc': {SPN1: 1}, 'bone_074201fc': {SPN1: 1},
    'bone_8d0e40e2': {SPN2: 1}, 'bone_2c7ac18f': {SPN2: 1},
    'bone_3ed4e1a3': {SPN0: 1}, 'bone_a7ddb019': {SPN0: 1},
    'bone_c0ee3e2a': {PELV: 1}, 'bone_1249f0a3': {PELV: 1},
    'bone_a62e0eb3': {SPN2: 0.5, NECK: 0.5},
    'bone_8023796d': {NECK: 1}, 'bone_c68a1d48': {NECK: 1},
    # weapon/prop carriers: rigid on the torso
    'bone_d361bbe9': {SPN2: 1}, 'bone_685e46b6': {SPN2: 1},
    'bone_b62122f9': {PELV: 1}, 'bone_3a835926': {PELV: 1},
    # left arm
    'bone_b898b609': {L['clv']: 1}, 'bone_26810577': {L['clv']: 0.5, L['ut1']: 0.5},
    'bone_98b98abb': {L['clv']: 1}, 'bone_eb830ada': {L['uar']: 1},
    'bone_284003a7': {L['ut1']: 1}, 'bone_6fe07977': {L['ut2']: 1},
    'bone_89b93a80': {L['lar']: 1}, 'bone_e6ef593e': {L['lar']: 1},
    'bone_aff64c10': {L['lt1']: 1}, 'bone_84fab7bb': {L['lt1']: 1},
    'bone_b675f36c': {L['hnd']: 1},
    # right arm
    'bone_63d89144': {R['clv']: 1}, 'bone_15236c13': {R['clv']: 0.5, R['ut1']: 0.5},
    'bone_6bb3f727': {R['uar']: 1}, 'bone_0739e93a': {R['ut1']: 1}, 'bone_409993ea': {R['ut2']: 1},
    'bone_7257a1aa': {R['lar']: 1}, 'bone_6ab4d2e5': {R['lar']: 1},
    'bone_2bc69c58': {R['lt1']: 1}, 'bone_75f94d30': {R['hnd']: 1},
    # left leg + left coat chains
    'bone_176183f0': {L['thg']: 1}, 'bone_060df401': {L['clf']: 1}, 'bone_ee938089': {L['clf']: 1},
    'bone_58988870': {L['ft']: 1}, 'bone_058b96dd': {L['toe']: 1},
    'bone_39a40592': {L['thg']: 1}, 'bone_94247fa4': {L['thg']: 1}, 'bone_f9ce17a1': {L['thg']: 1},
    'bone_c4903a44': {L['thg']: 0.8, L['clf']: 0.2},
    'bone_e243588c': {PELV: 0.35, L['thg']: 0.65}, 'bone_0d8133b2': {PELV: 0.35, L['thg']: 0.65},
    'bone_40da34be': {L['thg']: 1},
    'bone_9a17b560': {PELV: 0.5, L['thg']: 0.5}, 'bone_6e589173': {PELV: 0.5, L['thg']: 0.5},
    # right leg + right coat chains
    'bone_757f1291': {R['thg']: 1}, 'bone_863d09fc': {R['clf']: 1}, 'bone_62c80b52': {R['clf']: 1},
    'bone_9b14362c': {R['ft']: 1}, 'bone_e556c9be': {R['toe']: 1},
    'bone_28295545': {R['thg']: 1}, 'bone_20137710': {R['thg']: 1}, 'bone_90ff34b8': {R['thg']: 1},
    'bone_a092a3a7': {R['thg']: 0.8, R['clf']: 0.2},
    'bone_8b727b95': {PELV: 0.35, R['thg']: 0.65}, 'bone_64b010ab': {PELV: 0.35, R['thg']: 0.65},
    'bone_24d8ad5d': {R['thg']: 1},
    'bone_f3269679': {PELV: 0.5, R['thg']: 0.5}, 'bone_0769b26a': {PELV: 0.5, R['thg']: 0.5},
}
# Fingers: thumb, index, middle, ring, pinky chains (base -> tip).
FINGERS = {
    'L': [['bone_78f4e1ac', 'bone_e1fdb016', 'bone_96fa8080'], ['bone_1e679ed0', 'bone_876ecf6a', 'bone_f069fffc'],
        ['bone_911fbacf', 'bone_0816eb75', 'bone_7f11dbe3'], ['bone_d34048cf', 'bone_4a491975'],
        ['bone_f4a6edbc', 'bone_6dafbc06', 'bone_1aa88c90']],
    'R': [['bone_9829becf', 'bone_0120ef75', 'bone_7627dfe3'], ['bone_febac1b3', 'bone_67b39009', 'bone_10b4a09f'],
        ['bone_45445772', 'bone_dc4d06c8', 'bone_ab4a365e'], ['bone_dbf635c5', 'bone_42ff647f', 'bone_35f854e9'],
        ['bone_147bb2df', 'bone_8d72e365', 'bone_fa75d3f3']],
}
FINGER_BONES = set()
for sk, chains in FINGERS.items():
    sd = L if sk == 'L' else R
    for fi, chain in enumerate(chains):
        for ji, b in enumerate(chain):
            MAP[b] = {sd['f'](fi, ji): 1}
            FINGER_BONES.add(b)
# Bones whose weight is split between Neck and Head by vertex height (Altair's skull pivot
# sits lower than Skyrim's Head joint, so his neck must not swing with the Head bone).
HEAD_SPLIT = {'bone_07c159a2', 'bone_9088ea6c', 'bone_8c5b399b'}
NECK_TO_HEAD_Z = (111.0, 118.0)

def convert_point(p):
    x, y, z = p
    return Vector((-z * 70.0, x * 70.0, -y * 70.0 + 69.0))

AXIS = Matrix(((0, 0, -70, 0), (70, 0, 0, 0), (0, -70, 0, 69), (0, 0, 0, 1)))  # == convert_point

# ---------------------------------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.pynifly(filepath=TARGET_NIF, rename_bones=False, rename_bones_niftools=False,
    blender_xf=False, import_animations=False, import_collisions=False, import_tris=False,
    import_pose=False, apply_skinning=False)
target_arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][-1]
target_arm.name = 'Altair Skyrim Skeleton'
tb = {b.name: target_arm.matrix_world @ b.head_local for b in target_arm.data.bones}

before = {o.name for o in bpy.context.scene.objects}
bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = None
bpy.ops.import_scene.pynifly(filepath=SOURCE_NIF, rename_bones=False, rename_bones_niftools=False,
    blender_xf=False, import_animations=False, import_collisions=False, import_tris=False,
    apply_skinning=True, import_pose=False)
src_objs = [o for o in bpy.context.scene.objects if o.name not in before]
src_meshes = [o for o in src_objs if o.type == 'MESH']
src_arm = [o for o in src_objs if o.type == 'ARMATURE'][0]
src_helper_names = [o.name for o in src_objs if o.type != 'MESH']
sb = {b.name: convert_point(src_arm.matrix_world @ b.head_local) for b in src_arm.data.bones}
sparent = {b.name: (b.parent.name if b.parent else None) for b in src_arm.data.bones}

# Every descendant of the source skull bone that is not otherwise mapped is a face bone.
def descendants(root):
    out, stack = set(), [root]
    while stack:
        n = stack.pop()
        for k, p in sparent.items():
            if p == n and k not in out:
                out.add(k); stack.append(k)
    return out
for b in descendants('bone_07c159a2') | {'bone_07c159a2', 'bone_9088ea6c', 'bone_8c5b399b'}:
    MAP.setdefault(b, {HEAD: 1})

# ---- conform transforms (legs/arms to Skyrim joints) ----------------------------------
def seg_xform(hs, cs, ht, ct, scale=True):
    ds, dt = (cs - hs), (ct - ht)
    s = dt.length / ds.length if scale else 1.0
    d = ds.normalized()
    S = Matrix.Identity(3) + (s - 1.0) * Matrix(((d.x*d.x, d.x*d.y, d.x*d.z),
                                                (d.y*d.x, d.y*d.y, d.y*d.z),
                                                (d.z*d.x, d.z*d.y, d.z*d.z)))
    Rm = ds.normalized().rotation_difference(dt.normalized()).to_matrix()
    M3 = Rm @ S
    M = M3.to_4x4()
    M.translation = ht - M3 @ hs
    return M, Rm, s

CONFORM = {}
conform_log = {}
for sd, sname, src in ((L, 'L', dict(thigh='bone_176183f0', calf='bone_060df401', foot='bone_58988870',
                                      upper='bone_eb830ada', fore='bone_89b93a80', hand='bone_b675f36c')),
                       (R, 'R', dict(thigh='bone_757f1291', calf='bone_863d09fc', foot='bone_9b14362c',
                                      upper='bone_6bb3f727', fore='bone_7257a1aa', hand='bone_75f94d30'))):
    hip_s, knee_s, ank_s = sb[src['thigh']], sb[src['calf']], sb[src['foot']]
    hip_t, knee_t = tb[sd['thg']], tb[sd['clf']]
    # Keep Altair's thicker boot sole on the ground: ankle goes to Skyrim's ankle in X/Y but
    # only drops enough to bring the sole from z~1.2 to z~0.2.
    ank_t = Vector((tb[sd['ft']].x, tb[sd['ft']].y, ank_s.z - 1.0))
    A_thigh, _, s1 = seg_xform(hip_s, knee_s, hip_t, knee_t)
    A_calf, _, s2 = seg_xform(knee_s, ank_s, knee_t, ank_t)
    A_foot = Matrix.Translation(ank_t - ank_s)
    sh_s, el_s, wr_s = sb[src['upper']], sb[src['fore']], sb[src['hand']]
    sh_t, el_t, wr_t = tb[sd['uar']], tb[sd['lar']], tb[sd['hnd']]
    A_upper, _, s3 = seg_xform(sh_s, el_s, sh_t, el_t)
    A_fore, R_fore, s4 = seg_xform(el_s, wr_s, el_t, wr_t)
    A_hand = Matrix.Translation(wr_t) @ R_fore.to_4x4() @ Matrix.Translation(-wr_s)
    groups = {
        'thigh': ([src['thigh'], 'bone_39a40592' if sname == 'L' else 'bone_28295545'], A_thigh),
        'calf': ([src['calf'], 'bone_ee938089' if sname == 'L' else 'bone_62c80b52'], A_calf),
        'foot': ([src['foot'], 'bone_058b96dd' if sname == 'L' else 'bone_e556c9be'], A_foot),
        'upper': ([src['upper']] + (['bone_284003a7', 'bone_6fe07977'] if sname == 'L' else ['bone_0739e93a', 'bone_409993ea']), A_upper),
        'fore': ([src['fore']] + (['bone_aff64c10', 'bone_84fab7bb', 'bone_e6ef593e'] if sname == 'L' else ['bone_2bc69c58', 'bone_6ab4d2e5']), A_fore),
        'hand': ([src['hand']] + [b for ch in FINGERS[sname] for b in ch], A_hand),
    }
    for g, (bones, A) in groups.items():
        for b in bones:
            CONFORM[b] = A
    conform_log[sname] = {'thigh_scale': round(s1, 3), 'calf_scale': round(s2, 3),
                          'upperarm_scale': round(s3, 3), 'forearm_scale': round(s4, 3),
                          'knee_src': [round(v, 1) for v in knee_s], 'knee_dst': [round(v, 1) for v in knee_t],
                          'ankle_src': [round(v, 1) for v in ank_s], 'ankle_dst': [round(v, 1) for v in ank_t]}

def clamp01(t):
    return max(0.0, min(1.0, t))

# ---- per-mesh conversion -------------------------------------------------------------
report = {'conform': conform_log, 'dropped_shapes': sorted(DROP_SHAPES), 'shapes': {}}
unmapped = {}
keep_meshes = []
for mesh in src_meshes:
    if mesh.name in DROP_SHAPES:
        bpy.data.objects.remove(mesh, do_unlink=True)
        continue
    keep_meshes.append(mesh)
    me = mesh.data
    mw = mesh.matrix_world.copy()
    names = {g.index: g.name for g in mesh.vertex_groups}
    srcw = []
    for v in me.vertices:
        srcw.append({names[g.group]: g.weight for g in v.groups
                     if g.weight > 0 and not names[g.group].startswith('SBP_')})
    world = [AXIS @ (mw @ v.co) for v in me.vertices]
    nrm_lin = AXIS.to_3x3() @ mw.to_3x3()

    # Corner normals in source space (custom split normals from the NIF), moved to world.
    corner_normals = [Vector(cn.vector) for cn in me.corner_normals]

    new_pos = []
    vert_lin = []      # per-vertex 3x3 used to carry normals
    if mesh.name == FACE_PARTS:
        # Eyes/teeth/tongue: rigidly move from their origin bind into the skull. In this
        # sub-mesh "down" is +Y and "forward" is +Z (axis-converted); eyelid bones give the
        # eye centres in the head.
        eye_idx = [i for i, w in enumerate(srcw) if 'bone_18100292' in w or 'bone_1ce92143' in w]
        c_obj = sum((world[i] for i in eye_idx), Vector()) / len(eye_idx)
        lids = ['bone_a30bfd0f', 'bone_fb157b83', 'bone_a4c7c415', 'bone_dfce215c']
        c_head = sum((sb[b] for b in lids), Vector()) / len(lids)
        Rx = Matrix.Rotation(math.radians(-90), 3, 'X')
        for p in world:
            new_pos.append(Rx @ (p - c_obj) + c_head)
            vert_lin.append(Rx)
        report['face_parts_offset'] = {'eye_centre_src': list(c_obj), 'eye_centre_head': list(c_head)}
    else:
        conform = mesh.name not in COAT_SHAPES
        I4 = Matrix.Identity(4)
        for i, p in enumerate(world):
            ws = srcw[i]
            tot = sum(ws.values())
            if not conform or tot <= 0:
                new_pos.append(p.copy()); vert_lin.append(Matrix.Identity(3)); continue
            acc = Matrix(((0,)*4,)*4)
            for b, w in ws.items():
                A = CONFORM.get(b, I4)
                acc = acc + A * (w / tot)
            new_pos.append(acc @ p)
            vert_lin.append(acc.to_3x3())

    # Skyrim weights
    out_w = []
    for i, ws in enumerate(srcw):
        acc = {}
        if mesh.name == FACE_PARTS:
            acc = {HEAD: 1.0}
        else:
            z = new_pos[i].z
            for b, w in ws.items():
                if b in HEAD_SPLIT:
                    t = clamp01((z - NECK_TO_HEAD_Z[0]) / (NECK_TO_HEAD_Z[1] - NECK_TO_HEAD_Z[0]))
                    targets = {HEAD: t, NECK: 1.0 - t}
                else:
                    targets = MAP.get(b)
                    if targets is None:
                        unmapped[b] = unmapped.get(b, 0) + w
                        targets = {PELV: 1}
                for tname, f in targets.items():
                    if f > 0:
                        acc[tname] = acc.get(tname, 0.0) + w * f
        if not acc:
            acc = {PELV: 1.0}
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
        top = [(n, w) for n, w in top if w >= 0.01] or top[:1]
        s = sum(w for _, w in top)
        out_w.append({n: w / s for n, w in top})

    # Apply geometry
    for v, p in zip(me.vertices, new_pos):
        v.co = p
    mesh.parent = None
    mesh.matrix_world = Matrix.Identity(4)
    for mod in list(mesh.modifiers):
        mesh.modifiers.remove(mod)
    for g in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(g)
    # Normals: carry source custom normals through the same per-vertex transform.
    new_cn = []
    for loop in me.loops:
        M = vert_lin[loop.vertex_index] @ nrm_lin
        n = (M.inverted_safe().transposed() @ corner_normals[loop.index])
        new_cn.append(n.normalized() if n.length > 1e-8 else Vector((0, 0, 1)))
    me.normals_split_custom_set(new_cn)

    groups = {}
    for vi, ws in enumerate(out_w):
        for n, w in ws.items():
            if n not in target_arm.data.bones:
                raise RuntimeError(f'{n} is not a Skyrim skeleton bone')
            g = groups.get(n) or groups.setdefault(n, mesh.vertex_groups.new(name=n))
            g.add([vi], w, 'REPLACE')
    part = mesh.vertex_groups.new(name='SBP_32_BODY')
    part.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    arm_mod = mesh.modifiers.new('Skyrim Skeleton Weights', 'ARMATURE')
    arm_mod.object = target_arm
    for k, val in (('PYN_GAME', 'SKYRIMSE'), ('PYN_BLENDER_XF', False),
                   ('PYN_RENAME_BONES', False), ('PYN_RENAME_BONES_NIFTOOLS', False)):
        mesh[k] = val

    # Textures: mod-specific folder + flat normal map.
    for mat in me.materials:
        if not mat:
            continue
        diff = mat.get('BSShaderTextureSet_Diffuse', '')
        base = os.path.basename(diff.replace('\\', '/')) if diff else None
        if not base:
            raise RuntimeError(f'{mesh.name}: no diffuse texture path on material')
        mat['BSShaderTextureSet_Diffuse'] = TEX_PREFIX + base
        mat['BSShaderTextureSet_Normal'] = FLAT_NORMAL
        if mat.node_tree:
            for n in [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']:
                mat.node_tree.nodes.remove(n)

    if mesh.name == FACE_PARTS:
        # Teeth/tongue were bound to their own origin-bind bones and cannot be placed with the
        # eye transform; Skyrim never opens this face's mouth, so only the eyes are kept.
        eye_set = {'bone_18100292', 'bone_1ce92143'}
        keep = [bool(srcw[i]) and max(srcw[i], key=srcw[i].get) in eye_set for i in range(len(srcw))]
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context='VERTS')
        bm.to_mesh(me); bm.free()
        new_pos = [p for p, k in zip(new_pos, keep) if k]
        out_w = [w for w, k in zip(out_w, keep) if k]
        report['face_parts_kept'] = 'eyes only (%d verts)' % len(me.vertices)

    bones_used = {}
    for ws in out_w:
        for n, w in ws.items():
            bones_used[n] = bones_used.get(n, 0.0) + w
    zs = [p.z for p in new_pos]
    report['shapes'][mesh.name] = {
        'verts': len(me.vertices), 'z_range': [round(min(zs), 2), round(max(zs), 2)],
        'max_influences': max(len(w) for w in out_w),
        'bones': {k: round(v, 1) for k, v in sorted(bones_used.items(), key=lambda kv: -kv[1])}}
report['unmapped_source_bones'] = {k: round(v, 2) for k, v in unmapped.items()}

for name in src_helper_names:
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

# ---- export ----------------------------------------------------------------------------
from io_scene_nifly.util.settings import ExportSettings
from io_scene_nifly.nif.pyn_props import write_export_settings
settings = ExportSettings()
settings.game = 'SKYRIMSE'
for k in ('rename_bones', 'rename_bones_niftools', 'rotate_bones_pretty', 'blender_xf', 'export_pose',
          'preserve_hierarchy', 'export_all_bones', 'write_bodytri', 'export_modifiers',
          'export_animations', 'write_tris'):
    setattr(settings, k, False)
settings.export_colors = True

def export(objs, path):
    for m in objs:
        write_export_settings(m, target_arm, settings)
    bpy.ops.object.select_all(action='DESELECT')
    target_arm.select_set(True)
    for m in objs:
        m.select_set(True)
    bpy.context.view_layer.objects.active = target_arm
    res = bpy.ops.export_scene.pynifly(
        filepath=path, target_game='SKYRIMSE', intuit_defaults=True, blender_xf=False,
        rename_bones=False, rename_bones_niftools=False, rotate_bones_pretty=False,
        preserve_hierarchy=False, export_all_bones=False, write_bodytri=False, export_pose=False,
        export_modifiers=False, export_animations=False, export_colors=True, write_tris=False)
    if not os.path.isfile(path):
        raise RuntimeError(f'export failed {path}: {res}')
    return sorted(res)

third = os.path.join(MESH_DIR, 'Altair.nif')
report['export_3rd'] = export(keep_meshes, third)

# First person: only arm/hand geometry of the body shape (vanilla 1st-person meshes are arms).
ARM_KEYS = ('Clavicle', 'UpperArm', 'Upperarm', 'Forearm', 'Hand', 'Finger')
body = bpy.data.objects['UCMA_Altair_Body_C']
fp = body.copy(); fp.data = body.data.copy(); fp.name = 'UCMA_Altair_Arms_1st'
bpy.context.scene.collection.objects.link(fp)
gname = {g.index: g.name for g in fp.vertex_groups}
def dominant(v):
    ws = [(gname[g.group], g.weight) for g in v.groups if not gname[g.group].startswith('SBP_')]
    return max(ws, key=lambda t: t[1])[0] if ws else ''
is_arm = [any(k in dominant(v) for k in ARM_KEYS) and 'Clavicle' not in dominant(v) for v in fp.data.vertices]
bm = bmesh.new(); bm.from_mesh(fp.data)
bm.verts.ensure_lookup_table()
kill = [f for f in bm.faces if not all(is_arm[v.index] for v in f.verts)]
bmesh.ops.delete(bm, geom=kill, context='FACES')
loose = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context='VERTS')
bm.to_mesh(fp.data); bm.free()
fp.modifiers.clear()
m = fp.modifiers.new('Skyrim Skeleton Weights', 'ARMATURE'); m.object = target_arm
for k in ('PYN_GAME', 'PYN_BLENDER_XF', 'PYN_RENAME_BONES', 'PYN_RENAME_BONES_NIFTOOLS'):
    fp[k] = body[k]
report['first_person_verts'] = len(fp.data.vertices)
report['export_1st'] = export([fp], os.path.join(MESH_DIR, '1stPersonAltair.nif'))

open(os.path.join(OUT_DIR, 'build_v2_report.json'), 'w', encoding='utf-8').write(json.dumps(report, indent=2))
print('BUILD_V2', json.dumps({'shapes': list(report['shapes']), 'unmapped': report['unmapped_source_bones'],
                              'conform': conform_log, 'fp_verts': report['first_person_verts']}, indent=1))
