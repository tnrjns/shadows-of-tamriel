import bpy, sys, json, os
addon=r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly'
sys.path.insert(0, os.path.dirname(addon))
import addon_utils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=False)
print("ADDON KEYS", [a.module for a in bpy.context.preferences.addons])
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.pynifly(filepath=r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif', import_animations=False, import_collisions=False, import_tris=False, rename_bones=False, blender_xf=False)
# Preview the source Y-up model after rotating it into Skyrim/Blender Z-up.
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,0))
root=bpy.context.object; root.name='Axis Preview (Y-up to Z-up)'; from mathutils import Matrix
root.rotation_mode='QUATERNION'; root.rotation_quaternion=(Matrix.Rotation(1.57079632679,4,'Z') @ Matrix.Rotation(-1.57079632679,4,'X')).to_quaternion(); root.scale=(70,70,70); root.location=(0,0,69)
for o in list(bpy.context.scene.objects):
    if o is not root and o.type not in {'CAMERA','LIGHT'}:
        o.parent=root; o.matrix_parent_inverse=Matrix.Identity(4)
bpy.context.view_layer.update()
print('ROOT', list(root.matrix_world)); print('MESH WORLD', list(next(o for o in bpy.context.scene.objects if o.type=='MESH').matrix_world))
# inspect contents and bounds
from mathutils import Vector
report=[]
for obj in bpy.context.scene.objects:
    entry={'name':obj.name,'type':obj.type,'loc':list(obj.location),'rot':list(obj.rotation_euler),'scale':list(obj.scale)}
    if obj.type=='MESH':
        pts=[obj.matrix_world @ v.co for v in obj.data.vertices]
        if pts:
            entry['bounds']=[[min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)]]
        entry['verts']=len(obj.data.vertices)
        entry['groups']=[g.name for g in obj.vertex_groups]
        entry['materials']=[m.name if m else None for m in obj.data.materials]
        entry['parent']=obj.parent.name if obj.parent else None
    elif obj.type=='ARMATURE':
        entry['bones']=[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None} for b in obj.data.bones]
    report.append(entry)
open(r'C:\Users\myste\Downloads\Altair Skyrim Native\inspect_source.json','w').write(json.dumps(report,indent=2))
# simple render
for o in bpy.context.scene.objects:
    if o.type=='MESH':
        for m in o.modifiers:
            if m.type=='ARMATURE': m.show_render=False; m.show_viewport=False
bpy.context.scene.render.engine='BLENDER_EEVEE'
bpy.context.scene.render.resolution_x=900;bpy.context.scene.render.resolution_y=900;bpy.context.scene.render.resolution_percentage=100
# frame centered all meshes
coords=[]
for o in bpy.context.scene.objects:
    if o.type=='MESH': coords.extend([o.matrix_world@Vector(c) for c in o.bound_box])
lo=Vector(tuple(min(p[i] for p in coords) for i in range(3))); hi=Vector(tuple(max(p[i] for p in coords) for i in range(3))); center=(lo+hi)/2
# orient camera from x=2.7, y=-4, z=2.4 assuming Y-up? camera sees all regardless
bpy.ops.object.camera_add(location=center+Vector((350,150,150)))
cam=bpy.context.object; cam.data.type='ORTHO'; cam.data.ortho_scale=max(hi-lo)*1.55; print('CENTER_EXT', list(center), list(hi-lo), 'CAM', list(cam.location), 'HIDE', [(o.name,o.hide_render) for o in bpy.context.scene.objects if o.type=='MESH'][:3]); cam.data.clip_end=10000; cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler(); bpy.context.scene.camera=cam
bpy.ops.object.light_add(type='AREA', location=center+Vector((80,140,210))); bpy.context.object.data.energy=1200
bpy.ops.object.light_add(type='AREA', location=center+Vector((-150,-90,120))); bpy.context.object.data.energy=900
bpy.context.scene.world.color=(0.16,0.16,0.16)
bpy.context.scene.render.image_settings.file_format='PNG'; bpy.context.scene.render.filepath=r'C:\Users\myste\Downloads\Altair Skyrim Native\altair_converted_front.png'
bpy.ops.render.render(write_still=True)












