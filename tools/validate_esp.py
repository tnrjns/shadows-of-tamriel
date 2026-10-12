"""Parse AltairNative.esp back and check structure + every FormID/path reference."""
import struct, sys, os, zlib
esp, mod = sys.argv[1], sys.argv[2]
ESM = r'C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm'
b = open(esp, 'rb').read()
errs = []
def subs(body):
    i, out = 0, []
    while i < len(body):
        t = body[i:i+4].decode(); sz = struct.unpack_from('<H', body, i+4)[0]
        out.append((t, body[i+6:i+6+sz])); i += 6 + sz
    if i != len(body): errs.append('subrecord overrun')
    return out
assert b[:4] == b'TES4'
tsz, tflags, tfid, _, tver, _ = struct.unpack_from('<IIIIHH', b, 4)
tes4 = subs(b[24:24+tsz])
hedr = dict(tes4)['HEDR']; ver, nrec, nextid = struct.unpack('<fII', hedr)
masters = [v.rstrip(b'\0').decode() for t, v in tes4 if t == 'MAST']
print('TES4 flags', hex(tflags), 'formver', tver, 'HEDR ver %.2f' % ver, 'numRecords', nrec, 'nextID', hex(nextid), 'masters', masters)
recs, ngroups, p = {}, 0, 24 + tsz
while p < len(b):
    assert b[p:p+4] == b'GRUP', 'expected group'
    gsz, label, gtype = struct.unpack_from('<I4sI', b, p+4); ngroups += 1
    q, end = p + 24, p + gsz
    while q < end:
        rt = b[q:q+4].decode(); dsz, fl, fid, _, rver, _ = struct.unpack_from('<IIIIHH', b, q+4)
        if rt != label.decode(): errs.append(f'{rt} inside {label} group')
        recs[fid] = (rt, subs(b[q+24:q+24+dsz]), rver)
        q += 24 + dsz
    if q != end: errs.append('group size mismatch')
    p = end
if nrec != len(recs) + ngroups: errs.append(f'HEDR numRecords {nrec} != {len(recs)+ngroups}')
# Skyrim.esm record types by formid (for reference checks)
d = open(ESM, 'rb').read(); esm_types = {}
def walk(p, end):
    while p < end:
        if d[p:p+4] == b'GRUP':
            gs = struct.unpack_from('<I', d, p+4)[0]; walk(p+24, p+gs); p += gs; continue
        dsz, fl, fid = struct.unpack_from('<III', d, p+4); esm_types[fid] = d[p:p+4].decode(); p += 24 + dsz
walk(struct.unpack_from('<I', d, 4)[0] + 24, len(d))
def check_ref(fid, want, where):
    if fid >> 24 == 0:
        t = esm_types.get(fid)
        if t != want: errs.append(f'{where}: {fid:08X} is {t}, expected {want}')
    elif fid >> 24 == len(masters):
        if fid not in recs or recs[fid][0] != want: errs.append(f'{where}: local {fid:08X} missing/not {want}')
    else: errs.append(f'{where}: bad master index {fid:08X}')
for fid, (rt, ss, rver) in recs.items():
    sd = {}
    for t, v in ss: sd.setdefault(t, []).append(v)
    edid = sd['EDID'][0].rstrip(b'\0').decode()
    print(f'{rt} {fid:08X} {edid} formver {rver}')
    for t, v in ss:
        if t in ('MOD2', 'MOD3', 'MOD4', 'MOD5'):
            path = v.rstrip(b'\0').decode('cp1252')
            local = os.path.join(mod, 'meshes', path.replace(chr(92), os.sep))
            where = 'mod' if os.path.isfile(local) else 'vanilla BSA (not checked)'
            print(f'   {t} {path}  [{where}]')
            if rt == 'ARMA' and not os.path.isfile(local): errs.append(f'{t} missing {path}')
        elif t == 'BOD2':
            bf, at = struct.unpack('<II', v)
            print('   BOD2 slots', [30 + i for i in range(32) if bf >> i & 1], 'armorType', at)
        elif t == 'FULL':
            print('   FULL', v.rstrip(b'\0').decode('cp1252'))
        elif t == 'DATA' and rt == 'ARMO':
            print('   DATA value/weight', struct.unpack('<if', v))
    if rt == 'ARMA':
        check_ref(struct.unpack('<I', sd['RNAM'][0])[0], 'RACE', 'ARMA RNAM')
        for v in sd.get('MODL', []): check_ref(struct.unpack('<I', v)[0], 'RACE', 'ARMA MODL')
        print('   additional races', len(sd.get('MODL', [])))
    if rt == 'ARMO':
        check_ref(struct.unpack('<I', sd['RNAM'][0])[0], 'RACE', 'ARMO RNAM')
        for v in sd['MODL']: check_ref(struct.unpack('<I', v)[0], 'ARMA', 'ARMO MODL')
        n = struct.unpack('<I', sd['KSIZ'][0])[0]; kws = struct.unpack(f'<{n}I', sd['KWDA'][0])
        for k in kws: check_ref(k, 'KYWD', 'ARMO KWDA')
        for t in ('YNAM', 'ZNAM'): check_ref(struct.unpack('<I', sd[t][0])[0], 'SNDR', 'ARMO ' + t)
        if struct.unpack('<I', sd['BOD2'][0][:4]) != struct.unpack('<I', recs[struct.unpack('<I', sd['MODL'][0])[0]][1][1][1][:4]):
            errs.append('ARMO/ARMA biped slots differ')
print('ESP_VALIDATION', 'FAIL' if errs else 'OK', errs)
