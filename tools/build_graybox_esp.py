"""AltairFreerunGraybox.esp (ESL): an interior test cell for AC1 free-running, built from the graybox pieces
(build_graybox_nifs.py). Get there with:  coc AltairFreerunGraybox
Layout (metres, +Y forward from the spawn):
  lane A (x = 0)    flat gaps of 1, 2.5, 4, 5.5 m between 4 x 4 m platforms 3 m up  (AC1's 050/300/550 cm jump items)
  lane B (x = +12)  heights 3 -> 4.5 -> 6 -> 3.5 -> 3 m                             (up / down jumps)
  lane C (x = -12)  platform -> 0.3 m beam -> platform -> beam -> platform              (beams)
  lane D (x = +24)  walls 6 m wide: 2.5 m and 3 m tall (catch, hang, shimmy, pull up), 5 m and 4 m (wall run up)
  lane E (x = -24)  platform -> 3 poles -> platform -> swing bar 5.3 m up -> platform
Each lane has stairs up to its first platform.
Usage: python tools/build_graybox_esp.py <out.esp>
"""
import struct, sys

OUT = sys.argv[1]
U = 70.0


def zstr(s): return s.encode('cp1252') + b'\0'
def sub(tag, data): return tag.encode() + struct.pack('<H', len(data)) + data
def record(tag, fid, body, flags=0):
    return tag.encode() + struct.pack('<IIIIHH', len(body), flags, fid, 0, 44, 0) + body
def group(label, gtype, payload):
    lab = label.encode() if isinstance(label, str) else struct.pack('<i', label)
    return b'GRUP' + struct.pack('<I4sIHHI', 24 + len(payload), lab, gtype, 0, 0, 0) + payload


PIECES = {  # name: (sx, sy, height) metres
    'gb_floor': (60.0, 60.0, 1.0), 'gb_pillar_300': (4.0, 4.0, 3.0), 'gb_pillar_350': (4.0, 4.0, 3.5),
    'gb_pillar_450': (4.0, 4.0, 4.5), 'gb_pillar_600': (4.0, 4.0, 6.0), 'gb_beam': (0.3, 4.0, 0.3),
    'gb_step': (2.0, 0.6, 0.35), 'gb_wall': (6.0, 1.0, 5.0),
    'gb_wall_250': (6.0, 1.0, 2.5), 'gb_wall_300': (6.0, 1.0, 3.0),
    'gb_wall_400': (6.0, 1.0, 4.0), 'gb_pole': (0.4, 0.4, 3.0), 'gb_bar': (4.0, 0.12, 0.12),
    'gb_tower': (4.0, 4.0, 15.0), 'gb_stepcol': (2.0, 0.5, 15.0), 'gb_plank': (4.5, 0.6, 0.2),
}
# ramps: (width, run, rise) - the model's top runs from its origin up along +Y; bounds for OBND
RAMPS = {'gb_ramp_lane': (2.0, 6.0, 3.0), 'gb_ramp_tower': (2.0, 4.0, 1.875)}
PIECES['gb_landing'] = (2.0, 2.0, 0.3)
# masters: Skyrim.esm (00), AltairLeapOfFaith.esp (01, for its haystack); this plugin's own records are 02
STAT_ID = {n: 0x02000800 + i for i, n in enumerate(list(PIECES) + list(RAMPS))}
CELL_ID = 0x02000830
HAYSTACK = 0x01000816   # AltairLeapOfFaith.esp: AltairHaystack (scripted)
COC_MARKER = 0x00000032  # COCMarkerHeading

stats = b''
BOUNDS = {n: (-sx / 2, -sy / 2, -h, sx / 2, sy / 2, 0.0) for n, (sx, sy, h) in PIECES.items()}
BOUNDS.update({n: (-w / 2, -0.2, -0.4, w / 2, run + 0.2, rise) for n, (w, run, rise) in RAMPS.items()})
for n, b in BOUNDS.items():
    obnd = struct.pack('<6h', *(int(v * U) for v in b))
    stats += record('STAT', STAT_ID[n], sub('EDID', zstr('AltairFR_' + n)) + sub('OBND', obnd) +
                    sub('MODL', zstr('AltairFreerun\\' + n + '.nif')) + sub('DNAM', bytes.fromhex('0000b44200000000')))

# placements: (piece, x, y, top z[, rotation z radians]) in metres
P = [('gb_floor', 0.0, 10.0, 0.0)]
for i, y in enumerate([0.0, 5.0, 11.5, 19.5, 29.0]):                       # lane A: gaps 1, 2.5, 4, 5.5
    P.append(('gb_pillar_300', 0.0, y, 3.0))
for piece, y, top in [('gb_pillar_300', 0.0, 3.0), ('gb_pillar_450', 6.0, 4.5), ('gb_pillar_600', 11.5, 6.0),
                      ('gb_pillar_350', 18.5, 3.5), ('gb_pillar_300', 26.0, 3.0)]:   # lane B: up 1.5, up 1.5, down 2.5, down 0.5
    P.append((piece, 12.0, y, top))
for piece, y in [('gb_pillar_300', 0.0), ('gb_beam', 6.0), ('gb_pillar_300', 12.5), ('gb_beam', 18.0),
                 ('gb_pillar_300', 25.0)]:                                  # lane C: beams
    P.append((piece, -12.0, y, 3.0))
def stairs(x):  # a ramp from the floor up to the 3 m platform at y = -2..2 (26.6 degrees, 6 m long)
    P.append(('gb_ramp_lane', x, -8.0, 0.0))
for x in (0.0, 12.0, -12.0):
    stairs(x)
# lane D (x = +24): ledges to catch from the floor (orange: 2.5 m and 3 m) and one out of reach (5 m)
P.append(('gb_wall_250', 24.0, 4.0, 2.5))
P.append(('gb_wall_300', 24.0, 12.0, 3.0))
P.append(('gb_wall', 24.0, 20.0, 5.0))
P.append(('gb_wall_400', 24.0, 28.0, 4.0))   # wall run up
# lane E (x = -24): platform -> three poles -> platform -> swing bar -> platform
P.append(('gb_pillar_300', -24.0, 0.0, 3.0))
for y in (4.5, 7.5, 10.5):
    P.append(('gb_pole', -24.0, y, 3.0))
P.append(('gb_pillar_300', -24.0, 15.0, 3.0))
P.append(('gb_bar', -24.0, 19.5, 5.3))         # 4 m bar across the lane, 5.3 m up (hanging, the feet are near 3 m)
P.append(('gb_pillar_300', -24.0, 25.0, 3.0))
stairs(-24.0)
# leap of faith tower (behind the spawn, right): 15 m, a spiral of 60 solid 25 cm steps round it ending on the
# east side, and a diving plank 4.5 m out to the west with the haystack just past its end (AC1 viewpoint style)
import math
TOWER = (22.0, -12.0)
P.append(('gb_tower', TOWER[0], TOWER[1], 15.0))
# a square spiral of ramps round the tower, anticlockwise from the south-east corner: 8 sides of 4 m rising
# 1.875 m each, flat 2 x 2 m landings at the corners; the last landing (SE, 15 m) and a bridge onto the top
SIDES = [  # (ramp origin relative to the tower, z rotation): rising +y, -x, -y, +x
    ((3.0, -2.0), 0.0), ((2.0, 3.0), -math.pi / 2), ((-3.0, 2.0), math.pi), ((-2.0, -3.0), math.pi / 2)]
CORNER_AFTER = [(3.0, 3.0), (-3.0, 3.0), (-3.0, -3.0), (3.0, -3.0)]
for i in range(8):
    (ox, oy), rz = SIDES[i % 4]
    h = i * 1.875
    P.append(('gb_ramp_tower', TOWER[0] + ox, TOWER[1] + oy, h, rz))
    cx, cy = CORNER_AFTER[i % 4]
    P.append(('gb_landing', TOWER[0] + cx, TOWER[1] + cy, h + 1.875))
P.append(('gb_landing', TOWER[0] + 3.0, TOWER[1] - 1.0, 15.0))   # bridge from the last landing onto the top
P.append(('gb_plank', TOWER[0] - 2.0 - 2.25, TOWER[1], 15.0))
HAY_AT = (TOWER[0] - 2.0 - 4.5 - 1.5, TOWER[1])   # 1.5 m past the plank's end

refs = b''
fid = 0x01000820
fid = 0x02000840
for item in P:
    piece, x, y, z = item[:4]
    rz = item[4] if len(item) > 4 else 0.0
    refs += record('REFR', fid, sub('NAME', struct.pack('<I', STAT_ID[piece])) +
                   sub('DATA', struct.pack('<6f', x * U, y * U, z * U, 0.0, 0.0, rz)))
    fid += 1
# the haystack (AltairLeapOfFaith.esp's scripted one: arms the AC1 dive when you stand 8 m+ above it)
refs += record('REFR', fid, sub('NAME', struct.pack('<I', HAYSTACK)) + sub('XSCL', struct.pack('<f', 1.0)) +
               sub('DATA', struct.pack('<6f', HAY_AT[0] * U, HAY_AT[1] * U, 0.0, 0.0, 0.0, 0.0)))
fid += 1
refs += record('REFR', fid, sub('NAME', struct.pack('<I', COC_MARKER)) +
               sub('DATA', struct.pack('<6f', 0.0, -9.0 * U, 0.0, 0.0, 0.0, 0.0)))
n_refs = len(P) + 2

# interior lighting (XCLL, 92 bytes, nothing inherited from a template)
xcll = bytearray(92)
struct.pack_into('<4B', xcll, 0, 120, 120, 128, 0)      # ambient
struct.pack_into('<4B', xcll, 4, 235, 228, 210, 0)      # directional
struct.pack_into('<4B', xcll, 8, 150, 160, 172, 0)      # fog colour near
struct.pack_into('<ff', xcll, 12, 0.0, 40000.0)          # fog near / far
struct.pack_into('<ii', xcll, 20, 50, 35)                # directional rotation XY / Z (degrees)
struct.pack_into('<fff', xcll, 28, 1.0, 0.0, 1.0)        # directional fade, fog clip, fog power
for i in range(6):                                       # directional ambient colours (+X -X +Y -Y +Z -Z)
    struct.pack_into('<4B', xcll, 40 + 4 * i, 105, 105, 112, 0)
struct.pack_into('<4Bf', xcll, 64, 0, 0, 0, 0, 1.0)      # specular, fresnel power
struct.pack_into('<4B', xcll, 72, 150, 160, 172, 0)      # fog colour far
struct.pack_into('<fffI', xcll, 76, 0.2, 0.0, 0.0, 0)    # fog max, light fade begin / end, inherit flags
cell = record('CELL', CELL_ID, sub('EDID', zstr('AltairFreerunGraybox')) + sub('FULL', zstr('Altair Free-run Graybox')) +
              sub('DATA', struct.pack('<H', 0x0001)) + sub('XCLL', bytes(xcll)) + sub('LTMP', bytes(4)) +
              sub('XCLW', bytes.fromhex('000000cf')))
oid = CELL_ID & 0xFFFFFF
cell_tree = group(oid % 10, 2, group((oid // 10) % 10, 3, cell + group(CELL_ID, 6, group(CELL_ID, 9, refs))))

n_records = len(PIECES) + len(RAMPS) + 1 + n_refs
n_groups = 2 + 4
tes4 = (sub('HEDR', struct.pack('<fII', 1.71, n_records + n_groups, 0x1000)) + sub('CNAM', zstr('AltairFreerun')) +
        sub('SNAM', zstr('Graybox test cell for AC1 free-running. coc AltairFreerunGraybox')) +
        sub('MAST', zstr('Skyrim.esm')) + sub('DATA', struct.pack('<Q', 0)) +
        sub('MAST', zstr('AltairLeapOfFaith.esp')) + sub('DATA', struct.pack('<Q', 0)))
with open(OUT, 'wb') as f:
    f.write(record('TES4', 0, tes4, 0x200))   # light plugin (ESL flag)
    f.write(group('STAT', 0, stats))
    f.write(group('CELL', 0, cell_tree))
print('wrote', OUT, n_refs, 'references')
