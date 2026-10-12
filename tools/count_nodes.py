import sys
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as P
f=P.NifFile(r'C:\Users\myste\Downloads\Altair Skyrim Native\meshes\armor\AltairNative\Altair.nif')
print('nodes',len(f.nodes),'root',f.rootName)
for n in list(f.nodes)[:40]: print(n)
