"""Re-encode the Altair diffuse DDS files for Skyrim SE and write a flat normal map.

Source files are uncompressed DX10 R8G8B8A8_UNORM_SRGB, some without mipmaps. Skyrim SE
shades diffuse textures in gamma space, so the same texels are written as R8G8B8A8_UNORM
(DXGI 28) with a full box-filtered mip chain.

Run with Blender's Python (needs numpy):
  blender -b --factory-startup --python tools/convert_textures.py -- <src_dir> <out_dir>
"""
import sys, os, struct, glob
import numpy as np

src_dir, out_dir = sys.argv[sys.argv.index('--') + 1:][:2]
os.makedirs(out_dir, exist_ok=True)

DDSD = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x8   # caps|height|width|pixelformat|mipmapcount|pitch

def read_rgba(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'DDS ', path
    h, w = struct.unpack('<II', b[12:20])
    mips = max(1, struct.unpack('<I', b[28:32])[0])
    fourcc = b[84:88]
    if fourcc != b'DX10':
        raise ValueError(f'{path}: expected DX10 header')
    fmt = struct.unpack('<I', b[128:132])[0]
    if fmt not in (28, 29):
        raise ValueError(f'{path}: unsupported DXGI format {fmt}')
    top = np.frombuffer(b, dtype=np.uint8, count=w * h * 4, offset=148).reshape(h, w, 4)
    return top.copy()

def mip_chain(img):
    out = [img]
    cur = img.astype(np.float32)
    while cur.shape[0] > 1 or cur.shape[1] > 1:
        h, w = cur.shape[:2]
        nh, nw = max(1, h // 2), max(1, w // 2)
        c = cur[:nh * (h // nh), :nw * (w // nw)]
        c = c.reshape(nh, h // nh, nw, w // nw, 4).mean(axis=(1, 3))
        cur = c
        out.append(np.clip(np.rint(c), 0, 255).astype(np.uint8))
    return out

def write_dds(path, levels):
    h, w = levels[0].shape[:2]
    hdr = bytearray(148)
    hdr[0:4] = b'DDS '
    struct.pack_into('<IIIIIII', hdr, 4, 124, DDSD, h, w, w * 4, 0, len(levels))
    struct.pack_into('<II4s', hdr, 76, 32, 0x4, b'DX10')                  # pixel format: FOURCC
    struct.pack_into('<I', hdr, 108, 0x1000 | 0x400000 | 0x8)              # TEXTURE|MIPMAP|COMPLEX
    struct.pack_into('<IIIII', hdr, 128, 28, 3, 0, 1, 0)                   # UNORM, 2D, 1 elem
    with open(path, 'wb') as f:
        f.write(hdr)
        for lv in levels:
            f.write(np.ascontiguousarray(lv).tobytes())

done = []
for p in sorted(glob.glob(os.path.join(src_dir, '*.dds'))):
    img = read_rgba(p)
    lv = mip_chain(img)
    write_dds(os.path.join(out_dir, os.path.basename(p)), lv)
    done.append((os.path.basename(p), img.shape[1], img.shape[0], len(lv)))

# Flat tangent-space normal; alpha is the specular mask (kept low for cloth/leather).
flat = np.zeros((16, 16, 4), np.uint8)
flat[..., 0] = 128; flat[..., 1] = 128; flat[..., 2] = 255; flat[..., 3] = 40
write_dds(os.path.join(out_dir, 'altair_flat_n.dds'), mip_chain(flat))
done.append(('altair_flat_n.dds', 16, 16, 5))
for d in done:
    print('TEX', *d)
