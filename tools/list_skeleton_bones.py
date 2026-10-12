import json
j=json.load(open(r'C:\Users\myste\Downloads\Altair Skyrim Native\node_report.json'))
for n in j['target']['nodes']:
 if n['name'].startswith('NPC '): print(n['name'],n['parent'])
