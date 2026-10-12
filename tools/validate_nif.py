import sys, json, os
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as P
p=r'C:\Users\myste\Downloads\Altair Skyrim Native\meshes\armor\AltairNative\Altair.nif'
f=P.NifFile(p)
print('GAME',f.game,'ROOT',f.rootName,'FILE',os.path.getsize(p),'SHAPES',len(f.shapes))
for s in f.shapes:
 print(s.name,'verts',len(s.verts),'bones',len(s.unique_bone_names),'partition',len(s.partitions or []),'tex',s.textures,'names',sorted(s.unique_bone_names)[:8])
