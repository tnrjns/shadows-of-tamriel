import json
j=json.load(open(r'C:\Users\myste\Downloads\Altair Skyrim Native\converted_shape_report.json'))
for o in j: print(o['name'], 'RAW',o['raw'],'EVAL',o['eval'],'groups',len(o['groups']))
