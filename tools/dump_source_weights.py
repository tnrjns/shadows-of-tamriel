import bpy, sys, os, json
BASE = r'C:\Users\myste\Downloads\Altair Skyrim Native'
sys.path.insert(0, os.path.join(BASE, 'tooling', 'pynifly-29.1.0'))
import addon_utils
addon_utils.enable('io_scene_nifly', default_set=True, persistent=False)
SRC = r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif'
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.pynifly(filepath=SRC, rename_bones=False, rename_bones_niftools=False, blender_xf=False,
    import_animations=False, import_collisions=False, import_tris=False, apply_skinning=True, import_pose=False)
def cv(p): return (-p[2]*70, p[0]*70, -p[1]*70+69)
rep = {'meshes': {}, 'bones': {}}
for o in bpy.context.scene.objects:
    if o.type == 'ARMATURE':
        for b in o.data.bones:
            h = o.matrix_world @ b.head_local; t = o.matrix_world @ b.tail_local
            rep['bones'][b.name] = {'head': cv(h), 'tail': cv(t), 'parent': b.parent.name if b.parent else None}
    if o.type != 'MESH': continue
    mw = o.matrix_world
    g = {}
    for v in o.data.vertices:
        p = cv(mw @ v.co)
        for e in v.groups:
            n = o.vertex_groups[e.group].name
            if e.weight <= 0: continue
            s = g.setdefault(n, [0.0, 0, [1e9,1e9,1e9], [-1e9,-1e9,-1e9]])
            s[0] += e.weight; s[1] += 1
            for i in range(3):
                s[2][i] = min(s[2][i], p[i]); s[3][i] = max(s[3][i], p[i])
    rep['meshes'][o.name] = {k: [round(v[0],1), v[1], [round(x,1) for x in v[2]], [round(x,1) for x in v[3]]] for k, v in sorted(g.items(), key=lambda kv: -kv[1][0])}
open(out, 'w').write(json.dumps(rep, indent=1))
