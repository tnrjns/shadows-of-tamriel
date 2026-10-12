import sys
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as P
f=P.NifFile(r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif')
print('shapes?', type(f.shapes),len(f.shapes))
s=f.shapes[0]
print('shape',type(s),s.name)
print('shape attrs', [x for x in dir(s) if not x.startswith('_')][:80])
print('shader',getattr(s,'shader',None),type(getattr(s,'shader',None)))
for x in dir(s):
 if 'shader' in x.lower() or 'texture' in x.lower():
  try: print(x,repr(getattr(s,x)))
  except Exception as e: print(x,e)
