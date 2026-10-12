"""Write AltairLeapOfFaith.esp: AC1 leaps of faith into haystacks (one in Solitude, one placeable anywhere).

Records: MGEF + SPEL (hidden ability that arms the AC1 dive animations via OAR HasSpell), the AC1 leap and
hay-landing sounds (SNDR + SOUN), the Place Haystack lesser power (MGEF + SPEL), a scripted haystack ACTI
(arms the dive when the player stands high above it), and two persistent haystack REFRs in SolitudeWorld's
persistent cell (the Solitude one and the portable one the power moves). The WRLD and
persistent CELL records are copied verbatim from Skyrim.esm so only references are added.
Usage: python tools/build_lof_esp.py <out.esp>
"""
import struct, sys

OUT = sys.argv[1]
ESM = r'C:\Program Files (x86)\Steam\steamapps\common\Skyrim Special Edition\Data\Skyrim.esm'
SOLITUDE_WORLD, PERSIST_CELL = 0x00037EDF, 0x00037EE6
HAY_MOUND = 0x00031038                      # HayMoundL01
MGEF_ID, SPEL_ID = 0x01000800, 0x01000801            # the dive ability (OAR condition HasSpell 801)
SNDR_LEAP, SNDR_LAND, SOUN_LEAP, SOUN_LAND = 0x01000810, 0x01000811, 0x01000812, 0x01000813
MGEF_PLACE, SPEL_PLACE, ACTI_HAY = 0x01000814, 0x01000815, 0x01000816
REF_HAY, REF_PORTABLE, REF_HAY2 = 0x01000818, 0x0100081A, 0x0100081C
# settings (written by the SKSE Menu Framework page, applied by the settings quest): globals, OAR toggle abilities
GLOBALS = [  # (id, editor id, default)  - lengths in game units
    (0x01000820, 'AltairLeapEnabled', 1.0), (0x01000821, 'AltairLeapGuidance', 0.6),
    (0x01000822, 'AltairLeapArmHeight', 560.0), (0x01000823, 'AltairLeapArmRadius', 1050.0),
    (0x01000824, 'AltairLeapSafeRadius', 520.0), (0x01000825, 'AltairLeapReadyMessage', 1.0),
    (0x01000826, 'AltairLeapVolume', 1.0), (0x01000827, 'AltairDebug', 0.0)]
G = {e: f for f, e, _ in GLOBALS}
OFF_SPELLS = [(0x01000830, 'AltairOffLocomotion'), (0x01000831, 'AltairOffParkour'), (0x01000832, 'AltairOffLeapDive')]
QUST_SETTINGS = 0x01000840
SNDR_SYNC, SOUN_SYNC = 0x01000850, 0x01000851    # viewpoint synchronization (AltairFreerun.dll plays it)

# Solitude haystack in the gate courtyard (navmesh z=-8412); the portable one waits disabled beside it
HAY_POS, PORTABLE_POS, HAY_SCALE = (-60760.0, 105500.0, -8395.0), (-60760.0, 105500.0, -8600.0), 1.0
# second haystack: street below the east city-wall walkway (walk z=-7134, siege defenders stand there), 13 m drop
HAY2_POS = (-58673.0, 107930.0, -8070.0)


def zstr(s): return s.encode('cp1252') + b'\0'
def wstr(s): return struct.pack('<H', len(s)) + s.encode('cp1252')
def sub(tag, data):
    assert len(data) < 0x10000
    return tag.encode() + struct.pack('<H', len(data)) + data
def record(tag, fid, body, flags=0):
    return tag.encode() + struct.pack('<IIIIHH', len(body), flags, fid, 0, 44, 0) + body
def group(label, gtype, payload):
    lab = label.encode() if isinstance(label, str) else struct.pack('<I', label)
    return b'GRUP' + struct.pack('<I4sIHHI', 24 + len(payload), lab, gtype, 0, 0, 0) + payload


def raw_record(fid_wanted, type_wanted):
    d = open(ESM, 'rb').read()
    p = struct.unpack_from('<I', d, 4)[0] + 24
    stack = [len(d)]
    while p < len(d):
        if d[p:p+4] == b'GRUP':
            p += 24; continue
        dsz, fl, fid = struct.unpack_from('<III', d, p + 4)
        if fid == fid_wanted and d[p:p+4] == type_wanted:
            return d[p:p + 24 + dsz]
        p += 24 + dsz
    raise KeyError(hex(fid_wanted))


def vmad(script, props):
    body = struct.pack('<hhH', 5, 2, 1) + wstr(script) + struct.pack('<BH', 0, len(props))
    for name, fid in props:
        body += wstr(name) + struct.pack('<BB', 1, 1) + struct.pack('<HhI', 0, -1, fid)
    return sub('VMAD', body)


def obnd(half):
    hx, hy, hz = (int(round(v)) for v in half)
    return sub('OBND', struct.pack('<6h', -hx, -hy, -hz, hx, hy, hz))


def xprm(half):
    return sub('XPRM', struct.pack('<3f3ffI', *half, 0.39, 0.78, 0.39, 0.15, 1))


# --- MGEF: hidden script-archetype effect (no script needed; it only marks the state)
data = bytearray(152)
struct.pack_into('<I', data, 0, 0x8000 | 0x0200 | 0x0400 | 0x0800)   # hide in UI, no dur/mag/area
struct.pack_into('<ii', data, 12, -1, -1)                            # magic skill, resist value
struct.pack_into('<I', data, 64, 1)                                  # archetype: Script
struct.pack_into('<i', data, 68, -1)                                 # actor value: none
struct.pack_into('<II', data, 80, 0, 0)                              # constant effect, self
struct.pack_into('<i', data, 88, -1)                                 # second actor value: none
struct.pack_into('<f', data, 112, 1.0)                               # dual cast scale
mgef = record('MGEF', MGEF_ID, sub('EDID', zstr('AltairLeapDiveEffect')) + sub('FULL', zstr('Leap of Faith')) +
              sub('DATA', bytes(data)) + sub('DNAM', zstr('')))
# --- SPEL: constant ability carrying it
spel = record('SPEL', SPEL_ID, sub('EDID', zstr('AltairLeapDive')) + sub('OBND', bytes(12)) +
              sub('FULL', zstr('Leap of Faith')) + sub('DESC', zstr('')) +
              sub('SPIT', struct.pack('<IIIfIIffI', 0, 0, 4, 0.0, 0, 0, 0.0, 0.0, 0)) +
              sub('EFID', struct.pack('<I', MGEF_ID)) + sub('EFIT', struct.pack('<fII', 0.0, 0, 0)))
# --- sounds: the AC1 leap cue (eagle cry + fall whoosh, stereo, not positional) and the hay landing (positional)
def sndr(fid, edid, path, output_model):
    return record('SNDR', fid, sub('EDID', zstr(edid)) + sub('CNAM', struct.pack('<I', 0x1EEF540A)) +
                  sub('GNAM', struct.pack('<I', 0x000172A1)) + sub('ANAM', zstr(path)) +   # AudioCategorySFX
                  sub('ONAM', struct.pack('<I', output_model)) + sub('LNAM', bytes(4)) +
                  sub('BNAM', bytes([0, 0, 128, 0, 0, 0])))
def soun(fid, edid, sndr_id):
    return record('SOUN', fid, sub('EDID', zstr(edid)) + sub('OBND', bytes(12)) + sub('SDSC', struct.pack('<I', sndr_id)))
sndr_leap = sndr(SNDR_LEAP, 'AltairLeapOfFaithSD', r'Data\Sound\FX\AltairAC1\LeapOfFaith.wav', 0x0007EDCA)    # SOMStereo
sndr_land = sndr(SNDR_LAND, 'AltairHaystackLandSD', r'Data\Sound\FX\AltairAC1\HaystackLand.wav', 0x0007F80C)  # SOMMono02000
soun_leap = soun(SOUN_LEAP, 'AltairLeapOfFaithSound', SNDR_LEAP)
soun_land = soun(SOUN_LAND, 'AltairHaystackLandSound', SNDR_LAND)
sndr_sync = sndr(SNDR_SYNC, 'AltairSynchronizeSD', r'Data\Sound\FX\AltairAC1\Synchronize.wav', 0x0007EDCA)    # SOMStereo
soun_sync = soun(SOUN_SYNC, 'AltairSynchronizeSound', SNDR_SYNC)
# --- Place Haystack lesser power: fire-and-forget self script effect
data = bytearray(152)
struct.pack_into('<I', data, 0, 0x0200 | 0x0400 | 0x0800)            # no duration / magnitude / area
struct.pack_into('<ii', data, 12, -1, -1)
struct.pack_into('<I', data, 64, 1)                                  # archetype: Script
struct.pack_into('<i', data, 68, -1)
struct.pack_into('<II', data, 80, 1, 0)                              # fire and forget, self
struct.pack_into('<i', data, 88, -1)
struct.pack_into('<f', data, 112, 1.0)
mgef_place = record('MGEF', MGEF_PLACE, sub('EDID', zstr('AltairPlaceHaystackEffect')) +
                    vmad('AltairPlaceHaystackEffect', [('AltairPortableHaystack', REF_PORTABLE)]) +
                    sub('FULL', zstr('Place Haystack')) + sub('DATA', bytes(data)) +
                    sub('DNAM', zstr('Places a haystack in front of you. Climb to anything high above it and jump.')))
spel_place = record('SPEL', SPEL_PLACE, sub('EDID', zstr('AltairPlaceHaystack')) + sub('OBND', bytes(12)) +
                    sub('FULL', zstr('Place Haystack')) + sub('ETYP', struct.pack('<I', 0x00025BEE)) +
                    sub('DESC', zstr('Places a haystack in front of you. Climb to anything high above it and take a leap of faith.')) +
                    sub('SPIT', struct.pack('<IIIfIIffI', 0, 0, 3, 0.0, 1, 0, 0.0, 0.0, 0)) +   # lesser power, FaF, self
                    sub('EFID', struct.pack('<I', MGEF_PLACE)) + sub('EFIT', struct.pack('<fII', 0.0, 0, 0)))
# --- the haystack: vanilla HayMoundL01 model on a scripted activator (no name, so no activation prompt)
acti_hay = record('ACTI', ACTI_HAY, sub('EDID', zstr('AltairHaystack')) +
                  vmad('AltairHaystackScript', [('AltairHaystackLandSound', SOUN_LAND), ('AltairLeapDive', SPEL_ID),
                                                ('AltairLeapOfFaithSound', SOUN_LEAP), ('AltairPlaceHaystack', SPEL_PLACE)] +
                       [(e, f) for f, e, _ in GLOBALS]) +
                  sub('OBND', struct.pack('<6h', -161, -150, 0, 190, 150, 151)) +
                  sub('MODL', zstr(r'AltairLeapOfFaith\HayStackAC1.nif')) +   # AC1-sized, no collision: he sinks in
                  sub('PNAM', bytes.fromhex('64c86400')) + sub('FNAM', bytes(2)))
# --- references in SolitudeWorld's persistent cell: the Solitude haystack and the portable one (initially disabled)
P, DISABLED = 0x400, 0x800
def hay_ref(fid, pos, flags):
    return record('REFR', fid, sub('NAME', struct.pack('<I', ACTI_HAY)) + sub('XSCL', struct.pack('<f', HAY_SCALE)) +
                  sub('DATA', struct.pack('<6f', *pos, 0, 0, 0)), flags)
ref_hay = hay_ref(REF_HAY, HAY_POS, P)
ref_portable = hay_ref(REF_PORTABLE, PORTABLE_POS, P | DISABLED)
ref_hay2 = hay_ref(REF_HAY2, HAY2_POS, P)

wrld = raw_record(SOLITUDE_WORLD, b'WRLD')
cell = raw_record(PERSIST_CELL, b'CELL')
world_children = group(SOLITUDE_WORLD, 1, cell + group(PERSIST_CELL, 6, group(PERSIST_CELL, 8, ref_hay + ref_portable + ref_hay2)))
# --- settings globals, OAR toggle abilities (hidden, reuse the hidden effect) and the settings quest
glob = b''.join(record('GLOB', f, sub('EDID', zstr(e)) + sub('FNAM', b'f') + sub('FLTV', struct.pack('<f', v)))
                for f, e, v in GLOBALS)
off_spells = b''.join(record('SPEL', f, sub('EDID', zstr(e)) + sub('OBND', bytes(12)) + sub('FULL', zstr(e)) +
                             sub('DESC', zstr('')) + sub('SPIT', struct.pack('<IIIfIIffI', 0, 0, 4, 0.0, 0, 0, 0.0, 0.0, 0)) +
                             sub('EFID', struct.pack('<I', MGEF_ID)) + sub('EFIT', struct.pack('<fII', 0.0, 0, 0)))
                      for f, e in OFF_SPELLS)
qust = record('QUST', QUST_SETTINGS, sub('EDID', zstr('AltairAC1Settings')) +
              vmad('AltairAC1SettingsScript', [(e, f) for f, e, _ in GLOBALS] + [(e, f) for f, e in OFF_SPELLS] +
                   [('AltairPlaceHaystack', SPEL_PLACE), ('AltairPortableHaystack', REF_PORTABLE),
                    ('AltairSolitudeHaystack', REF_HAY)]) +
              sub('FULL', zstr('Shadows of Tamriel Settings')) +
              sub('DNAM', struct.pack('<HBBII', 0x0011, 0, 0, 0, 0)) +       # start game enabled, run once
              sub('NEXT', b'') + sub('ANAM', bytes(4)))
groups = [group('GLOB', 0, glob), group('SNDR', 0, sndr_leap + sndr_land + sndr_sync), group('SOUN', 0, soun_leap + soun_land + soun_sync),
          group('MGEF', 0, mgef + mgef_place), group('SPEL', 0, spel + spel_place + off_spells), group('ACTI', 0, acti_hay),
          group('QUST', 0, qust),
          group('WRLD', 0, wrld + world_children)]
n_records = len(GLOBALS) + 3 + 3 + 2 + 2 + len(OFF_SPELLS) + 1 + 1 + 1 + 1 + 3    # GLOBs SNDR SOUN MGEF SPEL ACTI QUST WRLD CELL REFR
n_groups = 8 + 3
tes4 = (sub('HEDR', struct.pack('<fII', 1.71, n_records + n_groups, 0x841)) +
        sub('CNAM', zstr('AltairNative prototype')) +
        sub('SNAM', zstr('Private prototype: AC1 leap of faith off the Solitude bridge into a haystack.')) +
        sub('MAST', zstr('Skyrim.esm')) + sub('DATA', struct.pack('<Q', 0)))
with open(OUT, 'wb') as f:
    f.write(record('TES4', 0, tes4))
    for g in groups:
        f.write(g)
print('wrote', OUT)
