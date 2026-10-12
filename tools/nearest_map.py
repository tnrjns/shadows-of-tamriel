import json, math
p=r'C:\Users\myste\Downloads\Altair Skyrim Native\node_report.json'
j=json.load(open(p))
want=('NPC Root [Root]','NPC Pelvis [Pelv]','NPC Spine [Spn0]','NPC Spine1 [Spn1]','NPC Spine2 [Spn2]','NPC Neck [Neck]','NPC Head [Head]','NPC L Thigh [LThg]','NPC L Calf [LClf]','NPC L Foot [Lft ]','NPC R Thigh [RThg]','NPC R Calf [RClf]','NPC R Foot [Rft ]','NPC L UpperArm [LUar]','NPC L Forearm [LLar]','NPC L Hand [LHnd]','NPC R UpperArm [RUar]','NPC R Forearm [RLar]','NPC R Hand [RHnd]','NPC L Clavicle [LClv]','NPC R Clavicle [RClv]')
t={n['name']:n for n in j['target']['nodes'] if n['name'] in want}
out=[]
for s in j['src']['nodes']:
 if not s['name'].startswith('bone_'): continue
 x,y,z=map(float,s['pos']); v=(-z*70,x*70,-y*70+69)
 nearest=min(((math.dist(v,map(float,b['pos'])),name) for name,b in t.items()))
 out.append((s['name'],nearest[1],round(nearest[0],1),tuple(round(c,1) for c in v)))
for row in out: print('{:<14} {:<26} {:>5} {}'.format(*row))
