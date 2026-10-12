"""Write AltairNative.esp: one ArmorAddon (ARMA) + one Armor (ARMO) for Skyrim SE.

FormIDs of vanilla races/keywords/sounds were read from Skyrim.esm with tools/esm_lookup.py
and tools/esm_dump.py. Usage: python tools/build_esp.py <out.esp>
"""
import struct, sys

OUT = sys.argv[1]
SKYRIM = 0x00  # master index of Skyrim.esm
ARMA_ID, ARMO_ID = 0x01000800, 0x01000801   # index 01 = this plugin (one master)

MESH_3RD = 'armor\\AltairNative\\Altair.nif'
MESH_1ST = 'armor\\AltairNative\\1stPersonAltair.nif'
GROUND = 'Clothes\\Monk\\MonkRobesGND.nif'     # vanilla placeholder ground model

DEFAULT_RACE = 0x00000019
RACES = [  # playable + vampire variants + elders (NPC use)
    0x00013740, 0x0008883A,  # Argonian
    0x00013741, 0x0008883C,  # Breton
    0x00013742, 0x0008883D,  # Dark Elf
    0x00013743, 0x00088840,  # High Elf
    0x00013744, 0x00088844,  # Imperial
    0x00013745, 0x00088845,  # Khajiit
    0x00013746, 0x00088794,  # Nord
    0x00013747, 0x000A82B9,  # Orc
    0x00013748, 0x00088846,  # Redguard
    0x00013749, 0x00088884,  # Wood Elf
    0x00067CD8, 0x000A82BA,  # Elder
]
KW_ARMOR_CLOTHING, KW_VENDOR_CLOTHING, KW_CLOTHING_BODY = 0x0006BBE8, 0x0008F95B, 0x000A8657
SND_PICKUP, SND_DROP = 0x0003E879, 0x0003E909   # same as ClothesMonkRobes

def slot(n):
    return 1 << (n - 30)
BIPED = slot(30) | slot(31) | slot(32) | slot(33) | slot(37)   # head, hair, body, hands, feet
ARMOR_TYPE_CLOTHING = 2

def zstr(s):
    return s.encode('cp1252') + b'\0'

def sub(tag, data):
    assert len(data) < 0x10000
    return tag.encode() + struct.pack('<H', len(data)) + data

def record(tag, fid, body, flags=0):
    return tag.encode() + struct.pack('<IIIIHH', len(body), flags, fid, 0, 44, 0) + body

def group(label, records):
    payload = b''.join(records)
    return b'GRUP' + struct.pack('<I4sIHHI', 24 + len(payload), label.encode(), 0, 0, 0, 0) + payload

arma = b''.join([
    sub('EDID', zstr('AltairNativeAA')),
    sub('BOD2', struct.pack('<II', BIPED, ARMOR_TYPE_CLOTHING)),
    sub('RNAM', struct.pack('<I', DEFAULT_RACE)),
    # male/female priority, weight sliders disabled, unknown, detection, unknown, weapon adjust
    sub('DNAM', struct.pack('<BBBBHBBf', 0, 0, 0, 0, 0, 0, 0, 0.0)),
    sub('MOD2', zstr(MESH_3RD)),
    sub('MOD3', zstr(MESH_3RD)),
    sub('MOD4', zstr(MESH_1ST)),
    sub('MOD5', zstr(MESH_1ST)),
    *[sub('MODL', struct.pack('<I', r)) for r in RACES],
])
armo = b''.join([
    sub('EDID', zstr('AltairNativeOutfit')),
    sub('OBND', struct.pack('<6h', -22, -14, 0, 22, 14, 128)),
    sub('FULL', zstr("Altaïr's Assassin Robes")),
    sub('MOD2', zstr(GROUND)),
    sub('MOD4', zstr(GROUND)),
    sub('BOD2', struct.pack('<II', BIPED, ARMOR_TYPE_CLOTHING)),
    sub('YNAM', struct.pack('<I', SND_PICKUP)),
    sub('ZNAM', struct.pack('<I', SND_DROP)),
    sub('RNAM', struct.pack('<I', DEFAULT_RACE)),
    sub('KSIZ', struct.pack('<I', 3)),
    sub('KWDA', struct.pack('<III', KW_ARMOR_CLOTHING, KW_VENDOR_CLOTHING, KW_CLOTHING_BODY)),
    sub('DESC', zstr('')),
    sub('MODL', struct.pack('<I', ARMA_ID)),
    sub('DATA', struct.pack('<if', 250, 3.0)),
    sub('DNAM', struct.pack('<i', 0)),
])
groups = [group('ARMO', [record('ARMO', ARMO_ID, armo)]),
          group('ARMA', [record('ARMA', ARMA_ID, arma)])]
tes4 = b''.join([
    sub('HEDR', struct.pack('<fII', 1.71, 4, 0x802)),   # 2 records + 2 groups
    sub('CNAM', zstr('AltairNative prototype')),
    sub('SNAM', zstr('Private prototype: Altair outfit as a Skyrim-native armor (ARMA+ARMO).')),
    sub('MAST', zstr('Skyrim.esm')),
    sub('DATA', struct.pack('<Q', 0)),
])
with open(OUT, 'wb') as f:
    f.write(record('TES4', 0, tes4))
    for g in groups:
        f.write(g)
print('wrote', OUT)
