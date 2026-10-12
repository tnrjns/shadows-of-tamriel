import sys
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as P
f=P.NifFile(r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif')
for s in f.shapes:
 print(s.name,'skin',s.has_skin_instance,'partition_count',len(s.partitions or []),'parts',s.partitions,'bones',len(s.unique_bone_names),'textures',s.textures)
