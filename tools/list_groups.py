import json
j=json.load(open(r'C:\Users\myste\Downloads\Altair Skyrim Native\inspect_source.json'))
for o in j:
 if o.get('type')=='MESH': print(o['name'],o['groups'][:8])
