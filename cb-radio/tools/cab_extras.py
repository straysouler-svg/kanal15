"""Per-driver cab sounds under his voice (2026-11-04): the music on his radio, a police scanner, sirens,
a spoon in a tea glass, the kitten, phone pings, wipers... All synthesised (no samples, no credits).
A CB eats most of it - it only has to read as "that's Кардан's cab", not as hi-fi.

Per actor in phrases/level3_eleven.json, cab.extras:
  [{"kind": "music", "style": "rock", "db": -14, "chance": 0.9}, {"kind": "siren", "db": -16, "chance": 0.2}]
db = level relative to the voice RMS in the CB band (like the other bed parts); chance = per transmission.
Styles: retro, rock, pop, dance, hiphop, classic, romance, folk.
Kinds: music, scanner, siren, clink, meow, knit, ping, buzz, ringtone, navi, blinker, wipers, lighter,
       radar, airhorn, pages, burner, bark, whine (Граф: audio/fx/graf_bark_*.wav, graf_whine_*.wav).
"""
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

import cab as C

SR = C.SR


# ---------------------------------------------------------------- building blocks
def _env(m, a=0.005, r=0.04):
    e = np.ones(m)
    ai, ri = max(1, min(m // 2, int(a * SR))), max(1, min(m // 2, int(r * SR)))
    e[:ai] = np.linspace(0, 1, ai)
    e[-ri:] *= np.linspace(1, 0, ri)
    return e


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tone(f, dur, rng, harm=8, roll=1.0, decay=0.0, vib=0.0, detune=0.0, inharm=0.0, a=0.005, r=0.04):
    """Additive note: harmonics 1..harm at 1/h**roll; decay (1/s) makes it plucked/struck."""
    m = max(8, int(dur * SR))
    t = np.arange(m) / SR
    ph = 2 * np.pi * f * (1 + detune) * t
    if vib:
        ph = ph + vib * np.sin(2 * np.pi * 5.3 * t)
    x = np.zeros(m)
    for h in range(1, harm + 1):
        if f * h > 9000:
            break
        k = h * np.sqrt(1 + inharm * h * h)
        amp = 1.0 / h ** roll
        if decay:
            amp = amp * np.exp(-t * decay * (1 + 0.35 * (h - 1)))
        x += amp * np.sin(ph * k + rng.uniform(0, 6.3))
    return x * _env(m, a, r)


def _place(out, x, start):
    s = int(start * SR)
    if s >= len(out) or s + len(x) <= 0:
        return
    a, b = max(0, s), min(len(out), s + len(x))
    out[a:b] += x[a - s:b - s]


def _kick(rng):
    m = int(0.22 * SR)
    t = np.arange(m) / SR
    f = 45 + 80 * np.exp(-t * 30)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)
    x[:int(0.004 * SR)] += rng.standard_normal(int(0.004 * SR)) * 0.4      # beater click
    return x


def _snare(rng, clap=False):
    m = int(0.18 * SR)
    t = np.arange(m) / SR
    n = C._bp(rng.standard_normal(m), 1200, 6000) * np.exp(-t * (30 if clap else 22))
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 35) * (0.0 if clap else 0.6)
    return n / C._rms(n) * 0.35 + body


def _hat(rng):
    m = int(0.05 * SR)
    return C._hp(rng.standard_normal(m), 5000) * np.exp(-np.arange(m) / SR * 90) * 0.25


def _room(x, rng, sec=0.07, wet=0.25):
    """Small cab: a very short reverb so it sounds like a speaker in a box."""
    m = int(sec * SR)
    ir = rng.standard_normal(m) * np.exp(-np.arange(m) / SR / (sec / 5))
    y = fftconvolve(x, ir)[:len(x)]
    return x + wet * y / (C._rms(y) + 1e-12) * C._rms(x)


def _speaker(x, rng, lo=150, hi=5500):
    return _room(C._bp(x, lo, hi), rng)


# ---------------------------------------------------------------- music on the cab radio
CH = {  # chord tones (semitones from the root)
    "maj": (0, 4, 7), "min": (0, 3, 7), "5": (0, 7, 12),
}


def _chords(prog, bar0, nbars):
    return [prog[(bar0 + i) % len(prog)] for i in range(nbars)]


MUSIC_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "music"
# real recordings (Wikimedia Commons, Public domain / CC0, see music/CREDITS.md) - user 2026-11-04:
# the synthesised tunes sounded like a toy ("тутуту"), wants guitar or classical
POOLS = {
    "classic": ["piano_"],                                         # Профессор, Сорока
    "romance": ["guitar_gymnopedie", "guitar_romance"],
    "ten": ["ten_lyria_"],                                         # Тень: уральский рок / новая волна 80-х
    "romance_sova": ["romance_lyria_", "guitar_gymnopedie", "guitar_romance"],            # Сова, Тень
    "retro": ["guitar_gran_vals", "guitar_romance", "piano_chopin_n16"],
    "chanson": ["chanson_"],                                       # Михалыч, Палыч: Лещенко, Вавич, Плевицкая
    "folk_ru": ["folk_", "chanson_plevitskaya"],                   # Петровна (до своей «эстрады» на ElevenLabs)
    "folk": ["guitar_gran_vals", "strum_"],
    "folk_yanek": ["yanek_lyria_med", "guitar_gran_vals", "strum_"],                        # Янек
    "pop": ["pop_lyria_lastochka", "guitar_romance", "guitar_leyenda", "folk_vyaltseva"],   # Ласточка
    "dance": ["dance_lyria_lisa", "strum_", "guitar_leyenda", "rock_rust_rebellion"],
    "vitek": ["svadba_lyria_vitek", "rock_light_", "rock_rockenergy"],  # Лиса
    "rock_light": ["rock_light_", "rock_modernrockboy", "rock_take_the_lead", "rock_rockenergy"],  # Стас, Витёк, Студент
    "hiphop": ["rock_light_", "rock_modernrockboy", "rock_take_the_lead"],
    "rock": ["rock_rockenergy", "rock_grunge", "rock_hard", "rock_rust", "rock_cool", "rock_lyria_"],  # Борода
    "rock_kardan": ["rock_lyria_kardan", "rock_grunge", "rock_hard", "rock_lyria_"],     # Кардан: его группа чаще
    "drums": ["drums_"],                                          # закреплённые барабанные нарезки (12.11: «Это барабанное соло!»)
    "chanson_mih": ["chanson_lyria_kilometry", "chanson_lyria_starushka", "chanson_leshchenko", "chanson_vavich"],
    "chanson_palych": ["chanson_lyria_shlagbaum", "chanson_leshchenko", "chanson_plevitskaya"],
    "estrada": ["folk_lyria_", "folk_"],                           # Петровна
    "dutar": ["dutar_lyria_", "strum_"],                           # Рустам «Самарканд»: дутар, своя песня «Оппок»
    "uzpop": ["uzpop_lyria_", "dance_lyria_lisa"],                 # Бахтияр «Ковбой»: узбекская попса
    "course": ["course_en_"],                                      # Бахтияр: аудиокурс английского бормочет
}
_REC = {}


def _recordings(style):
    files = sorted(f for f in MUSIC_DIR.glob("*.wav") if any(f.stem.startswith(p) for p in POOLS.get(style, [])))
    return files


def _load(f):
    if f not in _REC:
        import soundfile as sf
        from scipy.signal import resample_poly
        from math import gcd
        x, sr = sf.read(f, dtype="float32")
        g = gcd(SR, sr)
        _REC[f] = resample_poly(x, SR // g, sr // g).astype(np.float32)   # 22050 -> 48000 = 320/147
    return _REC[f]


DRUMMY = ("rock", "dance", "hiphop", "drums")         # стили, где ломоть обязан быть с барабанами (12.11: случайный ломоть попадал в лирическое окно — у Кардана играло «пианино»)


def _attacks(seg):
    d = np.abs(np.diff(seg, axis=0))
    return float(np.mean(d > 4 * np.median(d)))


def recorded(n, rng, style):
    """A random stretch of a real recording (not a quiet bit), as heard from the cab speakers.
    Для DRUMMY-стилей из громких кандидатов выбирается самый «ударный» — без барабанов рок не рок."""
    files = _recordings(style)
    if not files:
        return None
    x = _load(files[int(rng.integers(0, len(files)))])
    if len(x) <= n:
        x = np.tile(x, n // len(x) + 2)
    best = None
    for _ in range(12):                              # skip silences between pieces / fades
        s = int(rng.integers(0, len(x) - n))
        seg = x[s:s + n].astype(np.float64)
        if C._rms(seg) <= 0.04:
            continue
        if not style.startswith(DRUMMY):
            best = seg
            break
        if best is None or _attacks(seg) > _attacks(best):
            best = seg
    if best is None:                                 # вся запись тихая — берём как есть
        best = x[int(rng.integers(0, len(x) - n)):][:n].astype(np.float64)
    seg = best
    f = min(n // 4, int(0.3 * SR))
    seg = seg.copy()
    seg[:f] *= np.linspace(0, 1, f)
    seg[-f:] *= np.linspace(1, 0, f)
    if style == "retro" or style.startswith("chanson"):   # an old receiver / a worn cassette
        seg = C._bp(seg, 350, 2800)
        seg = np.tanh(seg / (np.max(np.abs(seg)) + 1e-9) * 1.6)
        seg += C._bp(rng.standard_normal(n), 1000, 4000) * 0.02
    return _speaker(seg, rng)


def music(n, rng, style):
    rec = recorded(n, rng, style)
    if rec is not None:
        return rec
    dur = n / SR + 1.0
    out = np.zeros(int(dur * SR))
    off = rng.uniform(0, 2.0)                       # we tune in somewhere in the middle of a song
    put = lambda x, t: _place(out, x, t - off)      # noqa: E731
    if style == "rock":                             # Кардан: distorted power chords, 132 bpm
        bpm = rng.uniform(126, 138)
        e = 30 / bpm                                # eighth note
        prog = [(40, "5"), (43, "5"), (45, "5"), (48, "5"), (40, "5"), (43, "5"), (38, "5"), (45, "5")]
        bars = int(dur / (8 * e)) + 2
        gtr = np.zeros_like(out)
        for b, (root, q) in enumerate(_chords(prog, int(rng.integers(0, 8)), bars)):
            for i in range(8):
                t = (b * 8 + i) * e
                ch = sum(_tone(_hz(root + s), e * 0.92, rng, harm=14, roll=0.9, detune=rng.uniform(-0.003, 0.003),
                               decay=4.0) for s in CH[q])
                _place(gtr, ch, t - off)
                if i in (0, 4):
                    put(_kick(rng) * 1.2, t)
                if i in (2, 6):
                    put(_snare(rng) * 1.1, t)
                put(_hat(rng), t)
        gtr = np.tanh(gtr / (np.max(np.abs(gtr)) + 1e-9) * 7)    # fuzz
        out += C._lp(gtr, 3800) * 0.9
    elif style in ("pop", "dance"):                 # Ласточка / Лиса: four on the floor, pad, bass
        bpm = rng.uniform(112, 120) if style == "pop" else rng.uniform(122, 128)
        q = 60 / bpm
        prog = ([(60, "maj"), (55, "maj"), (57, "min"), (53, "maj")] if style == "pop"
                else [(57, "min"), (53, "maj"), (60, "maj"), (55, "maj")])
        bars = int(dur / (4 * q)) + 2
        for b, (root, kind) in enumerate(_chords(prog, int(rng.integers(0, 4)), bars)):
            t0 = b * 4 * q
            pad = sum(_tone(_hz(root + s), 4 * q, rng, harm=10, roll=1.3, a=0.08, r=0.2, vib=0.002)
                      for s in CH[kind])
            put(C._lp(pad, 2500) * 0.5, t0)
            for i in range(4):
                put(_kick(rng), t0 + i * q)
                put(_hat(rng) * 1.3, t0 + i * q + q / 2)
                if i in (1, 3):
                    put(_snare(rng, clap=True) * 0.8, t0 + i * q)
                for k in range(2):
                    put(_tone(_hz(root - 12), q / 2 * 0.8, rng, harm=5, roll=1.5, decay=6) * 0.7, t0 + i * q + k * q / 2)
            if rng.random() < 0.7:                  # a hook on a bell
                for i, s in enumerate(rng.choice([0, 4, 7, 12, 9], 4)):
                    put(_tone(_hz(root + 12 + int(s)), q, rng, harm=4, roll=2, decay=7) * 0.45, t0 + i * q)
    elif style == "hiphop":                         # Стас: boom-bap, bass, a bell loop
        bpm = rng.uniform(86, 94)
        q = 60 / bpm
        prog = [(45, "min"), (41, "maj"), (43, "maj"), (40, "min")]
        bars = int(dur / (4 * q)) + 2
        loop = [int(x) for x in rng.choice([0, 3, 5, 7, 10, 12], 8)]
        for b, (root, kind) in enumerate(_chords(prog, int(rng.integers(0, 4)), bars)):
            t0 = b * 4 * q
            for t in (0, 1.5 * q, 2.5 * q):
                put(_kick(rng) * 1.3, t0 + t)
            for t in (q, 3 * q):
                put(_snare(rng) * 1.1, t0 + t)
            for i in range(8):
                put(_hat(rng), t0 + i * q / 2)
                put(_tone(_hz(root + 24 + loop[i]), q / 2, rng, harm=3, roll=2, decay=9) * 0.35, t0 + i * q / 2)
            put(_tone(_hz(root), 2 * q, rng, harm=3, roll=1.5, a=0.01, r=0.1) * 0.9, t0)
            put(_tone(_hz(root), 2 * q, rng, harm=3, roll=1.5, a=0.01, r=0.1) * 0.9, t0 + 2 * q)
    elif style == "classic":                        # Профессор: piano, Chopin-ish arpeggios
        bpm = rng.uniform(66, 76)
        e = 30 / bpm
        prog = [(57, "min"), (50, "min"), (55, "maj"), (48, "maj"), (53, "maj"), (50, "min"), (52, "maj"), (57, "min")]
        bars = int(dur / (8 * e)) + 2
        for b, (root, kind) in enumerate(_chords(prog, int(rng.integers(0, 8)), bars)):
            t0 = b * 8 * e
            tones = [root - 12, root - 12 + CH[kind][2], root + CH[kind][1], root + CH[kind][2],
                     root + 12, root + CH[kind][2], root + CH[kind][1], root - 12 + CH[kind][2]]
            for i, m_ in enumerate(tones):
                put(_tone(_hz(m_), 1.6, rng, harm=10, roll=1.6, decay=2.2, inharm=0.0004, a=0.002) * 0.55, t0 + i * e)
            for i in range(0, 8, 2):                # right hand melody in quarters
                m_ = root + 12 + int(rng.choice([CH[kind][1], CH[kind][2], 12, 14 if kind == "maj" else 15]))
                put(_tone(_hz(m_), 1.4, rng, harm=10, roll=1.5, decay=2.0, inharm=0.0004, a=0.002) * 0.7, t0 + i * e)
    elif style == "romance":                        # Сова: nylon guitar, slow 6/8
        e = rng.uniform(0.24, 0.3)
        prog = [(45, "min"), (50, "min"), (43, "maj"), (48, "maj"), (45, "min"), (40, "maj")]
        bars = int(dur / (6 * e)) + 2
        for b, (root, kind) in enumerate(_chords(prog, int(rng.integers(0, 6)), bars)):
            t0 = b * 6 * e
            pat = [root, root + 12 + CH[kind][2] - 12, root + 12 + CH[kind][1], root + 12 + CH[kind][2] - 12 + 12,
                   root + 12 + CH[kind][1], root + 12 + CH[kind][2] - 12]
            for i, m_ in enumerate(pat):
                put(_tone(_hz(m_), 1.5, rng, harm=12, roll=1.1, decay=3.0, a=0.001) * 0.6, t0 + i * e)
    elif style == "folk":                           # Янек: accordion polka on a Belarusian station
        bpm = rng.uniform(104, 116)
        q = 60 / bpm
        prog = [(55, "maj"), (50, "maj"), (55, "maj"), (48, "maj"), (50, "maj"), (55, "maj")]
        bars = int(dur / (2 * q)) + 2
        reed = lambda f, d: (_tone(f, d, rng, harm=9, roll=0.8, detune=0.004, a=0.02)       # noqa: E731
                             + _tone(f, d, rng, harm=9, roll=0.8, detune=-0.004, a=0.02))
        for b, (root, kind) in enumerate(_chords(prog, int(rng.integers(0, 6)), bars)):
            t0 = b * 2 * q
            put(reed(_hz(root - 12), q * 0.45) * 0.5, t0)
            put(sum(reed(_hz(root + s), q * 0.3) for s in CH[kind]) * 0.25, t0 + q)
            for i in range(4):
                s = int(rng.choice([0, 2, 4, 7, 9, 12])) if kind == "maj" else int(rng.choice([0, 3, 7, 12]))
                put(reed(_hz(root + 12 + s), q / 2 * 0.85) * 0.45, t0 + i * q / 2)
    else:                                           # "retro": Soviet estrada waltz on an old receiver
        bpm = rng.uniform(140, 160)
        q = 60 / bpm
        prog = [(57, "min"), (50, "min"), (52, "maj"), (57, "min"), (48, "maj"), (55, "maj"), (52, "maj"), (57, "min")]
        bars = int(dur / (3 * q)) + 2
        for b, (root, kind) in enumerate(_chords(prog, int(rng.integers(0, 8)), bars)):
            t0 = b * 3 * q
            put(_tone(_hz(root - 12), q * 0.9, rng, harm=5, roll=1.3, decay=3) * 0.7, t0)
            for i in (1, 2):
                put(sum(_tone(_hz(root + s), q * 0.6, rng, harm=8, roll=1.0, detune=0.003, a=0.01) for s in CH[kind])
                    * 0.18, t0 + i * q)
            m_ = root + 12 + int(rng.choice(CH[kind] + (12,)))
            put(_tone(_hz(m_), 3 * q * 0.95, rng, harm=6, roll=1.4, vib=0.25, a=0.04, r=0.15) * 0.6, t0)
        out = C._bp(out, 350, 2800)                 # an old receiver
        out = np.tanh(out / (np.max(np.abs(out)) + 1e-9) * 1.8)
        out += C._bp(rng.standard_normal(len(out)), 1000, 4000) * 0.02          # a little hiss
    out = out[:n]
    return _speaker(out, rng)


# ---------------------------------------------------------------- events
def scanner(n, rng):
    """Палыч's police scanner: squelch bursts with a garbled voice in them."""
    out = np.zeros(n)
    t = 0.0 if rng.random() < 0.5 else rng.uniform(0.2, 1.5)
    while t < n / SR:
        d = rng.uniform(0.8, 2.5)
        m = int(d * SR)
        tt = np.arange(m) / SR
        syl = 0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(3.5, 6) * tt + rng.uniform(0, 6)) ** 2
        f1 = 700 + 500 * C._slow(m, rng, 4, 0.6)
        voice = np.zeros(m)
        src = rng.standard_normal(m)
        for k in range(0, m, 2400):                 # crude formant: band moves every 50 ms
            e = min(m, k + 2400)
            fc = float(f1[k])
            voice[k:e] = C._bp(src[k:e], max(250, fc - 300), fc + 600)
        burst = voice / C._rms(voice) * syl
        burst[:int(0.03 * SR)] += np.sin(2 * np.pi * 1000 * np.arange(int(0.03 * SR)) / SR) * 2   # tone
        tail = rng.standard_normal(int(0.12 * SR)) * 1.2                                         # squelch
        x = np.concatenate([burst * _env(m, 0.005, 0.01), tail])
        _place(out, C._bp(x, 400, 3000), t)
        t += d + rng.uniform(1.5, 5)
    return out


def siren(n, rng):
    """An emergency vehicle passing: Euro two-tone or a wail, with Doppler."""
    m = n
    t = np.arange(m) / SR
    tc, w = rng.uniform(0.3, 0.8) * m / SR, rng.uniform(1.0, 2.5)
    dop = 1.0 + 0.035 * -np.tanh((t - tc) / (w * 0.4))
    if rng.random() < 0.6:
        per = rng.uniform(1.1, 1.3)
        f = np.where((t % per) < per / 2, 440.0, 587.0)
    else:
        per = rng.uniform(0.35, 0.6)
        f = 700 + 500 * (0.5 - 0.5 * np.cos(2 * np.pi * t / per))
    ph = 2 * np.pi * np.cumsum(f * dop) / SR
    x = sum(np.sin(ph * h) / h for h in range(1, 7))
    env = 1.0 / (1.0 + ((t - tc) / w) ** 2)
    return C._lp(x, 2500) * env


def clink(n, rng):
    """Петровна: a spoon in a glass in a подстаканник."""
    out = np.zeros(n)
    t = rng.uniform(0.1, 0.6) * n / SR
    for _ in range(int(rng.integers(2, 5))):
        f0 = rng.uniform(2100, 2700)
        m = int(0.5 * SR)
        k = np.arange(m) / SR
        x = sum(np.sin(2 * np.pi * f0 * r * k) * np.exp(-k * d) * a
                for r, d, a in ((1, 9, 1.0), (1.51, 14, 0.5), (2.76, 22, 0.3), (0.62, 12, 0.4)))
        _place(out, x * rng.uniform(0.6, 1.0), t)
        t += rng.uniform(0.12, 0.3)
    return out


def meow(n, rng):
    """Дизель the kitten: a small 'мяу' somewhere in the cab."""
    out = np.zeros(n)
    for j in range(1 if rng.random() < 0.7 else 2):
        d = rng.uniform(0.45, 0.8)
        m = int(d * SR)
        u = np.linspace(0, 1, m)
        f0 = rng.uniform(650, 850) * (1 + 0.45 * np.sin(np.pi * u) ** 1.5) * (1 - 0.15 * u)
        ph = 2 * np.pi * np.cumsum(f0) / SR
        x = sum(np.sin(ph * h) / h ** 0.7 for h in range(1, 7))
        # m-e-o-w: muffled start, open middle, closing end
        open_ = np.sin(np.pi * np.clip(u * 1.2, 0, 1)) ** 0.7
        bright = C._bp(x, 1200, 3600) * open_ + C._lp(x, 1000) * (1 - open_ * 0.6)
        env = np.sin(np.pi * u) ** 0.6
        _place(out, bright * env, rng.uniform(0.1, 0.6) * n / SR + j * (d + 0.4))
    return out


def knit(n, rng):
    """Сорока knitting: tiny needle clicks."""
    out = np.zeros(n)
    t = rng.uniform(0, 0.5)
    k = np.arange(int(0.006 * SR))
    while t < n / SR:
        f = rng.uniform(3000, 4200)
        _place(out, np.sin(2 * np.pi * f * k / SR) * np.exp(-k / 60) * rng.uniform(0.5, 1), t)
        t += rng.uniform(0.18, 0.45) if rng.random() < 0.85 else rng.uniform(0.8, 1.6)
    return out


def ping(n, rng):
    """Стас's phone: messenger / likes notifications."""
    out = np.zeros(n)
    for _ in range(int(rng.integers(1, 4))):
        t = rng.uniform(0.05, 0.85) * n / SR
        for i, f in enumerate((1318.5, 1760.0) if rng.random() < 0.6 else (1568.0, 2093.0, 1568.0)):
            _place(out, _tone(f, 0.25, rng, harm=2, roll=2, decay=14), t + i * 0.09)
    return out


def buzz(n, rng):
    """A phone vibrating on the dashboard (Витёк's mum calling)."""
    out = np.zeros(n)
    t = rng.uniform(0.0, 0.4) * n / SR
    while t < n / SR:
        m = int(0.7 * SR)
        k = np.arange(m) / SR
        x = np.sign(np.sin(2 * np.pi * 165 * k)) * (1 + 0.3 * np.sin(2 * np.pi * 9 * k))
        x = C._bp(x, 200, 2500) + C._bp(rng.standard_normal(m), 1500, 4000) * 0.15     # rattling on plastic
        _place(out, x * _env(m, 0.01, 0.02), t)
        t += 1.3
    return out


def ringtone(n, rng):
    """A marimba ringtone (Студент's mum / Витёк's brother)."""
    out = np.zeros(n)
    t = rng.uniform(0, 0.4) * n / SR
    mel = [76, 79, 84, 79, 81, 84, 88, 84]
    while t < n / SR:
        for i, m_ in enumerate(mel):
            _place(out, _tone(_hz(m_), 0.3, rng, harm=4, roll=2.5, decay=12) * 0.8, t + i * 0.13)
        t += len(mel) * 0.13 + 0.7
    return out


def navi(n, rng):
    """Студент's satnav: a chime before an instruction."""
    out = np.zeros(n)
    t = rng.uniform(0.1, 0.7) * n / SR
    for i, m_ in enumerate((84, 79, 76)):
        _place(out, _tone(_hz(m_), 0.5, rng, harm=3, roll=2, decay=6), t + i * 0.16)
    return out


def blinker(n, rng):
    return C.blinker(n, rng)


def wipers(n, rng):
    """Тень's wipers: swish ... thump."""
    out = np.zeros(n)
    per = rng.uniform(1.2, 1.5)
    t = rng.uniform(0, per)
    while t < n / SR:
        m = int(per * 0.45 * SR)
        sw = C._bp(rng.standard_normal(m), 900, 3200) * np.sin(np.linspace(0, np.pi, m)) ** 2
        k = np.arange(int(0.05 * SR))
        thump = np.sin(2 * np.pi * 320 * k / SR) * np.exp(-k / 250) * 2.5
        _place(out, sw, t)
        _place(out, thump, t + m / SR)
        t += per
    return out


def lighter(n, rng):
    """Zippo: the lid clicks open, the flint wheel scrapes."""
    out = np.zeros(n)
    t = rng.uniform(0.1, 0.5) * n / SR
    k = np.arange(int(0.012 * SR))
    clickx = np.sin(2 * np.pi * 2600 * k / SR) * np.exp(-k / 90) * 2
    _place(out, clickx, t)
    m = int(0.09 * SR)
    _place(out, C._bp(rng.standard_normal(m), 2000, 6000) * np.exp(-np.arange(m) / SR * 25) * 1.5, t + 0.35)
    return out


def radar(n, rng):
    """Борода's radar detector: chirps."""
    out = np.zeros(n)
    t = rng.uniform(0.1, 0.6) * n / SR
    for i in range(int(rng.integers(3, 7))):
        m = int(0.08 * SR)
        k = np.arange(m) / SR
        _place(out, np.sin(2 * np.pi * (2400 + 600 * k / k[-1]) * k) * _env(m, 0.003, 0.01), t + i * 0.16)
    return out


def airhorn(n, rng):
    """His own air horn, close."""
    h = C.horn(rng, n)
    return h


def pages(n, rng):
    """Профессор turns a page."""
    out = np.zeros(n)
    m = int(0.35 * SR)
    x = C._bp(rng.standard_normal(m), 1500, 7000) * np.sin(np.linspace(0, np.pi, m)) ** 3
    _place(out, x, rng.uniform(0.1, 0.7) * n / SR)
    return out


def timer(n, rng):
    """Сорока's rest timer on the tablet: a neat double beep."""
    out = np.zeros(n)
    t = rng.uniform(0.1, 0.7) * n / SR
    for i in range(2):
        m = int(0.07 * SR)
        _place(out, np.sin(2 * np.pi * 1975 * np.arange(m) / SR) * _env(m, 0.003, 0.01), t + i * 0.13)
    return out


def burner(n, rng):
    """Рустам: a camping gas burner under the kettle - steady hiss with a flicker, now and then the water rumbles."""
    t = np.arange(n) / SR
    hiss = C._bp(rng.standard_normal(n), 1800, 7000)
    flick = 1 + 0.25 * np.sin(2 * np.pi * rng.uniform(5, 9) * t) * C._lp(rng.standard_normal(n), 3)
    rumble = C._bp(rng.standard_normal(n), 90, 380) * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(0.3, 0.7) * t)) ** 3
    x = hiss * flick * 0.6 + rumble * 0.9
    f = min(n // 4, int(0.25 * SR))
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    return x


_FX = {}


def _fx_takes(prefix):
    """Recorded takes audio/fx/<prefix>_*.wav (48 kHz mono), e.g. Граф's bark made with ElevenLabs SFX."""
    if prefix not in _FX:
        import soundfile as sf
        d = Path(__file__).resolve().parents[1] / "audio" / "fx"
        _FX[prefix] = [sf.read(f, dtype="float32")[0] for f in sorted(d.glob(f"{prefix}_*.wav"))]
    return _FX[prefix]


def _take(n, rng, prefix, start=(0.05, 0.6)):
    out = np.zeros(n)
    takes = _fx_takes(prefix)
    if takes:
        x = takes[int(rng.integers(0, len(takes)))]
        x = x.mean(axis=1) if x.ndim > 1 else x
        _place(out, x[: n].astype(np.float64), rng.uniform(*start) * n / SR)
    return out


def bark(n, rng):
    """Граф (Вера «Кинолог»): an old German shepherd barks in the cab - he barks at the PTT."""
    return _take(n, rng, "graf_bark", (0.0, 0.5))


def whine(n, rng):
    """Граф whines: wants a walk."""
    return _take(n, rng, "graf_whine")


EVENTS = {"timer": timer, "scanner": scanner, "siren": siren, "clink": clink, "meow": meow, "knit": knit, "ping": ping,
          "buzz": buzz, "ringtone": ringtone, "navi": navi, "blinker": blinker, "wipers": wipers,
          "lighter": lighter, "radar": radar, "airhorn": airhorn, "pages": pages,
          "burner": burner, "bark": bark, "whine": whine}
SPARSE = {"timer", "clink", "meow", "ping", "navi", "lighter", "radar", "airhorn", "pages", "siren", "bark", "whine"}


def render(n, extras, rng):
    """Sum of this cab's extras, levels relative to a voice RMS of 1.0 (cab.bed scales by ref_rms)."""
    out = np.zeros(n)
    for ex in extras or []:
        if rng.random() > ex.get("chance", 1.0):
            continue
        kind = ex["kind"]
        x = music(n, rng, ex.get("style", "retro")) if kind == "music" else EVENTS[kind](n, rng)
        if not np.any(x):
            continue
        lvl = 10 ** ((ex.get("db", -20) + rng.uniform(-2, 2)) / 20)
        if kind in SPARSE:                          # sparse sounds: level by peak in the CB band
            xb = C._bp(x, 300, 3200)
            x = x / (np.max(np.abs(xb)) + 1e-9) * 2.0
        else:
            x = C._audible(x)
        out += x * lvl
    return out
