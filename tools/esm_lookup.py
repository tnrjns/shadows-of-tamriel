"""Look up FormIDs by EditorID in Skyrim.esm top-level groups (read-only)."""
import struct, zlib, sys, json
ESM = r'C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm'
want_types = set(sys.argv[1].split(','))
data = open(ESM, 'rb').read()
def subrecords(buf):
    i = 0
    while i + 6 <= len(buf):
        t = buf[i:i+4]; sz = struct.unpack_from('<H', buf, i+4)[0]
        yield t, buf[i+6:i+6+sz]; i += 6 + sz
out = {}
pos = struct.unpack_from('<I', data, 4)[0] + 24  # skip TES4
while pos < len(data):
    tag, gsize, label = data[pos:pos+4], *struct.unpack_from('<I4s', data, pos+4)
    if tag != b'GRUP': break
    if label.decode() in want_types:
        p, end = pos + 24, pos + gsize
        while p < end:
            rtype = data[p:p+4]; dsz, flags, fid = struct.unpack_from('<III', data, p+4)
            body = data[p+24:p+24+dsz]
            if rtype == b'GRUP': p += 24; continue
            if flags & 0x40000: body = zlib.decompress(body[4:])
            rec = {'fid': '%08X' % fid}
            for t, v in subrecords(body):
                if t == b'EDID': rec['edid'] = v.rstrip(b'\0').decode('cp1252')
                if t == b'MOD2' and 'mod2' not in rec: rec['mod2'] = v.rstrip(b'\0').decode('cp1252')
                if t == b'FULL' and 'full' not in rec: rec['full'] = v.hex() if len(v) == 4 else v.rstrip(b'\0').decode('cp1252')
            out.setdefault(label.decode(), []).append(rec)
            p += 24 + dsz
    pos += gsize
json.dump(out, sys.stdout, indent=0)
