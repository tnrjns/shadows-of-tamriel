"""Graybox pieces for the AltairFreerun test cell: textured boxes with static box collision, and their grid textures.
Every box has its top face at z = 0 (so a reference's z is the height of its top) and is centred on x / y.
UVs are in metres, so the grid texture shows a 1 m grid on every face.
Usage: python tools/build_graybox_nifs.py <mod dir>
"""
import sys, os, struct, math
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly')
from pyn.pynifly import NifFile, BSXFlags
from pyn.nifdefs import bhkBoxShapeProps, bhkRigidBodyProps, PynBufferTypes

NifFile.Load(r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\NiflyDLL.dll')
MOD = sys.argv[1]
U = 70.0          # game units per metre
HAVOK = 69.99125  # game units per Havok unit (Skyrim)

# (file, size x, size y, height, texture)
PIECES = [
    ('gb_floor', 60.0, 60.0, 1.0, 'grid'),
    ('gb_pillar_300', 4.0, 4.0, 3.0, 'grid'),
    ('gb_pillar_350', 4.0, 4.0, 3.5, 'grid'),
    ('gb_pillar_450', 4.0, 4.0, 4.5, 'grid'),
    ('gb_pillar_600', 4.0, 4.0, 6.0, 'grid'),
    ('gb_beam', 0.3, 4.0, 0.3, 'orange'),
    ('gb_step', 2.0, 0.6, 0.35, 'grid'),
    ('gb_wall', 6.0, 1.0, 5.0, 'grid'),
    ('gb_wall_250', 6.0, 1.0, 2.5, 'orange'),
    ('gb_wall_300', 6.0, 1.0, 3.0, 'orange'),
    ('gb_wall_400', 6.0, 1.0, 4.0, 'grid'),
    ('gb_pole', 0.4, 0.4, 3.0, 'orange'),
    ('gb_bar', 4.0, 0.12, 0.12, 'orange'),
    ('gb_tower', 4.0, 4.0, 15.0, 'grid'),
    ('gb_stepcol', 2.0, 0.5, 15.0, 'grid'),   # a solid stair step: top at the step height, down below the floor
    ('gb_plank', 4.5, 0.6, 0.2, 'orange'),    # the leap of faith diving plank
]


# ------------------------------------------------------------------------------------ textures (uncompressed DDS)
def dds(path, w, h, pixel):
    """BGRA8 DDS with a full mip chain; pixel(x, y, w, h) -> (r, g, b, a) at mip size w x h."""
    levels = []
    lw, lh = w, h
    while True:
        levels.append(b''.join(struct.pack('<4B', *(lambda c: (c[2], c[1], c[0], c[3]))(pixel(x, y, lw, lh)))
                               for y in range(lh) for x in range(lw)))
        if lw == 1 and lh == 1:
            break
        lw, lh = max(1, lw // 2), max(1, lh // 2)
    hdr = struct.pack('<4sI', b'DDS ', 124)
    hdr += struct.pack('<6I', 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x8, h, w, w * 4, 0, len(levels))
    hdr += bytes(44)
    hdr += struct.pack('<2I4s5I', 32, 0x41, b'\0\0\0\0', 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    hdr += struct.pack('<4I', 0x1000 | 0x8 | 0x400000, 0, 0, 0) + bytes(4)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(hdr + b''.join(levels))


def grid(base, line):
    def px(x, y, w, h):
        # one texture = 1 m: a strong line on the metre, a faint one on the half metre
        def near(v, n, at, width):
            return abs((v + 0.5) / n - at) * n < width
        t = max(1.0, w / 64.0)
        if near(x, w, 0.0, t) or near(x, w, 1.0, t) or near(y, h, 0.0, t) or near(y, h, 1.0, t):
            c = line
        elif near(x, w, 0.5, t * 0.5) or near(y, h, 0.5, t * 0.5):
            c = tuple((a + b) // 2 for a, b in zip(base, line))
        else:
            c = base
        return (*c, 255)
    return px


TEX = os.path.join(MOD, 'textures', 'AltairFreerun')
dds(os.path.join(TEX, 'grid_d.dds'), 128, 128, grid((150, 150, 150), (70, 70, 70)))
dds(os.path.join(TEX, 'orange_d.dds'), 128, 128, grid((225, 135, 40), (110, 60, 15)))
dds(os.path.join(TEX, 'flat_n.dds'), 4, 4, lambda x, y, w, h: (128, 128, 255, 255))


# ------------------------------------------------------------------------------------ meshes
def box_mesh(sx, sy, sz):
    """24 vertices (4 per face), metres -> game units; UVs in metres."""
    hx, hy = sx / 2, sy / 2
    faces = [  # (normal, 4 corners in metres, uv axes)
        ((0, 0, 1), [(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], (0, 1)),
        ((0, 0, -1), [(-hx, hy, -sz), (hx, hy, -sz), (hx, -hy, -sz), (-hx, -hy, -sz)], (0, 1)),
        ((0, -1, 0), [(-hx, -hy, -sz), (hx, -hy, -sz), (hx, -hy, 0), (-hx, -hy, 0)], (0, 2)),
        ((0, 1, 0), [(hx, hy, -sz), (-hx, hy, -sz), (-hx, hy, 0), (hx, hy, 0)], (0, 2)),
        ((-1, 0, 0), [(-hx, hy, -sz), (-hx, -hy, -sz), (-hx, -hy, 0), (-hx, hy, 0)], (1, 2)),
        ((1, 0, 0), [(hx, -hy, -sz), (hx, hy, -sz), (hx, hy, 0), (hx, -hy, 0)], (1, 2)),
    ]
    verts, norms, uvs, tris = [], [], [], []
    for n, corners, (a, b) in faces:
        base = len(verts)
        for c in corners:
            verts.append(tuple(v * U for v in c))
            norms.append(n)
            uvs.append((c[a], -c[b]))
        tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return verts, norms, uvs, tris


def ramp_mesh(w, run, rise, t):
    """A slab of width w and thickness t whose top runs from (0, 0, 0) up to (0, run, rise): the box tilted
    about X. Returns mesh data plus the box centre (game units) and tilt angle for the collision."""
    a = math.atan2(rise, run)
    L = math.hypot(run, rise)
    n = (0.0, -math.sin(a), math.cos(a))
    c = (0.0, run / 2 - n[1] * t / 2, rise / 2 - n[2] * t / 2)
    def X(p):  # local (centred, metres) -> model (game units)
        x, y, z = p
        return ((c[0] + x) * U, (c[1] + y * math.cos(a) - z * math.sin(a)) * U, (c[2] + y * math.sin(a) + z * math.cos(a)) * U)
    def N(v):
        x, y, z = v
        return (x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))
    hx, hy, hz = w / 2, L / 2, t / 2
    faces = [((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)], (0, 1)),
             ((0, 0, -1), [(-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz)], (0, 1)),
             ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)], (0, 2)),
             ((0, 1, 0), [(hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz)], (0, 2)),
             ((-1, 0, 0), [(-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz)], (1, 2)),
             ((1, 0, 0), [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)], (1, 2))]
    verts, norms, uvs, tris = [], [], [], []
    for nrm, corners, (i, j) in faces:
        b = len(verts)
        for q in corners:
            verts.append(X(q)); norms.append(N(nrm)); uvs.append((q[i], -q[j]))
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return verts, norms, uvs, tris, tuple(v * U for v in c), a, (hx * U, hy * U, hz * U)


def build(name, sx, sy, sz, tex, ramp=None):
    """A box (top at z = 0), or with ramp = (run, rise) a slab of width sx and thickness sz sloping up along +Y."""
    path = os.path.join(MOD, 'meshes', 'AltairFreerun', name + '.nif')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nif = NifFile()
    nif.initialize('SKYRIMSE', path, 'BSFadeNode', name)
    if ramp:
        verts, norms, uvs, tris, centre, tilt, half = ramp_mesh(sx, ramp[0], ramp[1], sz)
    else:
        verts, norms, uvs, tris = box_mesh(sx, sy, sz)
        centre, tilt, half = (0.0, 0.0, -sz * U / 2), 0.0, (sx * U / 2, sy * U / 2, sz * U / 2)
    shape = nif.createShapeFromData(name + ':0', verts, tris, uvs, norms, parent=nif.rootNode)
    shape.set_texture('Diffuse', f'textures\\AltairFreerun\\{tex}_d.dds')
    shape.set_texture('Normal', 'textures\\AltairFreerun\\flat_n.dds')
    shape.save_shader_attributes()

    # static box collision: a bhkBoxShape on a fixed rigid body offset down to the box centre
    bp = bhkBoxShapeProps()
    bp.bhkMaterial = 3741512247          # SKY_HAV_MAT_STONE
    bp.bhkRadius = 0.01
    for i, v in enumerate(half):
        bp.bhkDimensions[i] = v / HAVOK
    cshape = nif.add_shape(bp)
    rb = bhkRigidBodyProps()
    rb.bufType = PynBufferTypes.bhkRigidBodyTBufType
    rb.shapeID = cshape.id
    rb.collisionFilter_layer = 1         # L_STATIC
    rb.collisionFilterCopy_layer = 1
    rb.broadPhaseType = 1
    rb.collisionResponse = 1
    rb.collisionResponse2 = 1
    rb.processContactCallbackDelay = 0xFFFF
    rb.processContactCallbackDelay2 = 0xFFFF
    for i in range(3):
        rb.translation[i] = centre[i] / HAVOK
    rb.rotation[0] = math.sin(tilt / 2)   # about X: the slope (+Y tilts up toward +Z)
    rb.rotation[3] = math.cos(tilt / 2)
    rb.timeFactor = 1.0
    rb.gravityFactor = 1.0
    rb.friction = 0.5
    rb.rollingFrictionMult = 1.0
    rb.restitution = 0.4
    rb.maxLinearVelocity = 104.4
    rb.maxAngularVelocity = 31.57
    rb.penetrationDepth = 0.15
    rb.motionSystem = 7                  # MO_SYS_FIXED
    rb.deactivatorType = 1
    rb.solverDeactivation = 1
    rb.qualityType = 1                   # MO_QUAL_FIXED
    coll = nif.rootNode.add_collision(None, flags=1)
    coll.add_body(rb)
    BSXFlags.New(nif, 'BSX', 0x2, parent=nif.rootNode)   # Havok: the model has collision
    nif.save()
    return path


for p in PIECES:
    print('wrote', build(*p))
# ramps (walk up smoothly; Skyrim's step-up pops the camera on every stair)
RAMPS = [('gb_ramp_lane', 2.0, 0.0, 0.3, 'grid', (6.0, 3.0)),       # floor -> 3 m platform over 6 m
         ('gb_ramp_tower', 2.0, 0.0, 0.3, 'grid', (4.0, 1.875)),    # one side of the tower's square spiral
         ('gb_landing', 2.0, 2.0, 0.3, 'grid', None)]
for p in RAMPS:
    print('wrote', build(*p))
