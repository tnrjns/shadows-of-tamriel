"""Mix the AC1 leap-of-faith sounds (exported by ac1_anim_export --sounds) into two 44.1 kHz stereo WAVs for Skyrim.
Gains follow AC1's own sound objects (dB); the whoosh is lifted so it survives Skyrim's mix.
Usage: python tools/mix_lof_sounds.py <snd_dir> <out_dir>"""
import sys, wave, struct, glob, os, math
SRC, OUT = sys.argv[1], sys.argv[2]
RATE = 44100

def load(tag):
    f = glob.glob(os.path.join(SRC, f'*_{tag}_*.wav'))[0]
    w = wave.open(f); n = w.getnframes(); ch = w.getnchannels(); sr = w.getframerate()
    d = struct.unpack('<%dh' % (n * ch), w.readframes(n))
    chans = [[d[i * ch + c] / 32768 for i in range(n)] for c in range(ch)]
    if ch == 1: chans = chans * 2
    out = []
    m = int(n * RATE / sr)
    for c in chans:   # linear resample
        out.append([c[min(n - 1, int(i * sr / RATE))] * (1 - (i * sr / RATE) % 1) + c[min(n - 1, int(i * sr / RATE) + 1)] * ((i * sr / RATE) % 1) for i in range(m)])
    return out

def mix(parts, peak_db, name):
    L = max(int(t * RATE) + len(p[0]) for p, t, g in parts)
    o = [[0.0] * L, [0.0] * L]
    for p, t, g in parts:
        a = 10 ** (g / 20); s = int(t * RATE)
        for c in range(2):
            for i, v in enumerate(p[c]): o[c][s + i] += v * a
    pk = max(max(abs(v) for v in o[0]), max(abs(v) for v in o[1]))
    k = 10 ** (peak_db / 20) / pk
    w = wave.open(os.path.join(OUT, name), 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
    w.writeframes(b''.join(struct.pack('<hh', int(max(-1, min(1, o[0][i] * k)) * 32767), int(max(-1, min(1, o[1][i] * k)) * 32767)) for i in range(L)))
    print(name, f'{L / RATE:.2f}s')

eagle, whoosh = load('3281de70'), load('3f6eec9e')
mix([(eagle, 0.0, -10), (whoosh, 0.0, -14)], -1.0, 'LeapOfFaith.wav')
mix([(whoosh, 0.0, -12), (eagle, 0.35, -8), (eagle, 2.4, -16)], -1.0, 'Synchronize.wav')
land, hay = load('3e6b814d'), load('3d26aa14')
mix([(land, 0.0, -4), (hay, 0.0, -8)], -2.0, 'HaystackLand.wav')
