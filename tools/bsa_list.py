"""List file paths in a Skyrim SE BSA (v105) without extracting. Usage: bsa_list.py <bsa> [substring]"""
import struct, sys
b = open(sys.argv[1], 'rb').read()
magic, ver, off, flags, nfold, nfile, lfold, lfile, ftype = struct.unpack_from('<4sIIIIIIII', b, 0)
assert magic == b'BSA\0' and ver == 105, (magic, ver)
p = off; folders = []
for _ in range(nfold):
    h, cnt, _pad, foff = struct.unpack_from('<QIIQ', b, p); folders.append(cnt); p += 24
names_dirs = []
for cnt in folders:
    ln = b[p]; name = b[p+1:p+ln].decode('cp1252'); p += 1 + ln
    p += 16 * cnt
    names_dirs.append((name, cnt))
fnames = b[p:p+lfile].split(b'\0')
i = 0; sub = sys.argv[2].lower() if len(sys.argv) > 2 else ''
for d, cnt in names_dirs:
    for _ in range(cnt):
        path = d + chr(92) + fnames[i].decode('cp1252'); i += 1
        if sub in path.lower(): print(path)
