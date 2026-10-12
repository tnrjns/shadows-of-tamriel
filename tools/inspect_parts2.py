import sys
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as P
f=P.NifFile(r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif')
for s in f.shapes:
 p=s.partitions[0] if s.partitions else None
 if p: print(s.name, [(k,repr(getattr(p,k,None))) for k in dir(p) if 'part' in k.lower() or 'body' in k.lower() or 'flag' in k.lower()])
