import sys, json
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as nifly
src=r'C:\Users\myste\AppData\Local\ModOrganizer\Skyrim Special Edition\mods\Altair AC1 Movement\meshes\actors\character\Altair\Altair.nif'
tgt=r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\skeletons\Skyrim\skeleton.nif'
out={}
for k,path in [('src',src),('target',tgt)]:
    n=nifly.NifFile(path)
    out[k]={'game':str(n.game),'rootName':n.rootName,'nodes':[]}
    for name,node in n.nodes.items():
        tr=node.global_transform
        # inspect common transform interface
        trans=getattr(tr,'translation',None)
        if trans is None: trans=getattr(tr,'location',None)
        try: pos=list(trans)
        except: pos=str(trans)
        out[k]['nodes'].append({'name':name,'parent':node.parent.name if node.parent else None,'pos':pos})
open(r'C:\Users\myste\Downloads\Altair Skyrim Native\node_report.json','w').write(json.dumps(out,indent=2,default=str))

