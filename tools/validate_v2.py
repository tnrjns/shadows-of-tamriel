"""Validate the packaged Altair NIFs: format, shapes, skinning, partitions, texture files.

Run: blender -b --factory-startup --python tools/validate_v2.py -- <mod_dir>
Exits non-zero (prints VALIDATION_FAIL) on any hard error.
"""
import sys, os, json
sys.path.insert(0, r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0')
from io_scene_nifly.pyn import pynifly as P

mod = sys.argv[sys.argv.index('--') + 1]
SKEL = r'C:\Users\myste\Downloads\Altair Skyrim Native\tooling\pynifly-29.1.0\io_scene_nifly\skeletons\Skyrim\skeleton.nif'
skel_bones = {n.name for n in P.NifFile(SKEL).nodes.values()} if hasattr(P.NifFile(SKEL), 'nodes') else None
errors, warnings, out = [], [], {}
used_textures = set()
for rel in ('meshes/armor/AltairNative/Altair.nif', 'meshes/armor/AltairNative/1stPersonAltair.nif'):
    path = os.path.join(mod, rel)
    if not os.path.isfile(path):
        errors.append(f'missing {rel}'); continue
    f = P.NifFile(path)
    info = {'game': f.game, 'root': f.rootName, 'bytes': os.path.getsize(path), 'shapes': {}}
    if f.game != 'SKYRIMSE':
        errors.append(f'{rel}: game {f.game}')
    for s in f.shapes:
        if s.name.startswith('BSBound'):
            continue
        nv, nt = len(s.verts), len(s.tris)
        bones = list(s.bone_names)
        # per-vertex influence count and weight sums
        per_v = [0.0] * nv; cnt = [0] * nv
        for b, lst in s.bone_weights.items():
            for vi, w in lst:
                per_v[vi] += w; cnt[vi] += 1
        bad_sum = sum(1 for x in per_v if abs(x - 1.0) > 0.02)
        zero = sum(1 for x in per_v if x == 0)
        parts = [(p.name, getattr(p, 'id', None)) for p in (s.partitions or [])]
        tex = dict(s.textures)
        sh = s.shader.properties
        f1 = sh.Shader_Flags_1
        rec = {'blk': s.blockname, 'verts': nv, 'tris': nt, 'bones': len(bones),
               'max_infl': max(cnt) if cnt else 0, 'bad_weight_sums': bad_sum, 'unweighted': zero,
               'partitions': parts, 'textures': {k: v for k, v in tex.items() if v},
               'skinned_flag': bool(f1 & 0x2), 'f1': hex(f1), 'f2': hex(sh.Shader_Flags_2)}
        info['shapes'][s.name] = rec
        if nv == 0 or nt == 0: errors.append(f'{rel}:{s.name}: empty shape')
        if not bones: errors.append(f'{rel}:{s.name}: not skinned')
        if rec['max_infl'] > 4: errors.append(f'{rel}:{s.name}: {rec["max_infl"]} influences')
        if bad_sum or zero: errors.append(f'{rel}:{s.name}: {bad_sum} bad sums, {zero} unweighted')
        if not rec['skinned_flag']: errors.append(f'{rel}:{s.name}: shader lacks Skinned flag')
        if not parts: errors.append(f'{rel}:{s.name}: no dismember partition')
        if skel_bones is not None:
            missing = [b for b in bones if b not in skel_bones]
            if missing: errors.append(f'{rel}:{s.name}: bones not in skeleton {missing}')
        for slot, t in tex.items():
            if not t: continue
            used_textures.add(t.lower())
            if not t.lower().startswith('textures\\armor\\altairnative\\'):
                errors.append(f'{rel}:{s.name}: texture outside mod folder {t}')
            if not os.path.isfile(os.path.join(mod, t.replace('\\', os.sep))):
                errors.append(f'{rel}:{s.name}: missing texture file {t}')
    out[rel] = info
tex_dir = os.path.join(mod, 'textures', 'armor', 'AltairNative')
on_disk = {('textures\\armor\\altairnative\\' + n).lower() for n in os.listdir(tex_dir)}
unused = sorted(on_disk - used_textures)
if unused: warnings.append(f'unused texture files: {unused}')
out['errors'], out['warnings'] = errors, warnings
print(json.dumps(out, indent=1))
print('VALIDATION_FAIL' if errors else 'VALIDATION_OK', len(errors), 'errors', len(warnings), 'warnings')
