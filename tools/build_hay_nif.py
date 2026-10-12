"""An AC1-sized haystack for the leap of faith: Skyrim's HayMound01 stretched to about 2.3 x 2.0 x 1.3 m and with
no collision, so Altair sinks into it (the plugin then hides him inside, AC1-style).
Usage: python tools/build_hay_nif.py <vanilla haymound01.nif> <out nif>
"""
import sys, math
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly')
from pyn.pynifly import NifFile

NifFile.Load(r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\NiflyDLL.dll')
SRC, OUT = sys.argv[1], sys.argv[2]
SX, SY, SZ = 2.4, 2.4, 4.0   # 146 x 126 x 38 units -> ~350 x 300 x 152 units: 5.0 x 4.3 x 2.2 m

src = NifFile(SRC)
out = NifFile()
out.initialize('SKYRIMSE', OUT, 'BSFadeNode', 'AltairHaystackAC1')
for sh in src.shapes:
    t = sh.transform
    verts = [((v[0] * t.scale + t.translation[0]) * SX, (v[1] * t.scale + t.translation[1]) * SY,
              (v[2] * t.scale + t.translation[2]) * SZ) for v in sh.verts]
    norms = []
    for n in sh.normals:
        x, y, z = n[0] / SX, n[1] / SY, n[2] / SZ   # normals under a non-uniform scale: inverse-transpose
        l = math.sqrt(x * x + y * y + z * z) or 1.0
        norms.append((x / l, y / l, z / l))
    new = out.createShapeFromData(sh.name, verts, sh.tris, sh.uvs, norms, parent=out.rootNode)
    for slot, path in sh.textures.items():
        if path:
            new.set_texture(slot, path)
    for f in ('Shader_Flags_1', 'Shader_Flags_2', 'Glossiness', 'Spec_Str', 'Alpha'):
        try:
            setattr(new.shader.properties, f, getattr(sh.shader.properties, f))
        except AttributeError:
            pass
    new.save_shader_attributes()
    if sh.colors:
        new.set_colors(sh.colors)
    if sh.has_alpha_property:
        new.has_alpha_property = True
        new.alpha_property.properties.flags = sh.alpha_property.properties.flags
        new.alpha_property.properties.threshold = sh.alpha_property.properties.threshold
        new.save_alpha_property()
out.save()
xs = [v for s in out.shapes for v in s.verts]
print('wrote', OUT, 'bounds', [round(min(p[i] for p in xs)) for i in range(3)], [round(max(p[i] for p in xs)) for i in range(3)])
