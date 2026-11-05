"""Cab background for a CB transmission: what the other driver's mic hears around his voice.

Everything is synthesised (no samples, no credits):
- diesel: firing pulses of a 6-cylinder 4-stroke (rpm/60*3 Hz) with uneven cylinders
  (the typical diesel "лопотание"), slow rpm drift, cab body resonances, combustion grit;
- road: low tyre roar + mid hiss with slow swell, occasional expansion-joint thumps "ту-тук";
- wind: high hiss with gusts (stronger at speed);
- cab: little rattles/creaks; sometimes the turn-signal relay ticking.
The result goes UNDER the dry voice, then the whole thing goes through radio() (CB band 300-3200 Hz),
so the low rumble mostly turns into the familiar mid-range grumble of a truck CB.

Per actor settings: "cab" in phrases/level3_eleven.json, e.g.
  {"rpm": 1300, "engine_db": -14, "road_db": -20, "wind_db": -32, "rattle": 0.6, "turbo": 0.2}
dB values are relative to the voice RMS.
"""
import numpy as np
from scipy.signal import butter, lfilter, sosfilt

SR = 48000


def _bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="bandpass", fs=SR, output="sos"), x)


def _lp(x, f, order=2):
    return sosfilt(butter(order, f, btype="lowpass", fs=SR, output="sos"), x)


def _hp(x, f, order=2):
    return sosfilt(butter(order, f, btype="highpass", fs=SR, output="sos"), x)


def _reson(x, f, q):
    """Two-pole resonator (cab panel / engine block mode)."""
    r = np.exp(-np.pi * f / q / SR)
    th = 2 * np.pi * f / SR
    return lfilter([1 - r], [1, -2 * r * np.cos(th), r * r], x)


def _rms(x):
    return float(np.sqrt(np.mean(np.square(x))) + 1e-12)


def _slow(n, rng, rate_hz, depth):
    """Smooth random wobble around 1.0."""
    k = max(4, int(n / SR * rate_hz) + 4)
    pts = rng.uniform(-1, 1, k)
    curve = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    curve = _lp(curve, max(rate_hz, 0.05), 1) if n > 64 else curve
    return 1.0 + depth * curve / (np.max(np.abs(curve)) + 1e-9)


def engine(n, rng, rpm=1300, turbo=0.0):
    rpm_curve = rpm * _slow(n, rng, 0.25, 0.04)               # driver's foot, road load
    f_fire = rpm_curve / 60.0 * 3.0                            # 6 cyl, 4-stroke
    phase = np.cumsum(f_fire / SR)
    idx = np.nonzero(np.diff(np.floor(phase)) > 0)[0]
    cyl = rng.uniform(0.75, 1.25, 6)                           # uneven cylinders -> "лопотание"
    exc = np.zeros(n)
    burst = int(0.004 * SR)
    shape = np.exp(-np.arange(burst) / (0.0011 * SR))
    for j, i in enumerate(idx):
        amp = cyl[j % 6] * rng.uniform(0.85, 1.15)
        seg = shape * (0.6 + 0.4 * rng.standard_normal(burst)) * amp
        e = min(n, i + burst)
        exc[i:e] += seg[: e - i]
    body = (_reson(exc, 95, 6) * 1.0 + _reson(exc, 180, 7) * 0.8 + _reson(exc, 340, 8) * 0.6
            + _reson(exc, 620, 9) * 0.45 + _reson(exc, 1150, 10) * 0.25)
    # combustion grit: noise gated by the firing pulses
    gate = _lp(np.abs(exc), 400, 1)
    grit = _bp(rng.standard_normal(n), 400, 2600) * (gate / (np.max(gate) + 1e-9))
    out = body / _rms(body) + 0.35 * grit / _rms(grit)
    if turbo > 0:                                              # faint turbo whistle following rpm
        ft = 2200 + (rpm_curve - 1000) * 1.2
        whine = np.sin(2 * np.pi * np.cumsum(ft / SR)) * _slow(n, rng, 0.5, 0.5)
        out += turbo * 0.12 * whine
    return out / _rms(out)


def road(n, rng):
    roar = _lp(rng.standard_normal(n), 350) * 1.0
    hiss = _bp(rng.standard_normal(n), 600, 3500) * 0.35
    out = (roar / _rms(roar) + hiss / _rms(hiss) * 0.5) * _slow(n, rng, 0.3, 0.25)
    # expansion joints: "ту-тук" (front axle, then rear ~0.3 s later)
    if rng.random() < 0.35:
        for _ in range(rng.integers(1, 3)):
            t0 = int(rng.uniform(0.1, 0.8) * n)
            for d, a in ((0, 1.0), (rng.uniform(0.22, 0.38), 0.8)):
                s = t0 + int(d * SR)
                if s + 2400 < n:
                    k = np.arange(2400)
                    out[s:s + 2400] += a * 3.0 * np.exp(-k / 500) * np.sin(2 * np.pi * 70 * k / SR)
    return out / _rms(out)


def wind(n, rng):
    w = _bp(rng.standard_normal(n), 900, 5000) * _slow(n, rng, 0.6, 0.6)
    return w / _rms(w)


def rattles(n, rng, amount):
    out = np.zeros(n)
    for _ in range(int(rng.poisson(amount * 6 * n / SR))):
        s = int(rng.uniform(0, n - 1200))
        k = np.arange(1200)
        f = rng.uniform(1500, 4000)
        out[s:s + 1200] += np.exp(-k / rng.uniform(80, 250)) * np.sin(2 * np.pi * f * k / SR) * rng.uniform(0.3, 1)
    return out


def blinker(n, rng):
    out = np.zeros(n)
    period = int(rng.uniform(0.62, 0.72) * SR)                 # relay tick ... tock
    start = int(rng.uniform(0, period))
    k = np.arange(600)
    tick = np.exp(-k / 70) * np.sin(2 * np.pi * 2300 * k / SR)
    tock = np.exp(-k / 90) * np.sin(2 * np.pi * 1700 * k / SR) * 0.8
    for s in range(start, n - 600, period):
        out[s:s + 600] += tick
        h = s + period // 2
        if h + 600 < n:
            out[h:h + 600] += tock
    return out


# ---------------------------------------------------------------- v2: street ambience (2026-11-03)
# User: v1 engine pulses + rattles sounded like a broken gearbox / interference. What the mic should
# catch is road noise, wind from an open window, passing traffic and its horns - smooth, no clatter.
def road_smooth(n, rng):
    brown = np.cumsum(rng.standard_normal(n))
    brown = _hp(brown - np.mean(brown), 30)
    roar = _lp(brown, 900)
    hiss = _bp(rng.standard_normal(n), 700, 3200)
    out = roar / _rms(roar) + 0.45 * hiss / _rms(hiss)
    return out * _slow(n, rng, 0.15, 0.12)


def window_wind(n, rng, opening):
    """Open window: low buffeting that flutters + airy hiss with gusts."""
    gust = _slow(n, rng, 0.35, 0.5)
    flutter = _slow(n, rng, 6.0, 0.35)
    buff = _bp(rng.standard_normal(n), 120, 700) * gust * flutter
    air = _bp(rng.standard_normal(n), 900, 4500) * gust
    out = buff / _rms(buff) * opening + air / _rms(air) * (0.35 + 0.4 * opening)
    return out


def passing(n, rng, rate):
    """Vehicles passing by: a swell of tyre/engine noise that drops in pitch as it goes past."""
    out = np.zeros(n)
    t = np.arange(n) / SR
    for _ in range(int(rng.poisson(rate * n / SR)) or (1 if rng.random() < rate * 3 else 0)):
        tc = rng.uniform(0.15, 0.9) * n / SR
        w = rng.uniform(0.35, 0.9)                          # how fast it goes by
        env = 1.0 / (1.0 + ((t - tc) / w) ** 2)
        truck = rng.random() < 0.4
        lo1, hi1 = (300, 2500) if truck else (600, 3800)
        before = _bp(rng.standard_normal(n), lo1, hi1)
        after = _bp(rng.standard_normal(n), lo1 * 0.7, hi1 * 0.6)  # doppler: lower once past
        mix = 1 / (1 + np.exp(-(t - tc) / 0.08))
        s = (before / _rms(before)) * (1 - mix) + (after / _rms(after)) * mix
        out += s * env * rng.uniform(0.6, 1.4) * (1.3 if truck else 1.0)
    return out


def horn(rng, n):
    """A distant horn somewhere in the traffic: car beep(s) or a truck air horn. n = samples."""
    out = np.zeros(n)
    truck = rng.random() < 0.45
    if truck:
        freqs, dur, beeps = [rng.uniform(220, 240) * r for r in (1.0, 1.26, 1.5)], rng.uniform(0.6, 1.3), 1
    else:
        f = rng.uniform(380, 450)
        freqs, dur, beeps = [f, f * 1.25], rng.uniform(0.15, 0.4), int(rng.integers(1, 3))
    m = int(dur * SR)
    k = np.arange(m) / SR
    tone = np.zeros(m)
    for f in freqs:
        for h in range(1, 7):                               # brassy: odd+even harmonics
            tone += np.sin(2 * np.pi * f * h * k + rng.uniform(0, 6.3)) / h ** 1.1
    att = int(0.015 * SR)
    env = np.ones(m)
    env[:att] = np.linspace(0, 1, att)
    env[-att:] = np.linspace(1, 0, att)
    tone *= env
    tail = np.exp(-np.arange(int(0.35 * SR)) / (0.08 * SR)) * rng.standard_normal(int(0.35 * SR))
    tone = np.convolve(tone, np.concatenate([[1.0], tail * 0.04]))[:m + len(tail)]   # a bit of space
    tone = _lp(tone, 2200)                                   # far away
    start = int(rng.uniform(0.05, 0.75) * n)
    for b in range(beeps):
        s = start + b * int((dur + 0.12) * SR)
        e = min(n, s + len(tone))
        if s < n:
            out[s:e] += tone[: e - s]
    return out


def drone(n, rng, rpm):
    """Own engine as a smooth steady hum (no firing clatter)."""
    f = rpm / 60 * 3
    t = np.arange(n) / SR
    wob = _slow(n, rng, 0.2, 0.02)
    hum = sum(np.sin(2 * np.pi * f * h * np.cumsum(wob) / SR + rng.uniform(0, 6.3)) / h for h in range(1, 9))
    noise = _bp(rng.standard_normal(n), 150, 900)
    out = hum / _rms(hum) + 0.6 * noise / _rms(noise)
    return out * (1 + 0 * t)


def bed(n, cab, rng, ref_rms):
    """v2 cab background: road + open-window wind + passing traffic + rare horns + soft engine hum.
    Levels (dB) are relative to the voice RMS, measured in the CB band."""
    if not cab:
        return np.zeros(n)
    j = lambda: rng.uniform(-2, 2)  # noqa: E731
    out = _audible(road_smooth(n, rng)) * 10 ** ((cab.get("road_db", -19) + j()) / 20)
    win = cab.get("window", 0.5)
    out += _audible(window_wind(n, rng, win)) * 10 ** ((cab.get("wind_db", -22) + j()) / 20)
    p = passing(n, rng, cab.get("traffic", 0.15))
    if np.any(p):
        out += p / _rms(_bp(p, 300, 3200)) * 10 ** ((cab.get("traffic_db", -17) + j()) / 20) * np.sqrt(
            np.mean(np.abs(p) > 0.1 * np.max(np.abs(p))))
    if rng.random() < cab.get("horn_chance", 0.15):
        h = horn(rng, n)
        out += h / np.max(np.abs(h)) * 10 ** ((cab.get("horn_db", -14) + j()) / 20)
    out += _audible(drone(n, rng, cab.get("rpm", 1300))) * 10 ** ((cab.get("engine_db", -27) + j()) / 20)
    if cab.get("extras"):                       # his radio, scanner, kitten, phone... (cab_extras.py)
        import cab_extras
        out += cab_extras.render(n, cab["extras"], rng)
    f = min(n // 2, int(0.02 * SR))
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out * ref_rms


def _audible(x):
    """Normalise by the part a CB radio passes (300-3200 Hz), so a dB setting means what you hear."""
    return x / _rms(_bp(x, 300, 3200))


def bed_v1(n, cab, rng, ref_rms):
    """OLD v1 (engine pulses + rattles) - rejected by the user, kept for reference only."""
    if not cab:
        return np.zeros(n)
    jitter = lambda: rng.uniform(-2, 2)  # noqa: E731
    out = _audible(engine(n, rng, cab.get("rpm", 1300) * rng.uniform(0.92, 1.08), cab.get("turbo", 0.0))) \
        * 10 ** ((cab.get("engine_db", -16) + jitter()) / 20)
    out += _audible(road(n, rng)) * 10 ** ((cab.get("road_db", -20) + jitter()) / 20)
    out += _audible(wind(n, rng)) * 10 ** ((cab.get("wind_db", -32) + jitter()) / 20)
    # sparse clicks: level by PEAK relative to the voice RMS (rms of a sparse signal means nothing)
    r = rattles(n, rng, cab.get("rattle", 0.3))
    if np.any(r):
        out += r / np.max(np.abs(r)) * 10 ** ((cab.get("rattle_db", -14) + jitter()) / 20)
    if rng.random() < cab.get("blinker_chance", 0.1):
        b = blinker(n, rng)
        if np.any(b):
            out += b / np.max(np.abs(b)) * 10 ** (cab.get("blinker_db", -10) / 20)
    # fade in/out over 20 ms so the bed starts with the mic, not with a click
    f = min(n // 2, int(0.02 * SR))
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out * ref_rms


def with_bed(voice, cab, rng, pre_s=0.18, post_s=0.25):
    """Pad the dry voice (mic open a bit before and after the words) and mix the cab under it."""
    if not cab:
        return voice
    v = np.concatenate([np.zeros(int(pre_s * SR)), voice, np.zeros(int(post_s * SR))])
    act = voice[np.abs(voice) > 0.02 * np.max(np.abs(voice))]
    ref = _rms(act) if len(act) else _rms(voice)
    return (v + bed(len(v), cab, rng, ref)).astype(np.float32)


def kerchunk_bed(seconds, cab, rng):
    """A key-up without words: just the cab for a moment."""
    n = int(seconds * SR)
    return bed(n, cab, rng, 0.1).astype(np.float32)
