"""Dump raw subrecords of given FormIDs from Skyrim.esm (read-only reference)."""
import struct, zlib, sys
ESM = r'C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm'
want = {int(x, 16) for x in sys.argv[1].split(',')}
data = open(ESM, 'rb').read()
p = 0
hdr = data[:24]; print('TES4 hdr', hdr.hex(), 'ver', struct.unpack_from('<H', data, 20))
tes4 = data[24:24+struct.unpack_from('<I', data, 4)[0]]
i=0
while i < len(tes4):
    t=tes4[i:i+4]; sz=struct.unpack_from('<H',tes4,i+4)[0]; print('  TES4', t, tes4[i+6:i+6+sz][:40].hex()); i+=6+sz
p = 24 + len(tes4)
def walk(p, end):
    while p < end:
        t = data[p:p+4]
        if t == b'GRUP':
            gs = struct.unpack_from('<I', data, p+4)[0]; walk(p+24, p+gs); p += gs; continue
        dsz, flags, fid = struct.unpack_from('<III', data, p+4)
        if fid in want:
            body = data[p+24:p+24+dsz]
            if flags & 0x40000: body = zlib.decompress(body[4:])
            print(t, '%08X' % fid, 'flags', hex(flags), 'hdr', data[p:p+24].hex())
            i = 0
            while i < len(body):
                st = body[i:i+4]; sz = struct.unpack_from('<H', body, i+4)[0]
                v = body[i+6:i+6+sz]; print('   ', st, sz, v.hex() if len(v) <= 48 else v[:48].hex()+'...', repr(v[:60]) if st in (b'EDID', b'MOD2', b'MOD3', b'MOD4', b'MOD5', b'MODL') and sz != 4 else '')
                i += 6 + sz
        p += 24 + dsz
walk(p, len(data))
