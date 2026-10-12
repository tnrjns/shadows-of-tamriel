import bpy, sys, os
from mathutils import Vector
BASE=r'C:\Users\myste\Downloads\Altair Skyrim Native'
ADDON_PARENT=os.path.join(BASE,'tooling','pynifly-29.1.0')
sys.path.insert(0,ADDON_PARENT)
import addon_utils
addon_utils.enable('io_scene_nifly',default_set=True,persistent=False)
from io_scene_nifly import PyNiflyPreferences
prefs=bpy.context.preferences.addons['io_scene_nifly'].preferences
prefs.sky_texture_path_1=os.path.join(BASE,'textures')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
target=os.path.join(ADDON_PARENT,'io_scene_nifly','skeletons','Skyrim','skeleton.nif')
converted=os.path.join(BASE,'meshes','armor','AltairNative','Altair.nif')
bpy.ops.import_scene.pynifly(filepath=target,rename_bones=False,blender_xf=False,import_animations=False,import_collisions=False,import_tris=False)
arm=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'][-1]
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.import_scene.pynifly(filepath=converted,rename_bones=False,blender_xf=False,import_animations=False,import_collisions=False,import_tris=False,reference_skel=target,apply_skinning=True)
for o in bpy.context.scene.objects:
    if o.type=='MESH' and o.name.startswith('BSBound'): o.hide_render=True
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.name.startswith('BSBound')]
# Report the evaluated and raw bounds by shape to identify any invalid skin bind.
import json
report=[]
for o in [x for x in bpy.context.scene.objects if x.type=='MESH']:
    ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    raw=[o.matrix_world@Vector(c) for c in o.bound_box]
    ecb=[ev.matrix_world@Vector(c) for c in ev.bound_box]
    def bounds(cs): return [[min(p[i] for p in cs) for i in range(3)],[max(p[i] for p in cs) for i in range(3)]]
    report.append({'name':o.name,'raw':bounds(raw),'eval':bounds(ecb),'groups':[g.name for g in o.vertex_groups],'mods':[(m.type,m.object.name if getattr(m,'object',None) else None) for m in o.modifiers]})
open(os.path.join(BASE,'converted_shape_report.json'),'w').write(json.dumps(report,indent=2))
# Render the converted model from a 3/4 view using evaluated meshes.
scene=bpy.context.scene; scene.render.engine='BLENDER_WORKBENCH'; scene.display.shading.light='STUDIO'; scene.display.shading.color_type='SINGLE'; scene.display.shading.single_color=(0.8,0.55,0.3); scene.display.shading.show_cavity=True;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
for o in meshes:
    o.hide_render=False
    for mod in o.modifiers:
        mod.show_render=True
coords=[]
dg=bpy.context.evaluated_depsgraph_get()
for o in meshes:
    ev=o.evaluated_get(dg)
    for c in ev.bound_box: coords.append(ev.matrix_world@Vector(c))
lo=Vector(tuple(min(p[i] for p in coords) for i in range(3)));hi=Vector(tuple(max(p[i] for p in coords) for i in range(3)));center=(lo+hi)/2
bpy.ops.object.camera_add(location=center+Vector((300,150,140)))
cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=max(hi-lo)*1.6;cam.data.clip_end=5000;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
bpy.ops.object.light_add(type='AREA',location=center+Vector((80,140,220)));bpy.context.object.data.energy=9000
bpy.ops.object.light_add(type='AREA',location=center+Vector((-120,-100,100)));bpy.context.object.data.energy=6000
scene.world.color=(0.2,0.2,0.2);scene.render.image_settings.file_format='PNG';scene.render.filepath=os.path.join(BASE,'converted_nif_workbench.png')
print('CONVERTED_RENDER',len(meshes),'meshes',list(center),list(hi-lo))
bpy.ops.render.render(write_still=True)



